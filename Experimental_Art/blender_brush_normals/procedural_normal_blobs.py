"""
Procedurally blend small circular "scale" patches into a baked object-space
normal map, on a fixed grid of blocks, forcing adjacent scales to be visibly
distinct from each other rather than relying on the underlying gradient to
already provide contrast.

Two selectable algorithms (set ALGORITHM below), sharing the same block
setup (steps 1-5) and neighbor-differentiation pass:

    1. Import the file.
    2. Load it as a pixel matrix (color data per pixel).
    3. Group pixels into a grid of BLOCK_WIDTH x BLOCK_HEIGHT blocks (must
       be square and between BLOCK_SIZE_MIN/BLOCK_SIZE_MAX, checked before
       any file is touched).
    4. Average the pixels within each block (non-black pixels only -- black
       is treated as empty UV padding, not real surface data).
    5. Associate each block with that average -- a separate block-average
       matrix, one entry per block.
    6. Walk the block-average matrix, and for any block whose average is
       nearly identical to its right/bottom neighbor, nudge that neighbor's
       average (hue and/or shade) so adjacent scales don't disappear into
       each other. This runs before either algorithm paints anything, so
       painting always uses the already-differentiated averages.

ALGORITHM = "center_average_normalization" (the original): find the center
of each block, replace the pixels within a circle there with that block's
own average -- one flat circle per block.

ALGORITHM = "edge_gradient_cascade" (newer): within each row, walk block by
block left to right. Each block gets 3 small circles along its vertical
center -- one at its left edge, one at its true center, one at its right
edge -- rather than a single circle. The right-edge circle's color is a
hue/saturation/value blend halfway between this block's average and the
next block's average; that same blended color becomes the *next* block's
left-edge circle, since the two blocks share that edge pixel. Each block's
own center circle always uses its own (already-differentiated) average
unblended. The result is a gradient that runs from "blended with left
neighbor" to "pure own color" to "blended with right neighbor" within each
block, cascading down through every row. Purely horizontal -- there is no
equivalent blending between vertically-stacked blocks.

Deliberately simple and a little rough on purpose -- meant to prove the
pipeline (this script -> reload in Blender -> re-bake to tangent -> check
on the model) works end to end before adding more randomness/organic
variation.

Drop-folder workflow: every .png in to_process/ gets processed and written
to export/ as fname_processed.png, then the original in to_process/ is
deleted -- so to_process/ is always just a queue of textures waiting to be
processed, never an archive.

Usage:
    pip install numpy pillow
    (edit the parameters below)
    py procedural_normal_blobs.py
"""

import colorsys
import random
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.spatial import cKDTree

# ---- parameters, edit these ----
SCRIPT_DIR = Path(__file__).resolve().parent
IMPORT_DIR = SCRIPT_DIR / "to_process"
EXPORT_DIR = SCRIPT_DIR / "export"

ALGORITHM = "brush_stroke_cells"  # or "center_average_normalization", "edge_gradient_cascade", "voronoi_flow_cells"

BLOCK_WIDTH = 256          # pixels -- blocks must be square, so this must equal BLOCK_HEIGHT. Only used by
BLOCK_HEIGHT = 256         # pixels    center_average_normalization and edge_gradient_cascade, ignored by voronoi_flow_cells.
BLOCK_SIZE_MIN = 64        # blocks smaller than this are rejected
BLOCK_SIZE_MAX = 2048      # blocks larger than this (or larger than the image) are rejected
CIRCLE_RATIO = 0.8         # circle diameter as a fraction of the block size (<1 leaves gaps between scales).
                            # For edge_gradient_cascade this is applied against half the block size instead,
                            # since its 3 circles per block are spaced at half-block intervals, not one per block.
BLACK_THRESHOLD = 10       # pixels with R+G+B below this are treated as empty padding, not surface data
BLEND_STRENGTH = 1.0       # 0 = no change, 1 = fully replace with the block's average inside the circle
SIMILARITY_THRESHOLD = 12  # RGB distance below which two adjacent blocks/cells count as "the same" and get nudged apart
HUE_TWEAK = 0.04           # max random hue shift (0-1 scale) applied when nudging a too-similar neighbor
SHADE_TWEAK = 12           # max random brightness shift (0-255 scale) applied when nudging a too-similar neighbor
RENORMALIZE = True         # keep each pixel a valid unit normal after blending
RANDOM_SEED = None         # set to an int for a reproducible result

