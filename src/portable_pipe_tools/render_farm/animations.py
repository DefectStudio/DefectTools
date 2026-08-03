from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import struct

from portable_pipe_tools.render_farm.worker import WorkerStage


SPRITE_FRAME_SIZE = 48
SPRITE_DISPLAY_SCALE = 2
SPRITE_FRAME_INTERVAL_MS = 140

DEFAULT_ANIMATION_SPRITE_FOLDER = (
    Path(__file__).resolve().parents[3] / "spriteImages"
)

STAGE_SPRITE_FILENAMES: dict[WorkerStage, str] = {
    WorkerStage.WAITING: "Base_Idle.png",
    WorkerStage.MOVING: "Base_Run.png",
    WorkerStage.RENDERING: "Base_WateringCan.png",
    WorkerStage.FINISHING: "Base_Hoe.png",
}

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


@dataclass(frozen=True)
class SpriteSheetInfo:
    path: Path
    width: int
    height: int
    frame_count: int
    has_alpha: bool


def inspect_sprite_sheet(path: str | Path) -> SpriteSheetInfo:
    sprite_path = Path(path)
    with sprite_path.open("rb") as handle:
        header = handle.read(26)

    if len(header) < 26 or header[:8] != _PNG_SIGNATURE:
        raise ValueError(f"Animation sprite is not a valid PNG: {sprite_path}")
    if header[12:16] != b"IHDR":
        raise ValueError(f"Animation sprite has no PNG IHDR header: {sprite_path}")

    width, height = struct.unpack(">II", header[16:24])
    color_type = header[25]
    has_alpha = color_type in (4, 6)

    if height != SPRITE_FRAME_SIZE:
        raise ValueError(
            f"Sprite sheet must be {SPRITE_FRAME_SIZE}px high: "
            f"{sprite_path} is {height}px"
        )
    if width == 0 or width % SPRITE_FRAME_SIZE != 0:
        raise ValueError(
            f"Sprite sheet width must be a multiple of {SPRITE_FRAME_SIZE}px: "
            f"{sprite_path} is {width}px"
        )
    if not has_alpha:
        raise ValueError(f"Sprite sheet must include an alpha channel: {sprite_path}")

    return SpriteSheetInfo(
        path=sprite_path,
        width=width,
        height=height,
        frame_count=width // SPRITE_FRAME_SIZE,
        has_alpha=has_alpha,
    )


def get_stage_sprite_paths(sprite_folder: str | Path) -> dict[WorkerStage, Path]:
    folder = Path(sprite_folder).expanduser()
    return {
        stage: folder / filename
        for stage, filename in STAGE_SPRITE_FILENAMES.items()
    }
