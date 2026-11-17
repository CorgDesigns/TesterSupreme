import json
import math
import logging
from pathlib import Path

from PIL import Image, ImageDraw

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

SIZE = 1024
COLORS_FILE = Path(__file__).with_name("colors.json")
OUTPUT_FILE = Path(__file__).with_name("hex_atlas.png")

def hex_to_rgb(value: str) -> tuple[int, int, int]:
    """Convert a #RRGGBB, #RGB, #RRGGBBAA, or #RGBA value into an RGB tuple (alpha is dropped)."""
    if not isinstance(value, str):
        raise ValueError(f"Color values must be strings: {value!r}")

    color = value.strip().removeprefix("#")
    if len(color) in (3, 4):
        color = "".join(character * 2 for character in color)
    if len(color) == 8:
        color = color[:6]
    if len(color) != 6:
        raise ValueError(f"Invalid hex color {value!r}; use #RRGGBB, #RGB, #RRGGBBAA, or #RGBA.")

    try:
        return tuple(int(color[index : index + 2], 16) for index in (0, 2, 4))
    except ValueError as error:
        raise ValueError(f"Invalid hex color {value!r}; use hexadecimal digits only.") from error

def load_colors() -> list[tuple[int, int, int]]:
    try:
        with COLORS_FILE.open("r", encoding="utf-8") as file:
            values = json.load(file)

        if not isinstance(values, list) or not values:
            raise ValueError("colors.json must contain a non-empty JSON array of hex colors.")

        colors = [hex_to_rgb(value) for value in values]

        seen: dict[tuple[int, int, int], list[int]] = {}
        for index, color in enumerate(colors):
            seen.setdefault(color, []).append(index)

        duplicates = {color: indices for color, indices in seen.items() if len(indices) > 1}
        if duplicates:
            lines = [
                f"  {values[indices[0]]} repeated at entries {[i + 1 for i in indices]}"
                for indices in duplicates.values()
            ]
            raise ValueError(
                "colors.json contains duplicate colors (same RGB after resolving hex/alpha):\n"
                + "\n".join(lines)
                + "\nRemove or change the repeated entries before generating the atlas."
            )

        return colors
    except json.JSONDecodeError as e:
        logging.error(f"Failed to decode JSON from {COLORS_FILE}: {e}")
        raise
    except FileNotFoundError:
        logging.error(f"File not found: {COLORS_FILE}")
        raise
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        raise

def generate_atlas(colors: list[tuple[int, int, int]]) -> None:
    columns = math.ceil(math.sqrt(len(colors)))
    rows = math.ceil(len(colors) / columns)
    image = Image.new("RGB", (SIZE, SIZE), (0, 0, 0))
    draw = ImageDraw.Draw(image)

    for index, color in enumerate(colors):
        column = index % columns
        row = index // columns
        left = column * SIZE // columns
        top = row * SIZE // rows
        right = (column + 1) * SIZE // columns
        bottom = (row + 1) * SIZE // rows
        draw.rectangle((left, top, right - 1, bottom - 1), fill=color)

    image.save(OUTPUT_FILE)
    logging.info(f"Generated {OUTPUT_FILE.name} using {len(colors)} colors.")

if __name__ == "__main__":
    try:
        colors = load_colors()
        generate_atlas(colors)
    except Exception as e:
        logging.error(f"An error occurred: {e}")