# voronoi_flow_cells only, below this line
VORONOI_AVG_CELL_SIZE = 120  # pixels -- target average cell diameter; controls how many seed points get scattered
VORONOI_SIZE_VARIANCE = 0.5  # 0 = every cell the same size, ~1 = large size variation between cells (soccer-ball-like)
VORONOI_ELONGATION_MAX = 2.0 # each cell gets stretched along its own random angle by up to this factor (1 = circular, no stretch)
VORONOI_EDGE_SOFTNESS = 10   # pixels -- how wide the soft blended seam between two cells is
VORONOI_CANDIDATES = 12      # how many nearest seeds (by plain distance) to consider when weight/stretch might reorder them

# brush_stroke_cells only, below this line
STROKE_AVG_SPACING = 130     # pixels -- controls how many strokes get scattered (same role as VORONOI_AVG_CELL_SIZE)
STROKE_LENGTH_MIN = 60       # pixels -- shortest possible stroke (short dabs)
STROKE_LENGTH_MAX = 260      # pixels -- longest possible stroke (long sweeping strokes)
STROKE_WIDTH_VARIANCE = 0.5  # 0 = every stroke the same thickness, ~1 = large thickness variation
STROKE_EDGE_SOFTNESS = 8     # pixels -- how wide the soft blended seam between two strokes is
STROKE_CANDIDATES = 18       # how many nearby sample points to consider per pixel before picking the true nearest stroke
STROKE_SAMPLES_PER_STROKE = 5  # points sampled along each stroke's length for the candidate spatial index -- more
                                # gives more reliable candidate coverage for long strokes, at a small speed cost


def validated_block_size(width, height, min_size, max_size):
    if width != height:
        raise ValueError(f"BLOCK_WIDTH ({width}) and BLOCK_HEIGHT ({height}) must be equal -- blocks must be square.")
    if not (min_size <= width <= max_size):
        raise ValueError(f"Block size {width} is out of range -- must be between {min_size} and {max_size}.")
    return width


def load_normal_image(path):
    img = Image.open(path).convert("RGB")
    return np.array(img, dtype=np.float64)


def save_normal_image(arr, path):
    arr = np.clip(arr, 0, 255).astype(np.uint8)
    Image.fromarray(arr).save(path)


def renormalize_pixels(block):
    # A normal map encodes a unit vector as color: v = color/255*2-1.
    # Averaging or hue-shifting colors doesn't keep the result unit-length,
    # which quietly weakens the bump once this gets re-baked to
    # tangent-space. This undoes the encoding, re-normalizes each vector,
    # and re-encodes.
    vec = (block / 255.0) * 2.0 - 1.0
    length = np.linalg.norm(vec, axis=-1, keepdims=True)
    length = np.where(length < 1e-6, 1.0, length)
    vec = vec / length
    return (vec + 1.0) * 0.5 * 255.0


def compute_block_averages(arr, block_size, black_threshold):
    """Steps 3-5: group into blocks, average non-black pixels, store per block."""
    h, w, _ = arr.shape
    blocks_h = (h + block_size - 1) // block_size
    blocks_w = (w + block_size - 1) // block_size

    averages = np.zeros((blocks_h, blocks_w, 3), dtype=np.float64)
    has_surface = np.zeros((blocks_h, blocks_w), dtype=bool)

    for by in range(blocks_h):
        for bx in range(blocks_w):
            y0, y1 = by * block_size, min((by + 1) * block_size, h)
            x0, x1 = bx * block_size, min((bx + 1) * block_size, w)
            block = arr[y0:y1, x0:x1]
            mask = block.sum(axis=-1) > black_threshold
            if mask.any():
                averages[by, bx] = block[mask].mean(axis=0)
                has_surface[by, bx] = True

    return averages, has_surface, blocks_h, blocks_w


