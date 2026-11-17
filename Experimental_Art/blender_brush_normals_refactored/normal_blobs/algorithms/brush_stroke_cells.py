"""Irregular cells claimed by configurable procedural brush strokes."""

from __future__ import annotations

from argparse import ArgumentParser, Namespace
from dataclasses import dataclass
import os

import numpy as np
from scipy.spatial import cKDTree

from normal_blobs.algorithms.cell_common import (
    ISOLATED_KEY_SCRATCH_BYTES,
    compute_cell_averages,
    differentiate_isolated_neighbors,
    isolate_cells_across_padding,
    keep_second_cells_inside_islands,
    paint_cells,
)
from normal_blobs.models import (
    CommonOptions,
    ImageArray,
    RandomStreams,
    ResourceEstimate,
)
from normal_blobs.resources import MIB
from normal_blobs.validation import (
    float_in_range,
    integer_in_range,
)

NAME = "brush_stroke_cells"
SUMMARY = "Algorithm 4: configurable organic, mineral, and panel brush cells."
DESCRIPTION = """
Algorithm 4 scatters strokes or panel centers and lets their distance fields
claim irregular cells. It provides 32 brush shapes organized into legacy,
foliage, animal, insect, natural-material, mineral, manufactured, and panel
families while retaining the legacy capsule output as its default.

Use it for the widest artistic control. Density, shape size, direction,
variation, curvature, segmentation, roughness, overlap, and edge softness can
be combined within documented safety limits. Processing is chunked, uses at
most eight workers, and preserves black padding and disconnected UV islands.
""".strip()
HELP_EPILOG = """
Examples:
  py procedural_normal_blobs.py brush_stroke_cells --seed 42
  py procedural_normal_blobs.py brush_stroke_cells --brush-shape leaf --density 0.34 --shape-size 0.52 --seed 42
  py procedural_normal_blobs.py brush_stroke_cells --brush-shape grass-clump --density 0.58 --curvature 0.7 --segments 6 --seed 42
  py procedural_normal_blobs.py brush_stroke_cells --brush-shape beetle-shell --density 0.36 --shape-size 0.48 --symmetry 0.9 --seed 42
  py procedural_normal_blobs.py brush_stroke_cells --brush-shape hexagon --density 0.48 --hex-jitter 0.03 --seed 42

Start with:
  --brush-shape chooses the visual family.
  --density controls how many cells are generated.
  --shape-size controls stroke length or panel diameter.
  --flow-angle and --flow-jitter control direction.

See README.md for the complete shape catalog and artistic recipes.
""".strip()

BRUSH_SHAPE_CATEGORIES = {
    "Legacy": ("capsule", "swirl", "sharp-start", "sharp-end", "sharp-both"),
    "Foliage": (
        "grass-blade", "grass-clump", "leaf", "branching-twig",
    ),
    "Animal": ("feather", "fur-tuft", "fish-scale"),
    "Insect": ("beetle-shell", "insect-wing"),
    "Organic": (
        "scale", "petal", "pine-needle", "scallop", "vine", "bark",
        "moss-patch", "tentacle",
    ),
    "Natural material": ("pebble", "boulder", "crack"),
    "Mineral": ("crystal", "shard"),
    "Manufactured": ("chevron", "circuit-trace"),
    "Panel": ("diamond-panel", "octagon-panel", "hexagon"),
}
BRUSH_SHAPES = tuple(
    shape for category in BRUSH_SHAPE_CATEGORIES.values() for shape in category
)
BRUSH_SHAPE_DESCRIPTIONS = {
    "capsule": "rounded equal-width stroke",
    "swirl": "curved sweeping stroke",
    "sharp-start": "pointed start with rounded end",
    "sharp-end": "rounded start with pointed end",
    "sharp-both": "pointed lens or diamond",
    "grass-blade": "tapered blade with a natural bend",
    "grass-clump": "clustered lobed grass blade",
    "leaf": "smooth symmetrical plant leaf",
    "branching-twig": "branch-like jagged twig or root",
    "feather": "barbed feather vane",
    "fur-tuft": "short pointed fur or hair tuft",
    "fish-scale": "overlapping shield-shaped scale",
    "insect-wing": "veined tapered wing",
    "beetle-shell": "rounded domed beetle or shell plate",
    "moss-patch": "rough clustered moss island",
    "tentacle": "curving tapered tentacle or tendril",
    "scale": "teardrop scale",
    "petal": "asymmetrical flower petal",
    "pine-needle": "narrow tapered needle or fiber",
    "scallop": "lobed shell or decorative edge",
    "vine": "narrow S-curved vine",
    "bark": "vertical lobed bark band",
    "pebble": "smooth oval stone or seed",
    "boulder": "rough rounded rock",
    "crack": "narrow jagged fracture",
    "crystal": "faceted pointed crystal",
    "shard": "splintered mineral shard",
    "chevron": "bent V-shaped manufactured stroke",
    "circuit-trace": "narrow technological conduit",
    "diamond-panel": "rotated diamond plate",
    "octagon-panel": "regular octagonal plate",
    "hexagon": "regular hexagonal plate",
}
BRUSH_SHAPE_CATEGORY_HELP = "; ".join(
    f"{category}: {', '.join(shapes)}"
    for category, shapes in BRUSH_SHAPE_CATEGORIES.items()
)
OVERLAP_ORDERS = ("balanced", "earlier", "later", "larger", "smaller")
HEX_LAYOUTS = ("honeycomb", "scattered")
CENTERED_PANEL_SHAPES = frozenset(
    ("hexagon", "diamond-panel", "octagon-panel")
)
DEFORMED_PATH_SHAPES = frozenset(
    (
        "swirl", "vine", "crack", "chevron", "circuit-trace",
        "grass-blade", "grass-clump", "branching-twig",
        "feather", "fur-tuft", "fish-scale", "insect-wing", "beetle-shell",
        "moss-patch", "tentacle",
    )
)
MINIMUM_PATH_SAMPLES = {
    "swirl": 3,
    "vine": 5,
    "crack": 5,
    "chevron": 3,
    "circuit-trace": 5,
    "grass-blade": 3,
    "grass-clump": 5,
    "branching-twig": 5,
    "feather": 5,
    "fur-tuft": 3,
    "fish-scale": 3,
    "insect-wing": 5,
    "beetle-shell": 5,
    "moss-patch": 5,
    "tentacle": 5,
}
DEFAULT_FLOW_ANGLES = {
    "scale": -90.0,
    "scallop": -90.0,
    "bark": 90.0,
    "chevron": 0.0,
    "circuit-trace": 0.0,
    "diamond-panel": 0.0,
    "octagon-panel": 0.0,
    "grass-blade": -90.0,
    "grass-clump": -90.0,
    "fern-frond": -70.0,
    "branching-twig": 90.0,
    "fish-scale": -90.0,
    "insect-wing": 25.0,
    "beetle-shell": 0.0,
}

MIN_AVERAGE_SPACING = 64.0
MAX_PIXEL_CONTROL = 4096.0
MAX_STROKES = 4096
MAX_CANDIDATES = 64
MAX_SAMPLES_PER_STROKE = 32
MAX_CHUNK_ROWS = 128
MAX_WORKERS = 8
DEFAULT_AVERAGE_SPACING = 130.0
DEFAULT_LENGTH_MIN = 60.0
DEFAULT_LENGTH_MAX = 260.0
DEFAULT_LENGTH_VARIATION = 0.35
DEFAULT_SWIRL_STRENGTH = 0.55
DEFAULT_FLOW_JITTER = 0.25
DEFAULT_CURVATURE = 0.35
DEFAULT_SEGMENTS = 4
DEFAULT_ROUGHNESS = 0.25
DEFAULT_SYMMETRY = 0.75
DEFAULT_BRANCHING = 0.35
MIN_SEGMENTS = 2
MAX_SEGMENTS = 16


def effective_segments(segments: int, sample_count: int) -> int:
    """Limit curve frequency to the number of available polyline intervals."""

    return min(segments, max(1, sample_count - 1))


