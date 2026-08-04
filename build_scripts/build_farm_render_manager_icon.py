from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ICON_SIZE = 256
EMOJI_FONT = Path(r"C:\Windows\Fonts\seguiemj.ttf")
ASSET_FOLDER = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "portable_pipe_tools"
    / "assets"
)


def main() -> None:
    if not EMOJI_FONT.is_file():
        raise FileNotFoundError(f"Windows emoji font was not found: {EMOJI_FONT}")

    ASSET_FOLDER.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(
        (7, 7, ICON_SIZE - 8, ICON_SIZE - 8),
        radius=48,
        fill="#f7f7f7",
        outline="#d63b3b",
        width=7,
    )

    font = ImageFont.truetype(str(EMOJI_FONT), 170)
    emoji = "🎥"
    bounds = draw.textbbox(
        (0, 0),
        emoji,
        font=font,
        embedded_color=True,
    )
    width = bounds[2] - bounds[0]
    height = bounds[3] - bounds[1]
    draw.text(
        (
            ICON_SIZE / 2 - width / 2 - bounds[0],
            ICON_SIZE / 2 - height / 2 - bounds[1],
        ),
        emoji,
        font=font,
        embedded_color=True,
    )

    png_path = ASSET_FOLDER / "farm_render_manager.png"
    ico_path = ASSET_FOLDER / "farm_render_manager.ico"
    image.save(png_path, format="PNG", optimize=True)
    image.save(
        ico_path,
        format="ICO",
        sizes=((16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)),
    )
    print(f"Wrote {png_path}")
    print(f"Wrote {ico_path}")


if __name__ == "__main__":
    main()
