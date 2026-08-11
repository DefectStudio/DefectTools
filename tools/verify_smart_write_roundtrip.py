from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile


LOAD_FAILURES = (
    "unrecognized or damaged project file",
    "project file loading failed",
    "input stream error",
)
MISSING_WRITER = "does not belong to the project file"
WRITER_SENTINEL = "CODEX_SMARTWRITE_ROUNDTRIP_DO_NOT_RENDER"


def _natron_environment(plugin_directory: Path, profile: Path) -> dict[str, str]:
    environment = os.environ.copy()
    existing_plugins = environment.get("NATRON_PLUGIN_PATH")
    plugin_paths = [str(plugin_directory)]
    if existing_plugins:
        plugin_paths.append(existing_plugins)
    environment["NATRON_PLUGIN_PATH"] = os.pathsep.join(plugin_paths)
    environment["LOCALAPPDATA"] = str(profile / "local")
    environment["APPDATA"] = str(profile / "roaming")
    return environment


def _run_natron(
    renderer: Path,
    project: Path,
    plugin_directory: Path,
    profile: Path,
    onload_script: Path | None = None,
) -> str:
    command = [str(renderer)]
    if onload_script is not None:
        command.extend(("--onload", str(onload_script)))
    command.extend(("--writer", WRITER_SENTINEL, str(project)))
    result = subprocess.run(
        command,
        cwd=plugin_directory.parent,
        env=_natron_environment(plugin_directory, profile),
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    output = "\n".join((result.stdout, result.stderr))
    lowered = output.casefold()
    failures = [message for message in LOAD_FAILURES if message in lowered]
    if failures:
        raise RuntimeError(
            "Natron could not load the project ({0}):\n{1}".format(
                ", ".join(failures), output
            )
        )
    if MISSING_WRITER not in lowered:
        raise RuntimeError(
            "Natron did not reach the expected post-load writer check:\n{0}".format(
                output
            )
        )
    return output


def verify_roundtrip(
    project: Path,
    renderer: Path,
    plugin_directory: Path,
) -> None:
    project = project.resolve()
    renderer = renderer.resolve()
    plugin_directory = plugin_directory.resolve()
    if not project.is_file():
        raise FileNotFoundError(project)
    if not renderer.is_file():
        raise FileNotFoundError(renderer)
    if not plugin_directory.is_dir():
        raise FileNotFoundError(plugin_directory)

    with tempfile.TemporaryDirectory(prefix="smartwrite-roundtrip-") as temp_name:
        temporary = Path(temp_name)
        saved_project = (
            temporary
            / "show"
            / "sequences"
            / "TST"
            / "TST_000_0001"
            / "comp"
            / "natron"
            / "TST_000_0001_comp_v001.ntp"
        )
        saved_project.parent.mkdir(parents=True)
        save_script = temporary / "save_roundtrip.py"
        reload_script = temporary / "verify_choices.py"
        save_script.write_text(
            "TARGET = {0!r}\n"
            "if not app.saveProjectAs(TARGET):\n"
            "    raise RuntimeError('Natron failed to save round-trip project')\n"
            "print('CODEX_SMARTWRITE_ROUNDTRIP_SAVED')\n".format(
                saved_project.as_posix()
            ),
            encoding="utf-8",
        )
        reload_script.write_text(
            "import SmartWriteExt\n"
            "SmartWriteExt.afterProjectLoaded(app)\n"
            "checked = 0\n"
            "empty = []\n"
            "for node in app.getChildren():\n"
            "    if node.getPluginID() != SmartWriteExt.PLUGIN_ID:\n"
            "        continue\n"
            "    for section in SmartWriteExt.SETTINGS_SECTIONS:\n"
            "        prefix = section[4]\n"
            "        for native_name, creator_name in section[5]:\n"
            "            if creator_name != 'createChoiceParam':\n"
            "                continue\n"
            "            checked += 1\n"
            "            name = '{0}_{1}'.format(prefix, native_name)\n"
            "            param = node.getParam(name)\n"
            "            if param is None or not param.getOptions():\n"
            "                empty.append(name)\n"
            "if empty:\n"
            "    raise RuntimeError('Empty SmartWrite choices: {0}'.format(empty))\n"
            "print('CODEX_SMARTWRITE_CHOICES_OK|{0}'.format(checked))\n",
            encoding="utf-8",
        )

        first_output = _run_natron(
            renderer,
            project,
            plugin_directory,
            temporary / "save-profile",
            save_script,
        )
        if "CODEX_SMARTWRITE_ROUNDTRIP_SAVED" not in first_output:
            raise RuntimeError("Natron did not confirm the round-trip save")
        if not saved_project.is_file():
            raise RuntimeError("Natron did not create the round-trip project")

        second_output = _run_natron(
            renderer,
            saved_project,
            plugin_directory,
            temporary / "reload-profile",
            reload_script,
        )
        if "CODEX_SMARTWRITE_CHOICES_OK" not in second_output:
            raise RuntimeError(
                "Natron did not restore the exposed SmartWrite choice options"
            )


def _parser() -> argparse.ArgumentParser:
    repository = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description="Verify that a SmartWrite project survives a Natron save/reload."
    )
    parser.add_argument("project", type=Path)
    parser.add_argument(
        "--renderer",
        type=Path,
        default=Path(os.environ.get("NATRON_RENDERER", r"F:\Natron\bin\NatronRenderer.exe")),
    )
    parser.add_argument(
        "--plugin-directory",
        type=Path,
        default=repository / "natron_plugins",
    )
    return parser


def main() -> int:
    arguments = _parser().parse_args()
    verify_roundtrip(
        arguments.project,
        arguments.renderer,
        arguments.plugin_directory,
    )
    print("SmartWrite Natron save/reload passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