def requested_candidate_count(
    candidates: int,
    samples_per_stroke: int,
    edge_selection: str,
    has_overlap_priority: bool,
    brush_shape: str = "capsule",
) -> int:
    """Return the sample search width before the tree-size cap is applied."""

    if brush_shape in CENTERED_PANEL_SHAPES:
        # Panels index one center per cell, so candidates are already distinct
        # and do not need extra centerline samples.
        count = candidates
    elif edge_selection == "legacy":
        count = candidates
    elif edge_selection == "distinct":
        count = max(candidates, samples_per_stroke + 1)
    else:
        raise ValueError(f"Unknown edge selection: {edge_selection!r}")
    if has_overlap_priority:
        count *= 2
    return count


@dataclass(frozen=True)
class SizeProfile:
    """Safe normalized-control limits for one square texture size."""

    minimum_cells: int
    maximum_cells: int
    minimum_length: float
    maximum_length: float
    maximum_priority_bias: float


SIZE_PROFILES = {
    1024: SizeProfile(16, 256, 24.0, 160.0, 0.15),
    2048: SizeProfile(64, 1024, 48.0, 320.0, 0.20),
    4096: SizeProfile(256, 4096, 96.0, 640.0, 0.25),
}


@dataclass(frozen=True)
class Config:
    average_spacing: float
    length_min: float
    length_max: float
    width_variance: float
    edge_softness: float
    candidates: int
    samples_per_stroke: int
    edge_selection: str = "legacy"
    chunk_rows: int = 64
    brush_shape: str = "capsule"
    density: float | None = None
    shape_size: float | None = None
    length_variation: float = 0.35
    swirl_strength: float = 0.55
    overlap_order: str = "balanced"
    overlap_priority: float = 0.0
    flow_angle: float | None = None
    flow_jitter: float = 0.25
    workers: int = 0
    hex_layout: str = "honeycomb"
    hex_jitter: float = 0.0
    curvature: float = DEFAULT_CURVATURE
    segments: int = DEFAULT_SEGMENTS
    roughness: float = DEFAULT_ROUGHNESS
    symmetry: float = DEFAULT_SYMMETRY
    branching: float = DEFAULT_BRANCHING


def estimate_resources(
    height: int, width: int, config: Config
) -> ResourceEstimate:
    """Estimate persistent maps and worst-case path-distance scratch arrays."""

    pixels = height * width
    chunk_pixels = min(config.chunk_rows, height) * width
    candidate_count = requested_candidate_count(
        config.candidates,
        config.samples_per_stroke,
        config.edge_selection,
        (
            config.overlap_order != "balanced"
            and config.overlap_priority > 0
        ),
        config.brush_shape,
    )
    persistent = pixels * 96
    scratch = chunk_pixels * candidate_count * 192
    worker_count = (
        min(os.cpu_count() or 1, MAX_WORKERS)
        if config.workers == 0
        else config.workers
    )
    worker_scratch = (
        chunk_pixels
        * candidate_count
        * 8
        * max(0, worker_count - 1)
    )
    cpu_bytes = int(
        (
            persistent
            + scratch
            + worker_scratch
            + ISOLATED_KEY_SCRATCH_BYTES
            + 64 * MIB
        )
        * 1.25
    )
    return ResourceEstimate(cpu_bytes=cpu_bytes)


def add_arguments(parser: ArgumentParser) -> None:
    shape = parser.add_argument_group("brush shape")
    shape.add_argument(
        "--brush-shape",
        choices=BRUSH_SHAPES,
        default="capsule",
        help=(
            "Cell geometry preset (default: capsule). Categories: "
            + BRUSH_SHAPE_CATEGORY_HELP
        ),
    )
    shape.add_argument(
        "--density",
        type=float_in_range(0.0, 1.0),
        metavar="RATIO",
        help=(
            "Resolution-aware stroke density from 0 (least) to 1 (most). "
            "Unset preserves --average-spacing."
        ),
    )
    shape.add_argument(
        "--shape-size",
        type=float_in_range(0.0, 1.0),
        metavar="RATIO",
        help=(
            "Resolution-aware stroke length or panel diameter from "
            "0 (smallest) to 1 (largest). Unset preserves legacy controls."
        ),
    )
    organic = parser.add_argument_group("organic shape controls")
    organic.add_argument(
        "--curvature",
        type=float_in_range(0.0, 1.0),
        metavar="RATIO",
        help=(
            "Bend amount for foliage, wings, shells, twigs, and tentacles: "
            "0 is straight and 1 is strongly curved (default: 0.35). "
            "Legacy and centered panel shapes keep their established geometry."
        ),
    )
    organic.add_argument(
        "--segments",
        type=integer_in_range(MIN_SEGMENTS, MAX_SEGMENTS),
        metavar="COUNT",
        help=(
            "Lobes, barbs, or centerline turns used by organic shapes from "
            f"{MIN_SEGMENTS} to {MAX_SEGMENTS} (default: {DEFAULT_SEGMENTS}); "
            "the effective count is capped by available path samples."
        ),
    )
    organic.add_argument(
        "--roughness",
        type=float_in_range(0.0, 1.0),
        metavar="RATIO",
        help=(
            "Deterministic edge and centerline irregularity from smooth 0 "
            "to rough 1 (default: 0.25); strongest on new organic shapes."
        ),
    )
    organic.add_argument(
        "--symmetry",
        type=float_in_range(0.0, 1.0),
        metavar="RATIO",
        help=(
            "Profile symmetry from asymmetric 0 to mirrored 1; useful for "
            "wings, scales, shells, and new organic shapes (default: 0.75)."
        ),
    )
    organic.add_argument(
        "--branching",
        type=float_in_range(0.0, 1.0),
        metavar="RATIO",
        help=(
            "Branch or tuft influence from 0 to 1; strongest on grass-clump, "
            "branch-like twig, moss-patch, and fur-tuft (default: 0.35)."
        ),
    )
    shape.add_argument(
        "--hex-layout",
        choices=HEX_LAYOUTS,
        help=(
            "Hexagon center layout: honeycomb for ordered metal panels or "
            "scattered for irregular panels (default: honeycomb)."
        ),
    )
    shape.add_argument(
        "--hex-jitter",
        type=float_in_range(0.0, 1.0),
        metavar="RATIO",
        help=(
            "Bounded honeycomb center variation from 0 (uniform) to 1 "
            "(30%% of panel spacing; default: 0)."
        ),
    )
    shape.add_argument(
        "--length-variation",
        type=float_in_range(0.0, 0.75),
        metavar="RATIO",
        help=(
            "Length variation around --shape-size from 0 to 0.75 "
            "(default: 0 for centered panels, 0.35 for other shapes)."
        ),
    )
    shape.add_argument(
        "--swirl-strength",
        type=float_in_range(0.0, 1.0),
        metavar="RATIO",
        help="Curvature of swirl strokes from 0 to 1 (default: 0.55).",
    )
    shape.add_argument(
        "--flow-angle",
        type=float_in_range(-360.0, 360.0),
        metavar="DEGREES",
        help=(
            "Preferred stroke direction in degrees; unset is random. "
            "Directional presets and manufactured panels supply an "
            "art-friendly default."
        ),
    )
    shape.add_argument(
        "--flow-jitter",
        type=float_in_range(0.0, 1.0),
        metavar="RATIO",
        help=(
            "Angular spread around flow direction: 0 aligned, 1 fully "
            "random (default: 0 for centered panels, 0.25 otherwise)."
        ),
    )
    shape.add_argument(
        "--overlap-order",
        choices=OVERLAP_ORDERS,
        help=(
            "Bias which nearby candidate strokes win contested pixels: "
            "balanced, earlier, later, larger, or smaller "
            "(default: balanced)."
        ),
    )
    shape.add_argument(
        "--overlap-priority",
        type=float_in_range(0.0, 1.0),
        metavar="RATIO",
        help=(
            "Strength of --overlap-order from 0 (none) to 1 (safe maximum; "
            "default: 0)."
        ),
    )

    legacy = parser.add_argument_group("legacy pixel controls")
    legacy.add_argument(
        "--average-spacing",
        type=float_in_range(MIN_AVERAGE_SPACING, MAX_PIXEL_CONTROL),
        metavar="PIXELS",
        help=(
            "Target average spacing between strokes from 64 to 4096 "
            "(default: 130)."
        ),
    )
    legacy.add_argument(
        "--length-min",
        type=float_in_range(1.0, MAX_PIXEL_CONTROL),
        metavar="PIXELS",
        help="Shortest generated stroke from 1 to 4096 (default: 60).",
    )
    legacy.add_argument(
        "--length-max",
        type=float_in_range(1.0, MAX_PIXEL_CONTROL),
        metavar="PIXELS",
        help="Longest generated stroke from 1 to 4096 (default: 260).",
    )
    legacy.add_argument(
        "--width-variance",
        type=float_in_range(0.0, 1.0),
        metavar="RATIO",
        help=(
            "Random width variation from 0 to 1. Defaults to 0 for "
            "centered panels and 0.5 for other shapes."
        ),
    )
    parser.add_argument(
        "--edge-softness",
        type=float_in_range(0.01, MAX_PIXEL_CONTROL),
        default=8.0,
        metavar="PIXELS",
        help=(
            "Width of the soft blend between stroke cells from 0.01 to "
            "4096 (default: 8)."
        ),
    )
    parser.add_argument(
        "--candidates",
        type=integer_in_range(2, MAX_CANDIDATES),
        default=18,
        metavar="COUNT",
        help="Nearby sampled points scored per pixel from 2 to 64 (default: 18).",
    )
    parser.add_argument(
        "--samples-per-stroke",
        type=integer_in_range(2, MAX_SAMPLES_PER_STROKE),
        metavar="COUNT",
        help=(
            "Index samples distributed along each stroke from 2 to 32; "
            "deformed paths require 3 or 5 depending on shape. Centered "
            "panels do not use this option (default: 5)."
        ),
    )
    parser.add_argument(
        "--edge-selection",
        choices=("legacy", "distinct"),
        help=(
            "Legacy preserves current hard-cell behavior; distinct blends "
            "against the nearest different stroke. Capsule defaults to "
            "legacy; other shapes default to distinct."
        ),
    )
    parser.add_argument(
        "--chunk-rows",
        type=integer_in_range(1, MAX_CHUNK_ROWS),
        default=64,
        metavar="ROWS",
        help=(
            "Pixel rows processed per memory-bounded chunk; lower values use "
            "less memory; range 1 to 128 (default: 64)."
        ),
    )
    parser.add_argument(
        "--workers",
        type=integer_in_range(0, MAX_WORKERS),
        default=0,
        metavar="COUNT",
        help=(
            "CPU workers used by the expensive spatial lookup: 0 uses all "
            "available logical CPUs up to 8, 1 is single-threaded, and 2-8 "
            "selects an explicit limit (default: 0)."
        ),
    )


