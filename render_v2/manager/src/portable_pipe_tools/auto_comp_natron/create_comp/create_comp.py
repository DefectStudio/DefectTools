from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import html
from pathlib import Path
import re
import shutil


TEMPLATE_SEQUENCE = "ZZZ"
TEMPLATE_SHOT_NUMBER = "0000"
INITIAL_COMP_VERSION = 1
BUNDLED_TEMPLATE_FILENAME = "default_comp_template.ntp"
_PROJECT_PATHS_VALUE = re.compile(
    r"(<Name>projectPaths</Name>.*?<Value>)(.*?)(</Value>)",
    re.DOTALL,
)
_PROJECT_PATH_ENTRY = re.compile(
    r"(&lt;Name&gt;Project&lt;/Name&gt;&lt;Value&gt;).*?(&lt;/Value&gt;)",
    re.DOTALL,
)
DiagnosticLog = Callable[[str], None]


def _log_step(diagnostic_log: DiagnosticLog | None, message: str) -> None:
    if diagnostic_log is not None:
        diagnostic_log(message)


class CompAlreadyExistsError(FileExistsError):
    def __init__(self, comp_path: Path) -> None:
        self.comp_path = comp_path
        super().__init__(f"A comp already exists for this shot: {comp_path}")


class CompTemplateNotFoundError(FileNotFoundError):
    def __init__(self, candidates: tuple[Path, ...]) -> None:
        self.candidates = candidates
        candidate_list = "\n".join(f"  {path}" for path in candidates)
        super().__init__(f"No comp template was found. Checked:\n{candidate_list}")


@dataclass(frozen=True)
class CreateCompResult:
    target_path: Path
    template_path: Path
    used_fallback_template: bool


@dataclass(frozen=True)
class SmartWriteOutputOptions:
    exr: bool = True
    mp4: bool = True
    mov: bool = False
    hero: bool = True


def _template_shot_name(sequence_name: str) -> str:
    return f"{sequence_name}_000_{TEMPLATE_SHOT_NUMBER}"


def _comp_filename(shot_name: str) -> str:
    return f"{shot_name}_comp_v{INITIAL_COMP_VERSION:03d}.ntp"


def get_comp_path(
    show_root: str | Path,
    sequence_name: str,
    shot_name: str,
) -> Path:
    return (
        Path(show_root)
        / "sequences"
        / sequence_name
        / shot_name
        / "comp"
        / "natron"
        / _comp_filename(shot_name)
    )


def get_bundled_template_path() -> Path:
    return Path(__file__).resolve().parent / "templates" / BUNDLED_TEMPLATE_FILENAME


def get_template_candidates(
    show_root: str | Path,
    sequence_name: str,
) -> tuple[Path, ...]:
    root = Path(show_root)
    sequence_template_shot = _template_shot_name(sequence_name)
    fallback_template_shot = _template_shot_name(TEMPLATE_SEQUENCE)
    candidates = [
        get_comp_path(
            root,
            sequence_name,
            sequence_template_shot,
        )
    ]
    fallback_path = get_comp_path(
        root,
        TEMPLATE_SEQUENCE,
        fallback_template_shot,
    )
    if fallback_path not in candidates:
        candidates.append(fallback_path)
    bundled_template_path = get_bundled_template_path()
    if bundled_template_path not in candidates:
        candidates.append(bundled_template_path)
    return tuple(candidates)


def _validate_selection(sequence_name: str, shot_name: str) -> None:
    expected_prefix = f"{sequence_name}_"
    if not sequence_name or not shot_name.startswith(expected_prefix):
        raise ValueError(
            f"Shot {shot_name!r} does not belong to sequence {sequence_name!r}."
        )


def _copy_without_overwrite(source_path: Path, target_path: Path) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    created_target = False
    try:
        with source_path.open("rb") as source_file:
            with target_path.open("xb") as target_file:
                created_target = True
                shutil.copyfileobj(source_file, target_file)
        shutil.copystat(source_path, target_path)
    except Exception:
        if created_target:
            target_path.unlink(missing_ok=True)
        raise