def tweak_color(rgb, hue_shift, shade_shift):
    r, g, b = np.clip(rgb, 0, 255) / 255.0
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    h = (h + random.uniform(-hue_shift, hue_shift)) % 1.0
    v = float(np.clip(v + random.uniform(-shade_shift, shade_shift) / 255.0, 0.0, 1.0))
    r2, g2, b2 = colorsys.hsv_to_rgb(h, s, v)
    return np.array([r2, g2, b2]) * 255.0


def differentiate_neighbors(averages, has_surface, blocks_h, blocks_w, similarity_threshold, hue_shift, shade_shift):
    """Step 8: walk the block-average matrix; nudge a neighbor's average

    whenever it's nearly identical to the current block's, before that
    neighbor is ever painted.
    """
    for by in range(blocks_h):
        for bx in range(blocks_w):
            if not has_surface[by, bx]:
                continue
            current = averages[by, bx]
            for nby, nbx in ((by, bx + 1), (by + 1, bx)):  # only "upcoming" neighbors in this walk order
                if nby >= blocks_h or nbx >= blocks_w or not has_surface[nby, nbx]:
                    continue
                neighbor = averages[nby, nbx]
                if np.linalg.norm(current - neighbor) < similarity_threshold:
                    averages[nby, nbx] = tweak_color(neighbor, hue_shift, shade_shift)
    return averages


def paint_blocks(arr, averages, has_surface, block_size, blocks_h, blocks_w, circle_ratio, blend_strength, black_threshold, renormalize):
    """Steps 6-7: find each block's center, replace pixels inside a circle there with its average."""
    h, w, _ = arr.shape
    out = arr.copy()

    for by in range(blocks_h):
        for bx in range(blocks_w):
            if not has_surface[by, bx]:
                continue

            y0, y1 = by * block_size, min((by + 1) * block_size, h)
            x0, x1 = bx * block_size, min((bx + 1) * block_size, w)
            cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
            radius = (min(x1 - x0, y1 - y0) / 2.0) * circle_ratio

            region = arr[y0:y1, x0:x1]
            surface_mask = region.sum(axis=-1) > black_threshold

            yy, xx = np.mgrid[y0:y1, x0:x1]
            dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
            falloff = np.clip(1.0 - dist / radius, 0.0, 1.0)  # 1 in the center, soft toward the circle's edge
            weight = (falloff * blend_strength * surface_mask)[..., None]

            blended = region * (1 - weight) + averages[by, bx] * weight
            if renormalize:
                blended = renormalize_pixels(blended)

            out[y0:y1, x0:x1] = np.where(surface_mask[..., None], blended, region)

    return out


def interpolate_hsv(rgb_a, rgb_b, t):
    """Blend two colors in hue/saturation/value space, t=0 is pure a, t=1 is pure b."""
    ra, ga, ba = np.clip(rgb_a, 0, 255) / 255.0
    rb, gb, bb = np.clip(rgb_b, 0, 255) / 255.0
    ha, sa, va = colorsys.rgb_to_hsv(ra, ga, ba)
    hb, sb, vb = colorsys.rgb_to_hsv(rb, gb, bb)

    dh = hb - ha  # shortest path around the hue wheel, not always straight from ha to hb
    if dh > 0.5:
        dh -= 1.0
    elif dh < -0.5:
        dh += 1.0

    h = (ha + dh * t) % 1.0
    s = sa + (sb - sa) * t
    v = va + (vb - va) * t
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return np.array([r, g, b]) * 255.0


def paint_circle(out, source, cx, cy, radius, color, blend_strength, black_threshold, renormalize):
    h, w, _ = source.shape
    x0, x1 = max(0, int(cx - radius)), min(w, int(cx + radius) + 1)
    y0, y1 = max(0, int(cy - radius)), min(h, int(cy + radius) + 1)
    if x0 >= x1 or y0 >= y1:
        return

    region = source[y0:y1, x0:x1]
    surface_mask = region.sum(axis=-1) > black_threshold
    if not surface_mask.any():
        return

    yy, xx = np.mgrid[y0:y1, x0:x1]
    dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    falloff = np.clip(1.0 - dist / radius, 0.0, 1.0)
    weight = (falloff * blend_strength * surface_mask)[..., None]

    blended = region * (1 - weight) + np.asarray(color) * weight
    if renormalize:
        blended = renormalize_pixels(blended)

    out[y0:y1, x0:x1] = np.where(surface_mask[..., None], blended, out[y0:y1, x0:x1])