def make_config(args: Namespace) -> Config:
    average_spacing = (
        DEFAULT_AVERAGE_SPACING
        if args.average_spacing is None
        else args.average_spacing
    )
    length_min = (
        DEFAULT_LENGTH_MIN if args.length_min is None else args.length_min
    )
    length_max = (
        DEFAULT_LENGTH_MAX if args.length_max is None else args.length_max
    )
    length_variation = (
        (
            0.0
            if args.brush_shape in CENTERED_PANEL_SHAPES
            else DEFAULT_LENGTH_VARIATION
        )
        if args.length_variation is None
        else args.length_variation
    )
    swirl_strength = (
        DEFAULT_SWIRL_STRENGTH
        if args.swirl_strength is None
        else args.swirl_strength
    )
    flow_jitter = (
        (
            0.0
            if args.brush_shape in CENTERED_PANEL_SHAPES
            else DEFAULT_FLOW_JITTER
        )
        if args.flow_jitter is None
        else args.flow_jitter
    )
    curvature = (
        DEFAULT_CURVATURE if args.curvature is None else args.curvature
    )
    segments = DEFAULT_SEGMENTS if args.segments is None else args.segments
    roughness = (
        DEFAULT_ROUGHNESS if args.roughness is None else args.roughness
    )
    symmetry = DEFAULT_SYMMETRY if args.symmetry is None else args.symmetry
    branching = (
        DEFAULT_BRANCHING if args.branching is None else args.branching
    )
    samples_per_stroke = (
        5 if args.samples_per_stroke is None else args.samples_per_stroke
    )
    width_variance = (
        0.0
        if (
            args.width_variance is None
            and args.brush_shape in CENTERED_PANEL_SHAPES
        )
        else (
            0.5
            if args.width_variance is None
            else args.width_variance
        )
    )
    hex_layout = args.hex_layout or "honeycomb"
    hex_jitter = 0.0 if args.hex_jitter is None else args.hex_jitter
    if (
        args.brush_shape in CENTERED_PANEL_SHAPES
        and args.shape_size is None
        and args.length_min is None
        and args.length_max is None
    ):
        # Uniform point-to-point diameter by default. Explicit legacy length
        # controls or normalized shape size can intentionally vary panels.
        length_min = average_spacing
        length_max = average_spacing
    overlap_order = args.overlap_order or "balanced"
    overlap_priority = args.overlap_priority or 0.0
    edge_selection = args.edge_selection
    if edge_selection is None:
        edge_selection = (
            "legacy" if args.brush_shape == "capsule" else "distinct"
        )

    if args.density is not None and args.average_spacing is not None:
        raise ValueError(
            "--density and --average-spacing are alternative controls; "
            "choose one"
        )
    if args.shape_size is not None and (
        args.length_min is not None or args.length_max is not None
    ):
        raise ValueError(
            "--shape-size cannot be combined with --length-min or "
            "--length-max"
        )
    if (
        args.brush_shape == "hexagon"
        and hex_layout == "honeycomb"
        and args.shape_size is not None
        and (
            args.density is not None
            or args.average_spacing is not None
        )
    ):
        raise ValueError(
            "honeycomb --shape-size, --density, and --average-spacing "
            "control the same panel scale; choose one"
        )
    if args.length_variation is not None and args.shape_size is None:
        raise ValueError("--length-variation requires --shape-size")
    if args.swirl_strength is not None and args.brush_shape != "swirl":
        raise ValueError("--swirl-strength requires --brush-shape swirl")
    if (
        args.brush_shape in CENTERED_PANEL_SHAPES
        and args.samples_per_stroke is not None
    ):
        raise ValueError(
            "--samples-per-stroke does not apply to centered panel shapes"
        )
    if args.brush_shape != "hexagon" and args.hex_layout is not None:
        raise ValueError("--hex-layout requires --brush-shape hexagon")
    if args.brush_shape != "hexagon" and args.hex_jitter is not None:
        raise ValueError("--hex-jitter requires --brush-shape hexagon")
    if hex_layout == "scattered" and hex_jitter > 0:
        raise ValueError(
            "--hex-jitter applies only to --hex-layout honeycomb"
        )
    if (
        args.flow_jitter is not None
        and args.flow_angle is None
        and args.brush_shape not in DEFAULT_FLOW_ANGLES
        and not (
            args.brush_shape == "hexagon"
            and hex_layout == "honeycomb"
        )
    ):
        raise ValueError(
            "--flow-jitter requires --flow-angle unless the selected shape "
            "supplies a default flow angle"
        )
    if overlap_order == "balanced" and overlap_priority > 0:
        raise ValueError(
            "--overlap-priority has no effect with --overlap-order balanced"
        )
    if overlap_order != "balanced" and overlap_priority == 0:
        raise ValueError(
            f"--overlap-order {overlap_order} requires a positive "
            "--overlap-priority"
        )
    if (
        overlap_priority > 0
        and overlap_order in ("larger", "smaller")
        and (
            (args.shape_size is not None and length_variation == 0)
            or (args.shape_size is None and length_min == length_max)
        )
    ):
        raise ValueError(
            f"--overlap-order {overlap_order} requires varying stroke "
            "lengths; increase --length-variation or use different "
            "--length-min/--length-max values"
        )
    if length_max < length_min:
        raise ValueError("--length-max must be greater than or equal to --length-min")
    minimum_samples = MINIMUM_PATH_SAMPLES.get(args.brush_shape, 2)
    if samples_per_stroke < minimum_samples:
        raise ValueError(
            f"--brush-shape {args.brush_shape} requires "
            f"--samples-per-stroke {minimum_samples} or more"
        )
    return Config(
        average_spacing=average_spacing,
        length_min=length_min,
        length_max=length_max,
        width_variance=width_variance,
        edge_softness=args.edge_softness,
        candidates=args.candidates,
        samples_per_stroke=samples_per_stroke,
        edge_selection=edge_selection,
        chunk_rows=args.chunk_rows,
        brush_shape=args.brush_shape,
        density=args.density,
        shape_size=args.shape_size,
        length_variation=length_variation,
        swirl_strength=swirl_strength,
        overlap_order=overlap_order,
        overlap_priority=overlap_priority,
        flow_angle=args.flow_angle,
        flow_jitter=flow_jitter,
        workers=args.workers,
        hex_layout=hex_layout,
        hex_jitter=hex_jitter,
        curvature=curvature,
        segments=segments,
        roughness=roughness,
        symmetry=symmetry,
        branching=branching,
    )


