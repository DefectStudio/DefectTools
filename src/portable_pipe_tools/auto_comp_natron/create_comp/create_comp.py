from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil


TEMPLATE_SEQUENCE = "ZZZ"
TEMPLATE_SHOT_NUMBER = "0000"
INITIAL_COMP_VERSION = 1


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


def create_comp(
    show_root: str | Path,
    sequence_name: str,
    shot_name: str,
) -> CreateCompResult:
    sequence = sequence_name.strip().upper()
    shot = shot_name.strip()
    _validate_selection(sequence, shot)

    target_path = get_comp_path(show_root, sequence, shot)
    if target_path.exists():
        raise CompAlreadyExistsError(target_path)

    template_candidates = get_template_candidates(show_root, sequence)
    template_path = next(
        (candidate for candidate in template_candidates if candidate.is_file()),
        None,
    )
    if template_path is None:
        raise CompTemplateNotFoundError(template_candidates)

    try:
        _copy_without_overwrite(template_path, target_path)
    except FileExistsError as error:
        raise CompAlreadyExistsError(target_path) from error

    return CreateCompResult(
        target_path=target_path,
        template_path=template_path,
        used_fallback_template=template_path == template_candidates[-1]
        and len(template_candidates) > 1,
    )