def paint_edge_gradient_cascade(arr, averages, has_surface, block_size, blocks_h, blocks_w, circle_ratio, blend_strength, black_threshold, renormalize):
    """Steps for edge_gradient_cascade: 3 circles per block (left/center/right edge

    midpoints), the shared boundary between two blocks blended 50/50 in HSV,
    cascading left to right across each row.
    """
    h, w, _ = arr.shape
    out = arr.copy()
    radius = (block_size / 4.0) * circle_ratio  # circles are spaced at half-block intervals now, not one per block

    for by in range(blocks_h):
        left_color = None  # color inherited at this block's left edge; None = "use this block's own average"

        for bx in range(blocks_w):
            if not has_surface[by, bx]:
                left_color = None  # broken by empty padding -- the next real block starts fresh
                continue

            y0, y1 = by * block_size, min((by + 1) * block_size, h)
            x0, x1 = bx * block_size, min((bx + 1) * block_size, w)
            cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
            own_avg = averages[by, bx]

            if left_color is None:
                left_color = own_avg  # first block in the row, or previous block was padding

            if bx + 1 < blocks_w and has_surface[by, bx + 1]:
                right_color = interpolate_hsv(own_avg, averages[by, bx + 1], 0.5)
            else:
                right_color = own_avg  # last block in the row -- nothing to blend toward

            paint_circle(out, arr, x0, cy, radius, left_color, blend_strength, black_threshold, renormalize)
            paint_circle(out, arr, cx, cy, radius, own_avg, blend_strength, black_threshold, renormalize)
            paint_circle(out, arr, x1, cy, radius, right_color, blend_strength, black_threshold, renormalize)

            left_color = right_color  # this block's right edge is the next block's left edge

    return out


def generate_voronoi_seeds(h, w, avg_cell_size, size_variance, elongation_max):
    """Scatter random seed points, one per cell. Each seed also gets a size

    weight (>1 grows its cell, <1 shrinks it) and its own random stretch
    angle + elongation factor, which is what gives cells a "flow" direction
    instead of being perfectly circular.
    """
    area = h * w
    num_seeds = max(4, int(round(area / (avg_cell_size ** 2))))

    positions = np.stack([
        np.random.uniform(0, w, num_seeds),
        np.random.uniform(0, h, num_seeds),
    ], axis=1)

    weights = 1.0 + np.random.uniform(-size_variance, size_variance, num_seeds)
    weights = np.clip(weights, 0.2, None)

    angles = np.random.uniform(0, np.pi, num_seeds)
    elongations = np.random.uniform(1.0, max(1.0, elongation_max), num_seeds)

    return positions, weights, angles, elongations


def weighted_aniso_distance(px, py, positions, weights, angles, elongations, candidate_idx):
    """px, py: (N,) pixel coords. candidate_idx: (N, k) seed indices to score.

    Returns (N, k) "effective" distances -- smaller for seeds that are
    closer, have a bigger weight, or where the pixel falls along that
    seed's stretch direction.
    """
    cand_pos = positions[candidate_idx]
    cand_w = weights[candidate_idx]
    cand_angle = angles[candidate_idx]
    cand_elong = elongations[candidate_idx]

    dx = px[:, None] - cand_pos[..., 0]
    dy = py[:, None] - cand_pos[..., 1]

    cos_a = np.cos(cand_angle)
    sin_a = np.sin(cand_angle)
    d_along = (dx * cos_a + dy * sin_a) / cand_elong
    d_perp = -dx * sin_a + dy * cos_a

    return np.sqrt(d_along ** 2 + d_perp ** 2) / cand_w


