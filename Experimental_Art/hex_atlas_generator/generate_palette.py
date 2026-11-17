"""Generate flat-color atlases from named palette presets."""

import argparse
import colorsys
import json
from pathlib import Path

from generate_atlas import hex_to_rgb
from generate_atlas_flat import generate_atlas


ROOT = Path(__file__).parent
PALETTE_DIR = ROOT / "palettes"
OUTPUT_DIR = ROOT / "palette_atlases"


def rgb_to_hex(color: tuple[int, int, int]) -> str:
    return "#%02X%02X%02X" % color


def apply_variant(color: tuple[int, int, int], variant: str) -> tuple[int, int, int]:
    """Apply a restrained style variation while keeping the palette recognizable."""
    if variant == "base":
        return color

    red, green, blue = (channel / 255 for channel in color)
    hue, saturation, value = colorsys.rgb_to_hsv(red, green, blue)

    if variant == "muted":
        saturation *= 0.55
    elif variant == "vibrant":
        saturation = min(1.0, saturation * 1.35)
    elif variant == "dark":
        value *= 0.70
    elif variant == "pastel":
        saturation *= 0.45
        value = min(1.0, value * 1.08)
    else:
        raise ValueError(f"Unknown palette variant: {variant}")

    return tuple(round(channel * 255) for channel in colorsys.hsv_to_rgb(hue, saturation, value))


def load_palette(name: str) -> tuple[dict, list[str]]:
    path = PALETTE_DIR / f"{name}.json"
    if not path.is_file():
        available = ", ".join(sorted(path.stem for path in PALETTE_DIR.glob("*.json")))
        raise ValueError(f"Unknown palette {name!r}. Available palettes: {available}")

    data = json.loads(path.read_text(encoding="utf-8"))
    values = data.get("colors")
    if not isinstance(values, list) or not values:
        raise ValueError(f"{path.name} must contain a non-empty 'colors' array.")

    for value in values:
        hex_to_rgb(value)

    return data, values


def output_paths(palette_name: str, variant: str, tones: int) -> tuple[Path, Path]:
    suffix_parts = []
    if variant != "base":
        suffix_parts.append(variant)
    if tones == 5:
        suffix_parts.append("5tone")
    suffix = "_" + "_".join(suffix_parts) if suffix_parts else ""
    stem = f"hex_atlas_{palette_name}{suffix}"
    return OUTPUT_DIR / f"{stem}.png", OUTPUT_DIR / f"{stem}_map.json"


def generate_palette(palette_name: str, variant: str, tones: int, gutter: int) -> Path:
    data, source_values = load_palette(palette_name)
    transformed_colors = [apply_variant(hex_to_rgb(value), variant) for value in source_values]
    transformed_values = [rgb_to_hex(color) for color in transformed_colors]
    output_file, map_file = output_paths(palette_name, variant, tones)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    generate_atlas(transformed_colors, transformed_values, tones, output_file, map_file, gutter)

    atlas_map = json.loads(map_file.read_text(encoding="utf-8"))
    atlas_map.update(
        {
            "palette": data.get("name", palette_name),
            "description": data.get("description", ""),
            "variant": variant,
            "source_palette": source_values,
        }
    )
    map_file.write_text(json.dumps(atlas_map, indent=2) + "\n", encoding="utf-8")
    print(f"Generated {output_file.name} using {len(source_values)} colors and {len(source_values) * tones} swatches.")
    return output_file


def list_palettes() -> None:
    for path in sorted(PALETTE_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        print(f"{path.stem:12} {data.get('description', '')}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--palette", help="Palette preset name, such as autumn or cyberpunk.")
    selection.add_argument("--all", action="store_true", help="Generate an atlas for every preset.")
    selection.add_argument("--list", action="store_true", help="List available presets.")
    parser.add_argument("--variant", choices=("base", "muted", "vibrant", "dark", "pastel"), default="base")
    parser.add_argument("--tones", type=int, choices=(3, 5), default=3)
    parser.add_argument("--gutter", type=int, default=4)
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    if arguments.list:
        list_palettes()
    elif arguments.all:
        if arguments.gutter < 0:
            raise SystemExit("--gutter must be zero or greater.")
        for palette_path in sorted(PALETTE_DIR.glob("*.json")):
            generate_palette(palette_path.stem, arguments.variant, arguments.tones, arguments.gutter)
    elif arguments.palette:
        if arguments.gutter < 0:
            raise SystemExit("--gutter must be zero or greater.")
        generate_palette(arguments.palette, arguments.variant, arguments.tones, arguments.gutter)
    else:
        raise SystemExit("Choose --palette NAME, --all, or --list.")
