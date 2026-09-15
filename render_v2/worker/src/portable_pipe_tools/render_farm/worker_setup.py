"""Explicit setup diagnostics. Never claims a job or installs project resources."""

from dataclasses import dataclass, field
from pathlib import Path
import shutil
import re
import tempfile

from portable_pipe_tools.render_farm.queue import read_json_object
from portable_pipe_tools.render_farm.v2_gui_settings import load_registered_projects


@dataclass
class SetupReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    projects: list[str] = field(default_factory=list)

    @property
    def ok(self):
        return not self.errors

    def describe(self):
        lines = ["Setup checks passed." if self.ok else "Setup needs attention."]
        lines += ["ERROR: " + value for value in self.errors]
        lines += ["NOTE: " + value for value in self.warnings]
        if self.projects:
            lines.append("Local projects checked: " + ", ".join(self.projects))
        lines.append("No jobs were claimed. Asset completeness and GPU compatibility require a test render.")
        return "\n".join(lines)


def _check_writable(folder: Path):
    # Probe only the explicitly configured folders; the temporary file removes itself.
    with tempfile.TemporaryFile(prefix=".worker-v2-check-", dir=folder) as stream:
        stream.write(b"check")
        stream.flush()


def check_worker_setup(settings_path: Path, *, dispatcher=None) -> SetupReport:
    report = SetupReport()
    settings = read_json_object(settings_path)
    engine = Path(settings.get("unreal_editor_cmd") or "")
    if not engine.is_absolute() or not engine.is_file() or engine.name.casefold() != "unrealeditor-cmd.exe":
        report.errors.append("Choose an installed UnrealEditor-Cmd.exe.")
    engine_version = None
    if engine.is_file() and len(engine.parents) > 2:
        version_file = engine.parents[2] / "Build/Build.version"
        if version_file.is_file():
            try:
                version = read_json_object(version_file)
                engine_version = f"{version['MajorVersion']}.{version['MinorVersion']}"
            except (OSError, ValueError, KeyError):
                report.warnings.append("Could not read the engine version; verify it matches each project.")
    projects = load_registered_projects(settings_path)
    if not projects:
        report.errors.append("Add at least one local project using the + button.")
    for project in projects:
        try:
            uproject = Path(project.local_uproject)
            metadata = read_json_object(uproject)
            association = str(metadata.get("EngineAssociation", ""))
            if engine_version and re.fullmatch(r"\d+\.\d+(?:\.\d+)?", association) and ".".join(association.split(".")[:2]) != engine_version:
                raise ValueError(f"Project requires Unreal {association}; selected engine is {engine_version}")
            farm = Path(project.render_farm_root)
            if not farm.is_dir() or farm.parent.name.casefold() != project.project_id.casefold():
                raise ValueError("The registered show/renderFarm folder is missing or mismatched")
            plugin = uproject.parent / "Plugins/RenderWorkerRuntime"
            if plugin.exists() and not (plugin / ".render-worker-runtime").is_file():
                raise ValueError("An unmanaged RenderWorkerRuntime plugin already exists; review it before rendering")
            targets = [uproject.parent, farm, farm.parent]
            if (uproject.parent / "Plugins").is_dir():
                targets.append(uproject.parent / "Plugins")
            if plugin.is_dir():
                targets.append(plugin)
            for folder in targets:
                _check_writable(folder)
            if min(shutil.disk_usage(uproject.parent).free, shutil.disk_usage(farm).free) < 10 * 1024**3:
                report.warnings.append(f"{project.project_id}: less than 10 GB free; confirm space for the render.")
            report.projects.append(project.project_id)
        except (OSError, ValueError) as error:
            report.errors.append(f"{project.project_id}: {error}")
    if dispatcher is not None:
        try:
            if dispatcher.check_auth() != "worker":
                raise ValueError("Use a worker credential, not a manager, submitter or viewer credential")
        except Exception as error:
            report.errors.append(f"Dispatcher connection failed: {error}")
    else:
        report.errors.append("The company V2 SQL service connection is required; filesystem coordination is not supported.")
    return report
