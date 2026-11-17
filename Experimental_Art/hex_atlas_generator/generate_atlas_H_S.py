"""Generate a 1024x1024 highlight/base/shadow atlas from colors.json."""

from pathlib import Path

from PIL import Image, ImageDraw

from generate_atlas import SIZE, load_colors


OUTPUT_FILE = Path(__file__).with_name("hex_atlas_H_S.png")
HIGHLIGHT_AMOUNT = 0.25
SHADOW_AMOUNT = 0.25


def blend_with(color: tuple[int, int, int], target: tuple[int, int, int], amount: float) -> tuple[int, int, int]:
    """Blend a color toward a target color by the given amount."""
    return tuple(round(channel + (target[index] - channel) * amount) for index, channel in enumerate(color))


def generate_atlas(colors: list[tuple[int, int, int]]) -> None:
    """Create one highlight/base/shadow row for every source color."""
    row_count = len(colors)
    image = Image.new("RGB", (SIZE, SIZE), (0, 0, 0))
    draw = ImageDraw.Draw(image)

    for row, color in enumerate(colors):
        highlight = blend_with(color, (255, 255, 255), HIGHLIGHT_AMOUNT)
        shadow = blend_with(color, (0, 0, 0), SHADOW_AMOUNT)
        variants = (highlight, color, shadow)

        top = row * SIZE // row_count
        bottom = (row + 1) * SIZE // row_count

        for column, variant in enumerate(variants):
            left = column * SIZE // 3
            right = (column + 1) * SIZE // 3
            draw.rectangle((left, top, right - 1, bottom - 1), fill=variant)

    image.save(OUTPUT_FILE)


if __name__ == "__main__":
    colors = load_colors()
    generate_atlas(colors)
    print(f"Generated {OUTPUT_FILE.name} using {len(colors)} colors and {len(colors) * 3} variants.")