def assign_voronoi_cells(h, w, positions, weights, angles, elongations, candidates):
    """For every pixel: find its nearest cell and second-nearest cell (by

    weighted/stretched distance), used later for both the fill color and
    the soft seam between cells.
    """
    yy, xx = np.mgrid[0:h, 0:w]
    px = xx.ravel().astype(np.float64)
    py = yy.ravel().astype(np.float64)

    tree = cKDTree(positions)
    k = min(candidates, len(positions))
    _, idx = tree.query(np.stack([px, py], axis=1), k=k)
    if k == 1:
        idx = idx[:, None]

    dist = weighted_aniso_distance(px, py, positions, weights, angles, elongations, idx)
    order = np.argsort(dist, axis=1)
    sorted_idx = np.take_along_axis(idx, order, axis=1)
    sorted_dist = np.take_along_axis(dist, order, axis=1)

    nearest_cell = sorted_idx[:, 0].reshape(h, w)
    nearest_dist = sorted_dist[:, 0].reshape(h, w)
    second_cell = (sorted_idx[:, 1] if k > 1 else sorted_idx[:, 0]).reshape(h, w)
    second_dist = (sorted_dist[:, 1] if k > 1 else sorted_dist[:, 0]).reshape(h, w)

    return nearest_cell, nearest_dist, second_cell, second_dist


def compute_cell_averages(arr, nearest_cell, num_seeds, black_threshold):
    flat = arr.reshape(-1, 3)
    cell_flat = nearest_cell.ravel()
    mask = flat.sum(axis=-1) > black_threshold

    sums = np.zeros((num_seeds, 3), dtype=np.float64)
    counts = np.zeros(num_seeds, dtype=np.float64)
    np.add.at(sums, cell_flat[mask], flat[mask])
    np.add.at(counts, cell_flat[mask], 1)

    has_surface = counts > 0
    safe_counts = np.where(has_surface, counts, 1)
    averages = sums / safe_counts[:, None]
    return averages, has_surface


def differentiate_voronoi_neighbors(positions, averages, has_surface, similarity_threshold, hue_shift, shade_shift, k=4):
    """Same idea as differentiate_neighbors, but "adjacent" means "nearby seeds"

    instead of "next cell in a grid row/column."
    """
    num_seeds = len(positions)
    tree = cKDTree(positions)
    query_k = min(k + 1, num_seeds)  # +1 because a seed's own position is always its own nearest match
    _, idx = tree.query(positions, k=query_k)
    if query_k == 1:
        idx = idx[:, None]

    for i in range(num_seeds):
        if not has_surface[i]:
            continue
        for j in idx[i][1:]:
            if j <= i or not has_surface[j]:
                continue  # only look "forward" so each pair is only ever nudged once
            if np.linalg.norm(averages[i] - averages[j]) < similarity_threshold:
                averages[j] = tweak_color(averages[j], hue_shift, shade_shift)

    return averages


def paint_voronoi_cells(arr, averages, nearest_cell, nearest_dist, second_cell, second_dist, edge_softness, blend_strength, black_threshold, renormalize):
    surface_mask = arr.sum(axis=-1) > black_threshold

    cell1_color = averages[nearest_cell]
    cell2_color = averages[second_cell]

    # t=0 deep inside a cell (pure cell1), t=0.5 exactly on the boundary (50/50 blend)
    t = np.clip(1.0 - (second_dist - nearest_dist) / edge_softness, 0.0, 1.0) * 0.5
    target_color = cell1_color * (1 - t[..., None]) + cell2_color * t[..., None]

    weight = blend_strength * surface_mask[..., None]
    blended = arr * (1 - weight) + target_color * weight

    if renormalize:
        blended = renormalize_pixels(blended)

    return np.where(surface_mask[..., None], blended, arr)


def generate_stroke_seeds(h, w, avg_spacing, length_min, length_max, width_variance):
    """Scatter random line segments instead of points -- a segment's territory

    is a capsule (constant-width body + rounded caps), which reads as an
    actual stroke shape instead of a stretched blob.
    """
    area = h * w
    num_strokes = max(4, int(round(area / (avg_spacing ** 2))))

    starts = np.stack([
        np.random.uniform(0, w, num_strokes),
        np.random.uniform(0, h, num_strokes),
    ], axis=1)

    angles = np.random.uniform(0, 2 * np.pi, num_strokes)
    lengths = np.random.uniform(length_min, length_max, num_strokes)
    ends = starts + np.stack([np.cos(angles), np.sin(angles)], axis=1) * lengths[:, None]

    widths = 1.0 + np.random.uniform(-width_variance, width_variance, num_strokes)
    widths = np.clip(widths, 0.2, None)

    return starts, ends, widths