def resolve_workers(requested: int) -> int:
    """Resolve automatic worker selection to a bounded positive count."""

    if requested == 0:
        return min(os.cpu_count() or 1, MAX_WORKERS)
    return requested


def validate_workload(
    height: int,
    width: int,
    config: Config,
) -> None:
    """Reject unsafe programmatic configs before allocating large arrays."""

    finite_controls = {
        "average_spacing": config.average_spacing,
        "length_min": config.length_min,
        "length_max": config.length_max,
        "edge_softness": config.edge_softness,
        "width_variance": config.width_variance,
        "length_variation": config.length_variation,
        "swirl_strength": config.swirl_strength,
        "overlap_priority": config.overlap_priority,
        "flow_jitter": config.flow_jitter,
        "hex_jitter": config.hex_jitter,
        "curvature": config.curvature,
        "roughness": config.roughness,
        "symmetry": config.symmetry,
        "branching": config.branching,
    }
    if config.density is not None:
        finite_controls["density"] = config.density
    if config.shape_size is not None:
        finite_controls["shape_size"] = config.shape_size
    if config.flow_angle is not None:
        finite_controls["flow_angle"] = config.flow_angle
    invalid = [
        name for name, value in finite_controls.items() if not np.isfinite(value)
    ]
    if invalid:
        raise ValueError(
            "non-finite brush control(s): " + ", ".join(sorted(invalid))
        )
    if config.brush_shape not in BRUSH_SHAPES:
        raise ValueError(f"unknown brush_shape: {config.brush_shape!r}")
    if config.overlap_order not in OVERLAP_ORDERS:
        raise ValueError(f"unknown overlap_order: {config.overlap_order!r}")
    if config.hex_layout not in HEX_LAYOUTS:
        raise ValueError(f"unknown hex_layout: {config.hex_layout!r}")
    if config.brush_shape != "hexagon" and config.hex_layout != "honeycomb":
        raise ValueError("hex_layout applies only to hexagon")
    if config.edge_selection not in ("legacy", "distinct"):
        raise ValueError(f"unknown edge_selection: {config.edge_selection!r}")
    if config.average_spacing <= 0:
        raise ValueError("average_spacing must be greater than 0")
    if not 1.0 <= config.length_min <= MAX_PIXEL_CONTROL:
        raise ValueError("length_min must be between 1 and 4096")
    if not config.length_min <= config.length_max <= MAX_PIXEL_CONTROL:
        raise ValueError(
            "length_max must be between length_min and 4096"
        )
    if not 0.01 <= config.edge_softness <= MAX_PIXEL_CONTROL:
        raise ValueError("edge_softness must be between 0.01 and 4096")
    if not 0.0 <= config.width_variance <= 1.0:
        raise ValueError("width_variance must be between 0 and 1")
    if config.density is not None and not 0.0 <= config.density <= 1.0:
        raise ValueError("density must be between 0 and 1")
    if config.shape_size is not None and not 0.0 <= config.shape_size <= 1.0:
        raise ValueError("shape_size must be between 0 and 1")
    if not 0.0 <= config.length_variation <= 0.75:
        raise ValueError("length_variation must be between 0 and 0.75")
    if not 0.0 <= config.swirl_strength <= 1.0:
        raise ValueError("swirl_strength must be between 0 and 1")
    if not 0.0 <= config.overlap_priority <= 1.0:
        raise ValueError("overlap_priority must be between 0 and 1")
    if config.flow_angle is not None and not -360.0 <= config.flow_angle <= 360.0:
        raise ValueError("flow_angle must be between -360 and 360")
    if not 0.0 <= config.flow_jitter <= 1.0:
        raise ValueError("flow_jitter must be between 0 and 1")
    if not 0.0 <= config.hex_jitter <= 1.0:
        raise ValueError("hex_jitter must be between 0 and 1")
    if not 0.0 <= config.curvature <= 1.0:
        raise ValueError("curvature must be between 0 and 1")
    if not isinstance(config.segments, (int, np.integer)):
        raise ValueError("segments must be an integer")
    if not MIN_SEGMENTS <= config.segments <= MAX_SEGMENTS:
        raise ValueError(
            f"segments must be between {MIN_SEGMENTS} and {MAX_SEGMENTS}"
        )
    if not 0.0 <= config.roughness <= 1.0:
        raise ValueError("roughness must be between 0 and 1")
    if not 0.0 <= config.symmetry <= 1.0:
        raise ValueError("symmetry must be between 0 and 1")
    if not 0.0 <= config.branching <= 1.0:
        raise ValueError("branching must be between 0 and 1")
    if config.brush_shape != "hexagon" and config.hex_jitter > 0:
        raise ValueError("hex_jitter applies only to hexagon")
    if config.hex_layout == "scattered" and config.hex_jitter > 0:
        raise ValueError("hex_jitter applies only to honeycomb layout")
    if not 2 <= config.candidates <= MAX_CANDIDATES:
        raise ValueError("candidates must be between 2 and 64")
    if not 2 <= config.samples_per_stroke <= MAX_SAMPLES_PER_STROKE:
        raise ValueError("samples_per_stroke must be between 2 and 32")
    minimum_samples = MINIMUM_PATH_SAMPLES.get(config.brush_shape, 2)
    if config.samples_per_stroke < minimum_samples:
        raise ValueError(
            f"{config.brush_shape} requires at least {minimum_samples} "
            "samples_per_stroke"
        )
    if not 1 <= config.chunk_rows <= MAX_CHUNK_ROWS:
        raise ValueError("chunk_rows must be between 1 and 128")
    if not 0 <= config.workers <= MAX_WORKERS:
        raise ValueError("workers must be between 0 and 8")

    if config.density is None and not (
        config.brush_shape == "hexagon"
        and config.hex_layout == "honeycomb"
        and config.shape_size is not None
    ):
        estimated_strokes = height * width / config.average_spacing**2
        if estimated_strokes > MAX_STROKES + 0.5:
            minimum_spacing = np.sqrt(height * width / MAX_STROKES)
            raise ValueError(
                "average_spacing would generate more than "
                f"{MAX_STROKES} strokes for {width}x{height}; use "
                f"{minimum_spacing:.2f} or greater, or use --density"
            )


def size_profile(height: int, width: int) -> SizeProfile:
    """Return documented limits, with a proportional fallback for unit tests."""

    if height == width and width in SIZE_PROFILES:
        return SIZE_PROFILES[width]

    area_scale = height * width / float(1024**2)
    length_scale = min(height, width) / 1024.0
    minimum_cells = max(4, int(round(16 * area_scale)))
    maximum_cells = max(minimum_cells, int(round(256 * area_scale)))
    return SizeProfile(
        minimum_cells=minimum_cells,
        maximum_cells=maximum_cells,
        minimum_length=max(4.0, 24.0 * length_scale),
        maximum_length=max(4.0, 160.0 * length_scale),
        maximum_priority_bias=0.15,
    )


