"""Generate a clean flat-color palette atlas from colors.json.

The default atlas gives every source color three square swatches:
shadow, base color, and highlight. A five-tone ramp is also available.
"""

import argparse
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw

from generate_atlas import SIZE, load_colors


DEFAULT_GUTTER = 4
DEFAULT_OUTPUT = "hex_atlas_flat.png"
DEFAULT_MAP = "hex_atlas_flat_map.json"
ATLAS_BACKGROUND = (32, 32, 32)


def blend_with(
    color: tuple[int, int, int],
    target: tuple[int, int, int],
    amount: float,
) -> tuple[int, int, int]:
    """Blend a color toward a target color by the given amount."""
    return tuple(
        round(channel + (target[index] - channel) * amount)
        for index, channel in enumerate(color)
    )


def make_variants(color: tuple[int, int, int], tone_count: int) -> list[tuple[int, int, int]]:
    """Return the requested tone ramp in shadow-to-highlight order."""
    if tone_count == 3:
        amounts = (0.25, None, 0.25)
    elif tone_count == 5:
        amounts = (0.50, 0.25, None, 0.25, 0.50)
    else:
        raise ValueError("tone_count must be either 3 or 5")

    variants = []
    for index, amount in enumerate(amounts):
        if amount is None:
            variants.append(color)
        elif index < tone_count // 2:
            variants.append(blend_with(color, (0, 0, 0), amount))
        else:
            variants.append(blend_with(color, (255, 255, 255), amount))
    return variants


def choose_layout(color_count: int, tone_count: int, gutter: int) -> tuple[int, int, int]:
    """Choose a layout that keeps swatches square and uses the canvas efficiently."""
    best_layout = None

    for group_columns in range(1, color_count + 1):
        group_rows = math.ceil(color_count / group_columns)
        available_width = SIZE - (group_columns * tone_count - 1) * gutter
        available_height = SIZE - (group_rows - 1) * gutter
        tile_size = min(available_width // (group_columns * tone_count), available_height // group_rows)

        if tile_size <= 0:
            continue

        if best_layout is None or tile_size > best_layout[2]:
            best_layout = (group_columns, group_rows, tile_size)

    if best_layout is None:
        raise ValueError("Too many colors for a 1024x1024 atlas with the selected gutter.")

    return best_layout


def generate_atlas(
    colors: list[tuple[int, int, int]],
    source_hex_values: list[str],
    tone_count: int,
    output_file: Path,
    map_file: Path,
    gutter: int = DEFAULT_GUTTER,
) -> None:
    group_columns, group_rows, tile_size = choose_layout(len(colors), tone_count, gutter)
    group_width = tone_count * tile_size + (tone_count - 1) * gutter
    group_height = tile_size
    atlas_width = group_columns * group_width + (group_columns - 1) * gutter
    atlas_height = group_rows * group_height + (group_rows - 1) * gutter
    offset_x = (SIZE - atlas_width) // 2
    offset_y = (SIZE - atlas_height) // 2

    image = Image.new("RGB", (SIZE, SIZE), ATLAS_BACKGROUND)
    draw = ImageDraw.Draw(image)
    entries = []
    tone_names = {
        3: ("shadow", "base", "highlight"),
        5: ("deep_shadow", "shadow", "base", "light", "highlight"),
    }[tone_count]

    for color_index, (color, source_hex) in enumerate(zip(colors, source_hex_values)):
        group_column = color_index % group_columns
        group_row = color_index // group_columns
        group_left = offset_x + group_column * (group_width + gutter)
        group_top = offset_y + group_row * (group_height + gutter)
        variants = make_variants(color, tone_count)
        variant_entries = []

        for tone_index, (tone_name, variant) in enumerate(zip(tone_names, variants)):
            left = group_left + tone_index * (tile_size + gutter)
            top = group_top
            right = left + tile_size
            bottom = top + tile_size
            draw.rectangle((left, top, right - 1, bottom - 1), fill=variant)
            variant_entries.append(
                {
                    "name": tone_name,
                    "x": left,
                    "y": top,
                    "width": tile_size,
                    "height": tile_size,
                    "uv_center": [round((left + tile_size / 2) / SIZE, 6), round((top + tile_size / 2) / SIZE, 6)],
                }
            )

        entries.append({"source_color": source_hex, "variants": variant_entries})

    image.save(output_file)
    map_file.write_text(
        json.dumps(
            {
                "image": output_file.name,
                "size": [SIZE, SIZE],
                "tone_count": tone_count,
                "gutter": gutter,
                "filtering": "nearest",
                "entries": entries,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tones",
        type=int,
        choices=(3, 5),
        default=3,
        help="Number of tones per color: 3 or 5 (default: 3).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).with_name(DEFAULT_OUTPUT),
        help="PNG output path.",
    )
    parser.add_argument(
        "--map-output",
        type=Path,
        default=Path(__file__).with_name(DEFAULT_MAP),
        help="JSON atlas-map output path.",
    )
    parser.add_argument(
        "--gutter",
        type=int,
        default=DEFAULT_GUTTER,
        help="Padding in pixels between swatches (default: 4).",
    )
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    if arguments.gutter < 0:
        raise SystemExit("--gutter must be zero or greater.")

    raw_values = json.loads(Path(__file__).with_name("colors.json").read_text(encoding="utf-8"))
    colors = load_colors()
    generate_atlas(colors, raw_values, arguments.tones, arguments.output, arguments.map_output, arguments.gutter)
    print(
        f"Generated {arguments.output.name} using {len(colors)} colors "
        f"and {len(colors) * arguments.tones} swatches."
    )
