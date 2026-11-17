# Brush Samples

This folder contains one production-generated 512x512 RGB normal-map preview
sample for every `brush_stroke_cells` brush shape.

The samples use the same high-contrast synthetic unit-normal source, an
8-pixel black padding border, seed `42`, and the following showcase controls.
The sparse layout and sharp blending are intentional so the shape silhouettes
remain visible in a preview gallery:

- density: `0.12`
- shape size: `0.82`
- length variation: `0.08`
- edge softness: `1.5`
- curvature: `0.85`
- segments: `6`
- roughness: `0.70`
- symmetry: `0.40`
- branching: `0.80`
- samples per stroke: `11`
- edge selection: `distinct`

Files are numbered in the same order as the brush catalog. See
[`manifest.json`](manifest.json) for the category, description, byte count, and
SHA-256 checksum for every sample.

The PNGs are intended as visual and pipeline examples, not final-resolution
game assets. They are generated from a synthetic source rather than a game
asset, so the source normals show the shape boundaries clearly without implying
a particular material.