def hex_honeycomb_centers(
    height: int,
    width: int,
    target_count: int,
    jitter: float,
    rng: RandomStreams,
) -> tuple[np.ndarray, float]:
    """Build a bounded triangular lattice whose Voronoi cells are hexagonal."""

    area_per_center = height * width / float(max(target_count, 1))
    spacing = np.sqrt(area_per_center / (np.sqrt(3.0) / 2.0))

    def build(active_spacing: float) -> np.ndarray:
        row_spacing = active_spacing * np.sqrt(3.0) / 2.0
        centers = []
        row = 0
        y = row_spacing / 2.0
        while y < height:
            x = active_spacing / 2.0
            if row % 2:
                x += active_spacing / 2.0
            while x < width:
                centers.append((x, y))
                x += active_spacing
            row += 1
            y += row_spacing
        return np.asarray(centers, dtype=np.float64)

    centers = build(spacing)
    while len(centers) > min(target_count, MAX_STROKES):
        spacing *= 1.005
        centers = build(spacing)

    if len(centers) < 4:
        centers = np.asarray(
            [
                [width * 0.25, height * 0.25],
                [width * 0.75, height * 0.25],
                [width * 0.25, height * 0.75],
                [width * 0.75, height * 0.75],
            ],
            dtype=np.float64,
        )
    if jitter > 0:
        maximum_offset = spacing * 0.30 * jitter
        centers = centers + rng.uniform(
            -maximum_offset,
            maximum_offset,
            centers.shape,
        )
        centers[:, 0] = np.clip(centers[:, 0], 0.0, width - 1.0)
        centers[:, 1] = np.clip(centers[:, 1], 0.0, height - 1.0)
    return centers, float(spacing)