def build_stroke_candidate_tree(starts, ends, samples_per_stroke):
    """Sample several points along each stroke's length and index those --

    a plain KDTree on just the start (or midpoint) can miss the true
    nearest stroke for long segments; sampling along the whole length fixes
    that. Duplicate stroke ids among a pixel's candidates are harmless,
    just slightly redundant work.
    """
    ts = np.linspace(0.0, 1.0, samples_per_stroke)
    points = starts[:, None, :] * (1 - ts[None, :, None]) + ends[:, None, :] * ts[None, :, None]
    num_strokes = starts.shape[0]
    stroke_ids = np.repeat(np.arange(num_strokes), samples_per_stroke)
    tree = cKDTree(points.reshape(-1, 2))
    return tree, stroke_ids


def segment_distance(px, py, starts, ends, widths, candidate_idx):
    """px, py: (N,) pixel coords. candidate_idx: (N, k) stroke indices to score.

    True point-to-segment distance (clamped projection onto the segment),
    divided by the stroke's width so thicker strokes claim more territory.
    """
    a = starts[candidate_idx]  # (N, k, 2)
    b = ends[candidate_idx]    # (N, k, 2)
    w_ = widths[candidate_idx]  # (N, k)

    abx = b[..., 0] - a[..., 0]
    aby = b[..., 1] - a[..., 1]
    apx = px[:, None] - a[..., 0]
    apy = py[:, None] - a[..., 1]

    ab_len2 = abx ** 2 + aby ** 2
    ab_len2 = np.where(ab_len2 < 1e-9, 1e-9, ab_len2)
    t = np.clip((apx * abx + apy * aby) / ab_len2, 0.0, 1.0)

    closest_x = a[..., 0] + t * abx
    closest_y = a[..., 1] + t * aby

    dx = px[:, None] - closest_x
    dy = py[:, None] - closest_y
    return np.sqrt(dx ** 2 + dy ** 2) / w_


def assign_stroke_cells(h, w, starts, ends, widths, candidates, samples_per_stroke):
    yy, xx = np.mgrid[0:h, 0:w]
    px = xx.ravel().astype(np.float64)
    py = yy.ravel().astype(np.float64)

    tree, stroke_ids = build_stroke_candidate_tree(starts, ends, samples_per_stroke)
    k = min(candidates, len(stroke_ids))
    _, sample_idx = tree.query(np.stack([px, py], axis=1), k=k)
    if k == 1:
        sample_idx = sample_idx[:, None]
    candidate_idx = stroke_ids[sample_idx]  # (N, k) -- may contain duplicate stroke ids, that's fine

    dist = segment_distance(px, py, starts, ends, widths, candidate_idx)
    order = np.argsort(dist, axis=1)
    sorted_idx = np.take_along_axis(candidate_idx, order, axis=1)
    sorted_dist = np.take_along_axis(dist, order, axis=1)

    nearest_cell = sorted_idx[:, 0].reshape(h, w)
    nearest_dist = sorted_dist[:, 0].reshape(h, w)
    second_cell = (sorted_idx[:, 1] if k > 1 else sorted_idx[:, 0]).reshape(h, w)
    second_dist = (sorted_dist[:, 1] if k > 1 else sorted_dist[:, 0]).reshape(h, w)

    return nearest_cell, nearest_dist, second_cell, second_dist


