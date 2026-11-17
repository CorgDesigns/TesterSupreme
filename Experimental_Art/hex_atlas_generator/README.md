# Hex Atlas Generator

Add the colors you want to use to `colors.json`. The generator accepts `#RRGGBB` and `#RGB` values.

Install the image dependency:

```powershell
py -m pip install -r requirements.txt
```

Generate the atlas:

```powershell
py generate_atlas.py
```

The program creates `hex_atlas.png`, which is always 1024×1024 pixels. Colors are arranged as evenly sized tiles in a square-like grid.

To create highlight, base, and shadow variants for every color, run:

```powershell
py generate_atlas_H_S.py
```

This creates `hex_atlas_H_S.png`. Each row contains the highlight, original color, and shadow from left to right. Highlights blend 25% toward white, while shadows blend 25% toward black.

For a model-friendly flat-color atlas with square swatches and padding, run:

```powershell
py generate_atlas_flat.py
```

This creates `hex_atlas_flat.png` and `hex_atlas_flat_map.json`. The map provides each swatch's pixel rectangle and UV center. The default layout is:

```text
[ Shadow ][ Base ][ Highlight ]
```

To generate the five-tone version:

```powershell
py generate_atlas_flat.py --tones 5 --output hex_atlas_flat_5tone.png --map-output hex_atlas_flat_5tone_map.json
```

The five-tone layout is:

```text
[ Deep Shadow ][ Shadow ][ Base ][ Light ][ Highlight ]
```

Use nearest-neighbor filtering when sampling these atlases so the flat colors stay crisp and do not blend across swatch edges.

## Palette presets

The `palettes` folder contains reusable themes for seasons, moods, environments, and visual styles. View the available presets:

```powershell
py generate_palette.py --list
```

Generate one preset:

```powershell
py generate_palette.py --palette autumn
```

Generate every preset:

```powershell
py generate_palette.py --all
```

Preset outputs are written to `palette_atlases`. Variants are available through `--variant base`, `muted`, `vibrant`, `dark`, or `pastel`:

```powershell
py generate_palette.py --palette cyberpunk --variant muted --tones 5
```

To create a new theme, copy any JSON file in `palettes`, rename it, and replace its `colors` list with your own hex values.