def generate_strokes(
    height: int, width: int, config: Config, rng: RandomStreams
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    profile = size_profile(height, width)
    if (
        config.brush_shape == "hexagon"
        and config.hex_layout == "honeycomb"
        and config.shape_size is not None
    ):
        stroke_count = int(
            round(
                profile.maximum_cells
                - (profile.maximum_cells - profile.minimum_cells)
                * config.shape_size
            )
        )
    elif config.density is None:
        stroke_count = max(
            4, int(round(height * width / config.average_spacing**2))
        )
    else:
        stroke_count = int(
            round(
                profile.minimum_cells
                + (profile.maximum_cells - profile.minimum_cells)
                * config.density
            )
        )

    honeycomb_centers: np.ndarray | None = None
    if config.brush_shape == "hexagon" and config.hex_layout == "honeycomb":
        honeycomb_centers, _ = hex_honeycomb_centers(
            height,
            width,
            stroke_count,
            config.hex_jitter,
            rng,
        )
        stroke_count = len(honeycomb_centers)
        starts = honeycomb_centers
    else:
        starts = np.stack(
            [
                rng.uniform(0, width, stroke_count),
                rng.uniform(0, height, stroke_count),
            ],
            axis=1,
        )
    flow_angle = config.flow_angle
    if flow_angle is None:
        flow_angle = DEFAULT_FLOW_ANGLES.get(config.brush_shape)
    if (
        flow_angle is None
        and config.brush_shape == "hexagon"
        and config.hex_layout == "honeycomb"
    ):
        flow_angle = 0.0

    if flow_angle is None:
        angles = rng.uniform(0, 2.0 * np.pi, stroke_count)
    else:
        center_angle = np.deg2rad(flow_angle)
        spread = np.pi * config.flow_jitter
        angles = center_angle + rng.uniform(-spread, spread, stroke_count)

    if config.shape_size is None:
        lengths = rng.uniform(
            config.length_min, config.length_max, stroke_count
        )
    else:
        target_length = (
            profile.minimum_length
            + (profile.maximum_length - profile.minimum_length)
            * config.shape_size
        )
        minimum_length = max(
            profile.minimum_length,
            target_length * (1.0 - config.length_variation),
        )
        maximum_length = min(
            profile.maximum_length,
            target_length * (1.0 + config.length_variation),
        )
        lengths = rng.uniform(minimum_length, maximum_length, stroke_count)
    vectors = np.stack(
        [np.cos(angles), np.sin(angles)], axis=1
    ) * lengths[:, None]
    if honeycomb_centers is not None:
        starts = honeycomb_centers - vectors * 0.5
        ends = honeycomb_centers + vectors * 0.5
    else:
        ends = starts + vectors
    widths = np.clip(
        1.0
        + rng.uniform(
            -config.width_variance, config.width_variance, stroke_count
        ),
        0.2,
        None,
    )
    return starts, ends, widths


def build_path_points(
    starts: np.ndarray,
    ends: np.ndarray,
    samples_per_stroke: int,
    brush_shape: str,
    swirl_strength: float,
    curvature: float = DEFAULT_CURVATURE,
    segments: int = DEFAULT_SEGMENTS,
    roughness: float = DEFAULT_ROUGHNESS,
    branching: float = DEFAULT_BRANCHING,
) -> np.ndarray:
    """Build straight or curved centerline samples for every stroke."""

    amounts = np.linspace(0.0, 1.0, samples_per_stroke)
    points = (
        starts[:, None, :] * (1.0 - amounts[None, :, None])
        + ends[:, None, :] * amounts[None, :, None]
    )

    if brush_shape not in DEFORMED_PATH_SHAPES:
        return points

    direction = ends - starts
    lengths = np.linalg.norm(direction, axis=1)
    safe_lengths = np.maximum(lengths, 1e-9)
    perpendicular = np.stack(
        [-direction[:, 1], direction[:, 0]], axis=1
    ) / safe_lengths[:, None]
    alternating_direction = np.where(
        np.arange(len(starts)) % 2 == 0, 1.0, -1.0
    )

    if brush_shape == "swirl":
        curve = (
            np.sin(np.pi * amounts)[None, :]
            * lengths[:, None]
            * (0.35 * swirl_strength)
            * alternating_direction[:, None]
        )
    elif brush_shape == "vine":
        curve = (
            np.sin(2.0 * np.pi * amounts)[None, :]
            * lengths[:, None]
            * 0.16
            * alternating_direction[:, None]
        )
    elif brush_shape == "crack":
        sample_numbers = np.arange(samples_per_stroke)
        jagged_direction = np.where(
            (
                sample_numbers[None, :]
                + np.arange(len(starts))[:, None]
            )
            % 2
            == 0,
            1.0,
            -1.0,
        )
        envelope = np.sin(np.pi * amounts)[None, :]
        curve = lengths[:, None] * 0.13 * envelope * jagged_direction
    elif brush_shape == "chevron":
        bend = 1.0 - np.abs(2.0 * amounts - 1.0)
        curve = (
            bend[None, :]
            * lengths[:, None]
            * 0.24
            * alternating_direction[:, None]
        )
    elif brush_shape == "circuit-trace":
        bends = np.sin(2.0 * np.pi * amounts)
        curve = (
            bends[None, :]
            * lengths[:, None]
            * 0.24
            * alternating_direction[:, None]
        )
    elif brush_shape in DEFORMED_PATH_SHAPES:
        cycles = effective_segments(segments, samples_per_stroke)
        rough_wave = np.sin(
            (cycles + 1.0) * np.pi * amounts
        ) * roughness
        if brush_shape == "grass-blade":
            profile = np.sin(np.pi * amounts)
            curve = profile[None, :] * lengths[:, None] * (
                0.22 * curvature + 0.04 * rough_wave[None, :]
            )
        elif brush_shape == "grass-clump":
            profile = np.sin(np.pi * amounts)
            lobes = np.sin(cycles * np.pi * amounts)
            curve = profile[None, :] * lengths[:, None] * (
                0.16 * curvature
                + 0.08 * branching * lobes[None, :]
                + 0.04 * rough_wave[None, :]
            )
        elif brush_shape == "branching-twig":
            turns = np.sin((cycles + 1.0) * np.pi * amounts)
            branch_turns = np.sin((cycles + 2.0) * np.pi * amounts)
            curve = lengths[:, None] * (
                0.15 * curvature * turns[None, :]
                + 0.10 * branching * branch_turns[None, :]
                + 0.04 * rough_wave[None, :]
            )
        elif brush_shape == "feather":
            barbs = np.sin(cycles * np.pi * amounts)
            curve = lengths[:, None] * (
                0.10 * curvature * np.sin(np.pi * amounts)[None, :]
                + 0.05 * roughness * barbs[None, :]
            )
        elif brush_shape == "fur-tuft":
            curve = lengths[:, None] * (
                0.07 * curvature * np.sin(np.pi * amounts)[None, :]
                + 0.08 * rough_wave[None, :]
            )
        elif brush_shape == "fish-scale":
            curve = (
                np.sin(np.pi * amounts)[None, :]
                * lengths[:, None]
                * 0.14
                * curvature
            )
        elif brush_shape == "insect-wing":
            veins = np.sin(cycles * np.pi * amounts)
            curve = lengths[:, None] * (
                0.15 * curvature * np.sin(2.0 * np.pi * amounts)[None, :]
                + 0.04 * roughness * veins[None, :]
            )
        elif brush_shape == "beetle-shell":
            curve = (
                np.sin(np.pi * amounts)[None, :]
                * lengths[:, None]
                * 0.10
                * curvature
            )
        elif brush_shape == "moss-patch":
            lobes = np.sin(cycles * np.pi * amounts)
            curve = lengths[:, None] * (
                0.08 * curvature * np.sin(np.pi * amounts)[None, :]
                + 0.10 * roughness * lobes[None, :]
                + 0.06 * branching * rough_wave[None, :]
            )
        elif brush_shape == "tentacle":
            sweep = np.sin(2.0 * np.pi * amounts)
            branch_sweep = np.sin((cycles + 1.0) * np.pi * amounts)
            curve = lengths[:, None] * (
                0.22 * curvature * sweep[None, :]
                + 0.06 * branching * branch_sweep[None, :]
                + 0.04 * roughness * rough_wave[None, :]
            )
        else:  # pragma: no cover - protected by the shape set
            raise ValueError(f"Unknown deformed path shape: {brush_shape!r}")
        curve = curve * alternating_direction[:, None]
    else:  # pragma: no cover - protected by DEFORMED_PATH_SHAPES
        raise ValueError(f"Unknown deformed path shape: {brush_shape!r}")

    points = points + perpendicular[:, None, :] * curve[..., None]
    # Trigonometric curves can leave tiny floating-point residues at a zero
    # crossing. Exact endpoints improve repeatability and tree bounds.
    points[:, 0] = starts
    points[:, -1] = ends

    return points


def build_candidate_tree(
    starts: np.ndarray,
    ends: np.ndarray,
    samples_per_stroke: int,
    brush_shape: str = "capsule",
    swirl_strength: float = 0.55,
    curvature: float = DEFAULT_CURVATURE,
    segments: int = DEFAULT_SEGMENTS,
    roughness: float = DEFAULT_ROUGHNESS,
    branching: float = DEFAULT_BRANCHING,
) -> tuple[cKDTree, np.ndarray, np.ndarray]:
    """Index centerline samples so long or curved strokes remain discoverable."""

    if brush_shape in CENTERED_PANEL_SHAPES:
        centers = ((starts + ends) / 2.0)[:, None, :]
        stroke_ids = np.arange(len(starts))
        return cKDTree(centers[:, 0]), stroke_ids, centers

    points = build_path_points(
        starts,
        ends,
        samples_per_stroke,
        brush_shape,
        swirl_strength,
        curvature,
        segments,
        roughness,
        branching,
    )
    stroke_ids = np.repeat(np.arange(len(starts)), samples_per_stroke)
    return cKDTree(points.reshape(-1, 2)), stroke_ids, points


def segment_distance(
    pixel_x: np.ndarray,
    pixel_y: np.ndarray,
    starts: np.ndarray,
    ends: np.ndarray,
    widths: np.ndarray,
    candidate_indices: np.ndarray,
) -> np.ndarray:
    """Calculate weighted point-to-segment distance for candidate strokes."""

    segment_start = starts[candidate_indices]
    segment_end = ends[candidate_indices]
    candidate_width = widths[candidate_indices]
    segment_x = segment_end[..., 0] - segment_start[..., 0]
    segment_y = segment_end[..., 1] - segment_start[..., 1]
    point_x = pixel_x[:, None] - segment_start[..., 0]
    point_y = pixel_y[:, None] - segment_start[..., 1]
    length_squared = np.maximum(segment_x**2 + segment_y**2, 1e-9)
    amount = np.clip(
        (point_x * segment_x + point_y * segment_y) / length_squared,
        0.0,
        1.0,
    )
    closest_x = segment_start[..., 0] + amount * segment_x
    closest_y = segment_start[..., 1] + amount * segment_y
    delta_x = pixel_x[:, None] - closest_x
    delta_y = pixel_y[:, None] - closest_y
    return np.sqrt(delta_x**2 + delta_y**2) / candidate_width


def hexagon_distance(
    pixel_x: np.ndarray,
    pixel_y: np.ndarray,
    starts: np.ndarray,
    ends: np.ndarray,
    widths: np.ndarray,
    candidate_indices: np.ndarray,
    priority_weights: np.ndarray | None = None,
) -> np.ndarray:
    """Score candidates with a rotated, regular point-to-point hexagon norm."""

    candidate_starts = starts[candidate_indices]
    candidate_ends = ends[candidate_indices]
    direction = candidate_ends - candidate_starts
    lengths = np.maximum(
        np.linalg.norm(direction, axis=-1),
        1e-9,
    )
    direction_x = direction[..., 0] / lengths
    direction_y = direction[..., 1] / lengths
    centers = (candidate_starts + candidate_ends) / 2.0
    delta_x = pixel_x[:, None] - centers[..., 0]
    delta_y = pixel_y[:, None] - centers[..., 1]

    # Rotate each pixel into its candidate's local frame. Local X points at
    # opposite hex vertices; local Y points at opposite flat sides.
    local_x = delta_x * direction_x + delta_y * direction_y
    local_y = -delta_x * direction_y + delta_y * direction_x
    absolute_x = np.abs(local_x)
    absolute_y = np.abs(local_y)
    inverse_sqrt_three = 1.0 / np.sqrt(3.0)
    hex_metric = np.maximum(
        2.0 * absolute_y * inverse_sqrt_three,
        absolute_x + absolute_y * inverse_sqrt_three,
    )

    radius = lengths * 0.5 * widths[candidate_indices]
    if priority_weights is not None:
        radius = radius * priority_weights[candidate_indices]
    radius = np.maximum(radius, 1e-9)

    # Retain pixel-like units for --edge-softness while allowing generated
    # size variation and overlap priority to change which panel wins.
    reference_radius = max(
        float(np.median(np.linalg.norm(ends - starts, axis=1))) * 0.5,
        1e-9,
    )
    return hex_metric * (reference_radius / radius)


def panel_distance(
    pixel_x: np.ndarray,
    pixel_y: np.ndarray,
    starts: np.ndarray,
    ends: np.ndarray,
    widths: np.ndarray,
    candidate_indices: np.ndarray,
    brush_shape: str,
    priority_weights: np.ndarray | None = None,
) -> np.ndarray:
    """Score candidates with a rotated diamond or regular-octagon norm."""

    candidate_starts = starts[candidate_indices]
    candidate_ends = ends[candidate_indices]
    direction = candidate_ends - candidate_starts
    lengths = np.maximum(
        np.linalg.norm(direction, axis=-1),
        1e-9,
    )
    direction_x = direction[..., 0] / lengths
    direction_y = direction[..., 1] / lengths
    centers = (candidate_starts + candidate_ends) / 2.0
    delta_x = pixel_x[:, None] - centers[..., 0]
    delta_y = pixel_y[:, None] - centers[..., 1]
    local_x = delta_x * direction_x + delta_y * direction_y
    local_y = -delta_x * direction_y + delta_y * direction_x
    absolute_x = np.abs(local_x)
    absolute_y = np.abs(local_y)

    if brush_shape == "diamond-panel":
        panel_metric = absolute_x + absolute_y
    elif brush_shape == "octagon-panel":
        panel_metric = np.maximum.reduce(
            (
                absolute_x,
                absolute_y,
                (absolute_x + absolute_y) / np.sqrt(2.0),
            )
        )
    else:
        raise ValueError(f"Unknown panel shape: {brush_shape!r}")

    radius = lengths * 0.5 * widths[candidate_indices]
    if priority_weights is not None:
        radius = radius * priority_weights[candidate_indices]
    radius = np.maximum(radius, 1e-9)
    reference_radius = max(
        float(np.median(np.linalg.norm(ends - starts, axis=1))) * 0.5,
        1e-9,
    )
    return panel_metric * (reference_radius / radius)


def taper_factor(
    amount: np.ndarray,
    brush_shape: str,
    segments: int = DEFAULT_SEGMENTS,
    roughness: float = DEFAULT_ROUGHNESS,
    symmetry: float = DEFAULT_SYMMETRY,
    branching: float = DEFAULT_BRANCHING,
    sample_count: int | None = None,
) -> np.ndarray:
    """Return width along a stroke; 0.08 prevents singular sharp tips."""

    cycles = (
        effective_segments(segments, sample_count)
        if sample_count is not None
        else segments
    )
    if brush_shape in ("capsule", "swirl"):
        factor = np.ones_like(amount)
    elif brush_shape == "sharp-start":
        factor = amount
    elif brush_shape == "sharp-end":
        factor = 1.0 - amount
    elif brush_shape == "sharp-both":
        factor = 1.0 - np.abs(2.0 * amount - 1.0)
    elif brush_shape == "scale":
        # Teardrop: a pointed start flowing into a broad, rounded end.
        factor = np.sin(amount * np.pi / 2.0)
    elif brush_shape == "leaf":
        # A soft, symmetrical lens with natural-looking pointed ends.
        factor = np.sin(np.pi * amount) ** 0.55
    elif brush_shape == "petal":
        # A leaf-like base that grows fuller toward the blossom end.
        factor = (
            np.sin(np.pi * amount) ** 0.55
            * (0.72 + 0.38 * amount)
        )
        factor = np.minimum(factor, 1.0)
    elif brush_shape == "pine-needle":
        factor = 0.35 * np.sin(np.pi * amount) ** 0.42
    elif brush_shape == "scallop":
        lobe = 0.88 + 0.12 * np.cos(4.0 * np.pi * amount)
        factor = np.sin(amount * np.pi / 2.0) ** 0.65 * lobe
    elif brush_shape == "vine":
        factor = 0.48 * (0.85 + 0.15 * np.cos(2.0 * np.pi * amount))
    elif brush_shape == "bark":
        factor = 0.62 + 0.16 * np.cos(6.0 * np.pi * amount)
    elif brush_shape == "pebble":
        factor = np.sqrt(
            np.maximum(0.0, 1.0 - (2.0 * amount - 1.0) ** 2)
        )
    elif brush_shape == "boulder":
        oval = np.maximum(
            0.0, 1.0 - (2.0 * amount - 1.0) ** 2
        ) ** 0.28
        lobes = 0.82 + 0.18 * np.cos(6.0 * np.pi * amount)
        factor = oval * lobes
    elif brush_shape == "crack":
        factor = 0.22 * (0.55 + 0.45 * np.sin(np.pi * amount))
    elif brush_shape == "crystal":
        # A broad faceted body with a short base bevel and longer tip.
        factor = np.minimum.reduce(
            (
                amount / 0.18,
                (1.0 - amount) / 0.32,
                np.ones_like(amount),
            )
        )
    elif brush_shape == "shard":
        # An off-center ridge creates a narrow, splintered mineral profile.
        factor = np.minimum.reduce(
            (
                amount / 0.12,
                (1.0 - amount) / 0.70,
                np.ones_like(amount),
            )
        )
    elif brush_shape == "chevron":
        factor = 0.60 * (0.80 + 0.20 * np.sin(np.pi * amount))
    elif brush_shape == "circuit-trace":
        factor = np.full_like(amount, 0.30)
    elif brush_shape == "grass-blade":
        factor = 0.12 + 0.88 * (1.0 - amount) ** 0.55
    elif brush_shape == "grass-clump":
        lobes = 0.82 + 0.18 * np.abs(
            np.sin(cycles * np.pi * amount)
        )
        factor = (0.18 + 0.82 * (1.0 - amount) ** 0.62) * lobes
    elif brush_shape == "branching-twig":
        factor = 0.22 + 0.78 * (1.0 - amount) ** 0.52
    elif brush_shape == "feather":
        barbs = 0.82 + 0.18 * np.sin(
            cycles * np.pi * amount
        ) ** 2
        factor = (0.12 + 0.88 * np.sin(np.pi * amount) ** 0.62) * barbs
    elif brush_shape == "fur-tuft":
        factor = 0.10 + 0.90 * (1.0 - amount) ** 0.48
    elif brush_shape == "fish-scale":
        factor = 0.10 + 0.90 * np.sin(np.pi * amount) ** 0.72
    elif brush_shape == "insect-wing":
        factor = 0.10 + 0.90 * np.sin(np.pi * amount) ** 0.58
    elif brush_shape == "beetle-shell":
        factor = 0.12 + 0.88 * np.sin(np.pi * amount) ** 0.38
    elif brush_shape == "moss-patch":
        lobes = 0.78 + 0.22 * np.abs(
            np.sin(cycles * np.pi * amount)
        )
        factor = (0.22 + 0.78 * np.sin(np.pi * amount) ** 0.34) * lobes
    elif brush_shape == "tentacle":
        factor = 0.12 + 0.88 * (1.0 - amount) ** 0.58
    else:
        raise ValueError(f"Unknown brush shape: {brush_shape!r}")
    if brush_shape in DEFORMED_PATH_SHAPES and brush_shape not in (
        "swirl", "vine", "crack", "chevron", "circuit-trace"
    ):
        asymmetry = 1.0 + (1.0 - symmetry) * 0.30 * (2.0 * amount - 1.0)
        irregularity = 1.0 + roughness * 0.10 * np.sin(
            cycles * 2.0 * np.pi * amount
        )
        branch_lift = 1.0 + branching * 0.06 * np.sin(
            (cycles + 1.0) * np.pi * amount
        )
        factor = factor * asymmetry * irregularity * branch_lift
    return np.clip(factor, 0.08, 1.0)


def path_distance(
    pixel_x: np.ndarray,
    pixel_y: np.ndarray,
    path_points: np.ndarray,
    widths: np.ndarray,
    candidate_indices: np.ndarray,
    brush_shape: str,
    priority_weights: np.ndarray | None,
    segments: int = DEFAULT_SEGMENTS,
    roughness: float = DEFAULT_ROUGHNESS,
    symmetry: float = DEFAULT_SYMMETRY,
    branching: float = DEFAULT_BRANCHING,
) -> np.ndarray:
    """Calculate distance to a tapered polyline without large 4-D arrays."""

    segment_count = path_points.shape[1] - 1
    best = np.full(candidate_indices.shape, np.inf, dtype=np.float64)
    candidate_width = widths[candidate_indices]
    if priority_weights is None:
        candidate_priority = 1.0
    else:
        candidate_priority = priority_weights[candidate_indices]

    for segment_index in range(segment_count):
        segment_start = path_points[candidate_indices, segment_index]
        segment_end = path_points[candidate_indices, segment_index + 1]
        segment_x = segment_end[..., 0] - segment_start[..., 0]
        segment_y = segment_end[..., 1] - segment_start[..., 1]
        point_x = pixel_x[:, None] - segment_start[..., 0]
        point_y = pixel_y[:, None] - segment_start[..., 1]
        length_squared = np.maximum(segment_x**2 + segment_y**2, 1e-9)
        local_amount = np.clip(
            (point_x * segment_x + point_y * segment_y) / length_squared,
            0.0,
            1.0,
        )
        closest_x = segment_start[..., 0] + local_amount * segment_x
        closest_y = segment_start[..., 1] + local_amount * segment_y
        delta_x = pixel_x[:, None] - closest_x
        delta_y = pixel_y[:, None] - closest_y
        global_amount = (
            segment_index + local_amount
        ) / float(segment_count)
        taper = taper_factor(
            global_amount,
            brush_shape,
            segments,
            roughness,
            symmetry,
            branching,
            path_points.shape[1],
        )
        distance = np.sqrt(delta_x**2 + delta_y**2)
        distance = distance / (
            candidate_width * taper * candidate_priority
        )
        best = np.minimum(best, distance)

    return best


def overlap_weights(
    starts: np.ndarray,
    ends: np.ndarray,
    order: str,
    strength: float,
    profile: SizeProfile,
) -> np.ndarray | None:
    """Map normalized overlap controls into a bounded distance advantage."""

    if strength == 0 or order == "balanced":
        return None

    stroke_count = len(starts)
    if order == "earlier":
        score = np.linspace(1.0, -1.0, stroke_count)
    elif order == "later":
        score = np.linspace(-1.0, 1.0, stroke_count)
    elif order in ("larger", "smaller"):
        lengths = np.linalg.norm(ends - starts, axis=1)
        length_range = np.ptp(lengths)
        if length_range < 1e-9:
            score = np.zeros(stroke_count)
        else:
            score = 2.0 * (lengths - lengths.min()) / length_range - 1.0
        if order == "smaller":
            score = -score
    else:
        raise ValueError(f"Unknown overlap order: {order!r}")

    bias = profile.maximum_priority_bias * strength
    return 1.0 + score * bias


def assign_cells(
    height: int,
    width: int,
    starts: np.ndarray,
    ends: np.ndarray,
    widths: np.ndarray,
    candidates: int,
    samples_per_stroke: int,
    edge_selection: str = "legacy",
    chunk_rows: int = 64,
    brush_shape: str = "capsule",
    swirl_strength: float = 0.55,
    priority_weights: np.ndarray | None = None,
    workers: int = 1,
    curvature: float = DEFAULT_CURVATURE,
    segments: int = DEFAULT_SEGMENTS,
    roughness: float = DEFAULT_ROUGHNESS,
    symmetry: float = DEFAULT_SYMMETRY,
    branching: float = DEFAULT_BRANCHING,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    tree, stroke_ids, path_points = build_candidate_tree(
        starts,
        ends,
        samples_per_stroke,
        brush_shape,
        swirl_strength,
        curvature,
        segments,
        roughness,
        branching,
    )
    candidate_count = min(
        requested_candidate_count(
            candidates,
            samples_per_stroke,
            edge_selection,
            priority_weights is not None,
            brush_shape,
        ),
        len(stroke_ids),
    )

    nearest_cell = np.empty((height, width), dtype=np.int64)
    distance_dtype = (
        np.float64 if edge_selection == "legacy" else np.float32
    )
    nearest_distance = np.empty((height, width), dtype=distance_dtype)
    second_cell = np.empty((height, width), dtype=np.int64)
    second_distance = np.empty((height, width), dtype=distance_dtype)

    for row_start in range(0, height, chunk_rows):
        row_end = min(row_start + chunk_rows, height)
        row_count = row_end - row_start
        pixel_x = np.tile(
            np.arange(width, dtype=np.float32), row_count
        )
        pixel_y = np.repeat(
            np.arange(row_start, row_end, dtype=np.float32), width
        )
        _, sample_indices = tree.query(
            np.stack([pixel_x, pixel_y], axis=1),
            k=candidate_count,
            workers=resolve_workers(workers),
        )
        if candidate_count == 1:
            sample_indices = sample_indices[:, None]
        candidate_indices = stroke_ids[sample_indices]
        if brush_shape == "hexagon":
            distances = hexagon_distance(
                pixel_x,
                pixel_y,
                starts,
                ends,
                widths,
                candidate_indices,
                priority_weights,
            )
        elif brush_shape in ("diamond-panel", "octagon-panel"):
            distances = panel_distance(
                pixel_x,
                pixel_y,
                starts,
                ends,
                widths,
                candidate_indices,
                brush_shape,
                priority_weights,
            )
        elif brush_shape == "capsule":
            distances = segment_distance(
                pixel_x, pixel_y, starts, ends, widths, candidate_indices
            )
            if priority_weights is not None:
                distances = (
                    distances / priority_weights[candidate_indices]
                )
        else:
            distances = path_distance(
                pixel_x,
                pixel_y,
                path_points,
                widths,
                candidate_indices,
                brush_shape,
                priority_weights,
                segments,
                roughness,
                symmetry,
                branching,
            )
        if edge_selection == "legacy":
            # Preserve the original candidate ordering and compatibility
            # checksum for legacy capsule processing.
            order = np.argsort(distances, axis=1)
            sorted_indices = np.take_along_axis(
                candidate_indices, order, axis=1
            )
            sorted_distances = np.take_along_axis(distances, order, axis=1)
            chunk_assignments = (
                sorted_indices[:, 0],
                sorted_distances[:, 0],
                sorted_indices[:, 1],
                sorted_distances[:, 1],
            )
        else:
            row_indices = np.arange(len(distances))
            nearest_position = np.argmin(distances, axis=1)
            selected_nearest_cell = candidate_indices[
                row_indices, nearest_position
            ]
            selected_nearest_distance = distances[
                row_indices, nearest_position
            ]
            different_distances = np.where(
                candidate_indices == selected_nearest_cell[:, None],
                np.inf,
                distances,
            )
            second_position = np.argmin(different_distances, axis=1)
            has_second = np.isfinite(
                different_distances[row_indices, second_position]
            )
            selected_second_cell = candidate_indices[row_indices, second_position]
            selected_second_distance = different_distances[
                row_indices, second_position
            ]
            chunk_assignments = (
                selected_nearest_cell,
                selected_nearest_distance,
                np.where(
                    has_second, selected_second_cell, selected_nearest_cell
                ),
                np.where(
                    has_second,
                    selected_second_distance,
                    selected_nearest_distance,
                ),
            )

        destination_arrays = (
            nearest_cell,
            nearest_distance,
            second_cell,
            second_distance,
        )
        for destination, values in zip(
            destination_arrays, chunk_assignments, strict=True
        ):
            destination[row_start:row_end] = values.reshape(
                row_end - row_start, width
            )

    return nearest_cell, nearest_distance, second_cell, second_distance


def process(
    array: ImageArray,
    common: CommonOptions,
    config: Config,
    rng: RandomStreams,
) -> ImageArray:
    height, width, _ = array.shape
    validate_workload(height, width, config)
    starts, ends, widths = generate_strokes(height, width, config, rng)
    profile = size_profile(height, width)
    priority_weights = overlap_weights(
        starts,
        ends,
        config.overlap_order,
        config.overlap_priority,
        profile,
    )
    nearest, nearest_distance, second, second_distance = assign_cells(
        height,
        width,
        starts,
        ends,
        widths,
        config.candidates,
        config.samples_per_stroke,
        config.edge_selection,
        config.chunk_rows,
        config.brush_shape,
        config.swirl_strength,
        priority_weights,
        config.workers,
        config.curvature,
        config.segments,
        config.roughness,
        config.symmetry,
        config.branching,
    )
    if config.brush_shape in DEFORMED_PATH_SHAPES:
        paths = build_path_points(
            starts,
            ends,
            config.samples_per_stroke,
            config.brush_shape,
            config.swirl_strength,
            config.curvature,
            config.segments,
            config.roughness,
            config.branching,
        )
        midpoints = paths[:, len(paths[0]) // 2]
    else:
        midpoints = (starts + ends) / 2.0
    midpoints, island_components = isolate_cells_across_padding(
        array,
        nearest,
        second,
        midpoints,
        common.black_threshold,
        config.chunk_rows,
    )
    averages, has_surface = compute_cell_averages(
        array,
        nearest,
        len(midpoints),
        common.black_threshold,
        config.chunk_rows,
    )
    differentiate_isolated_neighbors(
        midpoints,
        island_components,
        averages,
        has_surface,
        common,
        rng,
    )
    if island_components is not None:
        keep_second_cells_inside_islands(
            nearest,
            nearest_distance,
            second,
            second_distance,
            has_surface,
            config.chunk_rows,
        )
    return paint_cells(
        array,
        averages,
        nearest,
        nearest_distance,
        second,
        second_distance,
        config.edge_softness,
        common,
        config.chunk_rows,
    )