def process_image(arr, block_size):
    if ALGORITHM in ("center_average_normalization", "edge_gradient_cascade"):
        averages, has_surface, blocks_h, blocks_w = compute_block_averages(arr, block_size, BLACK_THRESHOLD)
        averages = differentiate_neighbors(averages, has_surface, blocks_h, blocks_w, SIMILARITY_THRESHOLD, HUE_TWEAK, SHADE_TWEAK)

        if ALGORITHM == "center_average_normalization":
            return paint_blocks(arr, averages, has_surface, block_size, blocks_h, blocks_w, CIRCLE_RATIO, BLEND_STRENGTH, BLACK_THRESHOLD, RENORMALIZE)
        else:
            return paint_edge_gradient_cascade(arr, averages, has_surface, block_size, blocks_h, blocks_w, CIRCLE_RATIO, BLEND_STRENGTH, BLACK_THRESHOLD, RENORMALIZE)

    elif ALGORITHM == "voronoi_flow_cells":
        h, w, _ = arr.shape
        positions, weights, angles, elongations = generate_voronoi_seeds(h, w, VORONOI_AVG_CELL_SIZE, VORONOI_SIZE_VARIANCE, VORONOI_ELONGATION_MAX)
        nearest_cell, nearest_dist, second_cell, second_dist = assign_voronoi_cells(h, w, positions, weights, angles, elongations, VORONOI_CANDIDATES)
        averages, has_surface = compute_cell_averages(arr, nearest_cell, len(positions), BLACK_THRESHOLD)
        averages = differentiate_voronoi_neighbors(positions, averages, has_surface, SIMILARITY_THRESHOLD, HUE_TWEAK, SHADE_TWEAK)
        return paint_voronoi_cells(arr, averages, nearest_cell, nearest_dist, second_cell, second_dist, VORONOI_EDGE_SOFTNESS, BLEND_STRENGTH, BLACK_THRESHOLD, RENORMALIZE)

    elif ALGORITHM == "brush_stroke_cells":
        h, w, _ = arr.shape
        starts, ends, widths = generate_stroke_seeds(h, w, STROKE_AVG_SPACING, STROKE_LENGTH_MIN, STROKE_LENGTH_MAX, STROKE_WIDTH_VARIANCE)
        nearest_cell, nearest_dist, second_cell, second_dist = assign_stroke_cells(h, w, starts, ends, widths, STROKE_CANDIDATES, STROKE_SAMPLES_PER_STROKE)
        averages, has_surface = compute_cell_averages(arr, nearest_cell, len(starts), BLACK_THRESHOLD)
        midpoints = (starts + ends) / 2.0
        averages = differentiate_voronoi_neighbors(midpoints, averages, has_surface, SIMILARITY_THRESHOLD, HUE_TWEAK, SHADE_TWEAK)
        return paint_voronoi_cells(arr, averages, nearest_cell, nearest_dist, second_cell, second_dist, STROKE_EDGE_SOFTNESS, BLEND_STRENGTH, BLACK_THRESHOLD, RENORMALIZE)

    else:
        raise ValueError(f"Unknown ALGORITHM: {ALGORITHM!r}")


def main():
    valid_algorithms = ("center_average_normalization", "edge_gradient_cascade", "voronoi_flow_cells", "brush_stroke_cells")
    if ALGORITHM not in valid_algorithms:
        raise ValueError(f"Unknown ALGORITHM: {ALGORITHM!r} -- must be one of {valid_algorithms}")

    block_size = None
    if ALGORITHM in ("center_average_normalization", "edge_gradient_cascade"):
        block_size = validated_block_size(BLOCK_WIDTH, BLOCK_HEIGHT, BLOCK_SIZE_MIN, BLOCK_SIZE_MAX)

    if RANDOM_SEED is not None:
        random.seed(RANDOM_SEED)
        np.random.seed(RANDOM_SEED)

    EXPORT_DIR.mkdir(exist_ok=True)

    queued = sorted(IMPORT_DIR.glob("*.png"))
    if not queued:
        print(f"Nothing to process in {IMPORT_DIR}")
        return

    for src in queued:
        dest = EXPORT_DIR / f"{src.stem}_processed.png"
        try:
            arr = load_normal_image(src)
            h, w, _ = arr.shape
            if block_size is not None and block_size > min(h, w):
                raise ValueError(f"Block size {block_size} is larger than this image ({w}x{h})")
            arr = process_image(arr, block_size)
            save_normal_image(arr, dest)
        except Exception as e:
            print(f"Skipped {src.name}: {e}")
            continue

        src.unlink()  # only remove the original once the export actually succeeded
        label = f"{block_size}px blocks" if block_size is not None else ALGORITHM
        print(f"{src.name} -> export/{dest.name} ({label})")


if __name__ == "__main__":
    main()