def _set_natron_project_directory(comp_path: Path) -> None:
    """Point Natron's named Project path at the copied comp's real directory."""

    try:
        project_text = comp_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return

    escaped_directory = html.escape(comp_path.parent.as_posix(), quote=True)

    def replace_project_paths(match: re.Match[str]) -> str:
        table_value, replacements = _PROJECT_PATH_ENTRY.subn(
            lambda entry: entry.group(1) + escaped_directory + entry.group(2),
            match.group(2),
            count=1,
        )
        if replacements == 0:
            return match.group(0)
        return match.group(1) + table_value + match.group(3)

    updated_text = _PROJECT_PATHS_VALUE.sub(
        replace_project_paths,
        project_text,
        count=1,
    )
    if updated_text != project_text:
        comp_path.write_text(updated_text, encoding="utf-8")


def _set_smart_write_outputs(
    comp_path: Path,
    output_options: SmartWriteOutputOptions,
) -> None:
    """Persist Auto Comp's output choices on every SmartWrite in the template."""

    try:
        project_text = comp_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return

    output_values = {
        "exrOutput": output_options.exr,
        "mp4Output": output_options.mp4,
        "movOutput": output_options.mov,
        "heroOutput": output_options.hero,
    }
    updated_text = project_text
    for parameter_name, enabled in output_values.items():
        value_pattern = re.compile(
            r"(<Name>"
            + re.escape(parameter_name)
            + r"</Name>\s*<Type>Bool</Type>.*?<Value>)(?:0|1)(</Value>)",
            re.DOTALL,
        )
        updated_text = value_pattern.sub(
            lambda match: match.group(1)
            + ("1" if enabled else "0")
            + match.group(2),
            updated_text,
        )

    if updated_text != project_text:
        comp_path.write_text(updated_text, encoding="utf-8")


def create_comp(
    show_root: str | Path,
    sequence_name: str,
    shot_name: str,
    *,
    smart_write_outputs: SmartWriteOutputOptions | None = None,
    diagnostic_log: DiagnosticLog | None = None,
) -> CreateCompResult:
    sequence = sequence_name.strip().upper()
    shot = shot_name.strip()
    _log_step(
        diagnostic_log,
        f"Create comp: validating selection sequence={sequence!r}, shot={shot!r}",
    )
    _validate_selection(sequence, shot)

    target_path = get_comp_path(show_root, sequence, shot)
    _log_step(diagnostic_log, f"Create comp: target path is {target_path}")
    if target_path.exists():
        _log_step(diagnostic_log, "Create comp: target already exists")
        raise CompAlreadyExistsError(target_path)

    template_candidates = get_template_candidates(show_root, sequence)
    _log_step(
        diagnostic_log,
        "Create comp: template candidates are "
        + "; ".join(str(candidate) for candidate in template_candidates),
    )
    template_path = next(
        (candidate for candidate in template_candidates if candidate.is_file()),
        None,
    )
    if template_path is None:
        _log_step(diagnostic_log, "Create comp: no template candidate exists")
        raise CompTemplateNotFoundError(template_candidates)
    _log_step(diagnostic_log, f"Create comp: selected template {template_path}")

    try:
        _log_step(diagnostic_log, "Create comp: copying template without overwrite")
        _copy_without_overwrite(template_path, target_path)
        _log_step(diagnostic_log, "Create comp: updating Natron Project directory")
        _set_natron_project_directory(target_path)
        if smart_write_outputs is not None:
            _log_step(
                diagnostic_log,
                f"Create comp: applying SmartWrite outputs {smart_write_outputs!r}",
            )
            _set_smart_write_outputs(target_path, smart_write_outputs)
    except FileExistsError as error:
        _log_step(diagnostic_log, "Create comp: target appeared during creation")
        raise CompAlreadyExistsError(target_path) from error
    except Exception:
        _log_step(diagnostic_log, "Create comp: failed; removing partial target")
        target_path.unlink(missing_ok=True)
        raise

    _log_step(diagnostic_log, f"Create comp: completed successfully at {target_path}")

    return CreateCompResult(
        target_path=target_path,
        template_path=template_path,
        used_fallback_template=template_path != template_candidates[0],
    )
