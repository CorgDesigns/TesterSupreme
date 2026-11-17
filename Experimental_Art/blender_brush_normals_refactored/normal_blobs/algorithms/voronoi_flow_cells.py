"""Random weighted, directionally elongated Voronoi cells."""

from __future__ import annotations

from argparse import ArgumentParser, Namespace
from dataclasses import dataclass

import numpy as np
from scipy.spatial import cKDTree

from normal_blobs.algorithms.cell_common import (
    ISOLATED_KEY_SCRATCH_BYTES,
    compute_cell_averages,
    differentiate_isolated_neighbors,
    first_two_distinct,
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

NAME = "voronoi_flow_cells"
SUMMARY = "Algorithm 3: irregular stretched Voronoi flow cells."
DESCRIPTION = """
Algorithm 3 scatters weighted seed points and assigns pixels to directionally
stretched Voronoi cells. Random size and elongation create flowing, stone-like,
organic, or hammered territories without a visible square grid.

Use it when irregular cells matter more than a recognizable brush silhouette.
Smaller average cell sizes and more candidates increase detail and processing
cost. Work is chunked to stay inside the configured RAM safety budget.
""".strip()
HELP_EPILOG = """
Examples:
  py procedural_normal_blobs.py voronoi_flow_cells --seed 42
  py procedural_normal_blobs.py voronoi_flow_cells --average-cell-size 90 --size-variance 0.7 --elongation-max 3

Start with:
  --average-cell-size controls cell density and has the largest visual impact.
  --size-variance changes how uniform the cells appear.
  --elongation-max changes circular cells into directional flow cells.
""".strip()
MAX_VORONOI_CELLS = 1_000_000


@dataclass(frozen=True)
class Config:
    average_cell_size: float
    size_variance: float
    elongation_max: float
    edge_softness: float
    candidates: int
    chunk_rows: int = 64


def estimate_resources(
    height: int, width: int, config: Config
) -> ResourceEstimate:
    """Estimate persistent maps and worst-case chunk working arrays."""

    pixels = height * width
    chunk_pixels = min(config.chunk_rows, height) * width
    persistent = pixels * 96
    spacing_squared = config.average_cell_size**2
    if spacing_squared == 0:
        return ResourceEstimate(cpu_bytes=2**63 - 1)
    cell_count = max(4, int(round(pixels / spacing_squared)))
    if cell_count > MAX_VORONOI_CELLS:
        return ResourceEstimate(cpu_bytes=2**63 - 1)
    candidate_count = min(config.candidates, cell_count)
    scratch = chunk_pixels * candidate_count * 96
    seeds_and_tree = cell_count * 128
    cpu_bytes = int(
        (
            persistent
            + scratch
            + seeds_and_tree
            + ISOLATED_KEY_SCRATCH_BYTES
            + 64 * MIB
        )
        * 1.25
    )
    return ResourceEstimate(cpu_bytes=cpu_bytes)


def add_arguments(parser: ArgumentParser) -> None:
    parser.add_argument(
        "--average-cell-size",
        type=float_in_range(8.0, 4096.0),
        default=120.0,
        metavar="PIXELS",
        help=(
            "Target average cell diameter from 8 to 4096. Smaller values "
            "create more cells and require more work (default: 120)."
        ),
    )
    parser.add_argument(
        "--size-variance",
        type=float_in_range(0.0, 1.0),
        default=0.5,
        metavar="RATIO",
        help=(
            "Random cell-size variation from 0 (uniform) to 1 (strongly "
            "varied; default: 0.5)."
        ),
    )
    parser.add_argument(
        "--elongation-max",
        type=float_in_range(1.0, 16.0),
        default=2.0,
        metavar="FACTOR",
        help=(
            "Maximum directional stretch from 1 to 16; 1 is circular "
            "(default: 2)."
        ),
    )
    parser.add_argument(
        "--edge-softness",
        type=float_in_range(0.01, 4096.0),
        default=10.0,
        metavar="PIXELS",
        help=(
            "Width of the soft blend between cells from 0.01 to 4096 "
            "(default: 10)."
        ),
    )
    parser.add_argument(
        "--candidates",
        type=integer_in_range(2, 64),
        default=12,
        metavar="COUNT",
        help="Nearby seeds scored per pixel from 2 to 64 (default: 12).",
    )
    parser.add_argument(
        "--chunk-rows",
        type=integer_in_range(1, 128),
        default=64,
        metavar="ROWS",
        help=(
            "Pixel rows processed per memory-bounded chunk; lower values use "
            "less memory; range 1 to 128 (default: 64)."
        ),
    )


def make_config(args: Namespace) -> Config:
    if args.elongation_max < 1.0:
        raise ValueError("--elongation-max must be at least 1")
    return Config(
        average_cell_size=args.average_cell_size,
        size_variance=args.size_variance,
        elongation_max=args.elongation_max,
        edge_softness=args.edge_softness,
        candidates=args.candidates,
        chunk_rows=args.chunk_rows,
    )


def generate_seeds(
    height: int, width: int, config: Config, rng: RandomStreams
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    cell_count = max(
        4, int(round(height * width / config.average_cell_size**2))
    )
    if cell_count > MAX_VORONOI_CELLS:
        raise ValueError(
            f"Voronoi settings would create {cell_count} cells; "
            f"the safe maximum is {MAX_VORONOI_CELLS}"
        )
    positions = np.stack(
        [
            rng.uniform(0, width, cell_count),
            rng.uniform(0, height, cell_count),
        ],
        axis=1,
    )
    weights = np.clip(
        1.0 + rng.uniform(-config.size_variance, config.size_variance, cell_count),
        0.2,
        None,
    )
    angles = rng.uniform(0, np.pi, cell_count)
    elongations = rng.uniform(1.0, config.elongation_max, cell_count)
    return positions, weights, angles, elongations


def weighted_anisotropic_distance(
    pixel_x: np.ndarray,
    pixel_y: np.ndarray,
    positions: np.ndarray,
    weights: np.ndarray,
    angles: np.ndarray,
    elongations: np.ndarray,
    candidate_indices: np.ndarray,
) -> np.ndarray:
    candidate_positions = positions[candidate_indices]
    candidate_weights = weights[candidate_indices]
    candidate_angles = angles[candidate_indices]
    candidate_elongations = elongations[candidate_indices]
    delta_x = pixel_x[:, None] - candidate_positions[..., 0]
    delta_y = pixel_y[:, None] - candidate_positions[..., 1]
    cosine = np.cos(candidate_angles)
    sine = np.sin(candidate_angles)
    along = (delta_x * cosine + delta_y * sine) / candidate_elongations
    perpendicular = -delta_x * sine + delta_y * cosine
    return np.sqrt(along**2 + perpendicular**2) / candidate_weights


def assign_cells(
    height: int,
    width: int,
    positions: np.ndarray,
    weights: np.ndarray,
    angles: np.ndarray,
    elongations: np.ndarray,
    candidates: int,
    chunk_rows: int = 64,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    tree = cKDTree(positions)
    candidate_count = min(candidates, len(positions))
    nearest_cell = np.empty((height, width), dtype=np.int64)
    nearest_distance = np.empty((height, width), dtype=np.float32)
    second_cell = np.empty((height, width), dtype=np.int64)
    second_distance = np.empty((height, width), dtype=np.float32)

    for row_start in range(0, height, chunk_rows):
        row_end = min(row_start + chunk_rows, height)
        row_count = row_end - row_start
        pixel_x = np.tile(
            np.arange(width, dtype=np.float32), row_count
        )
        pixel_y = np.repeat(
            np.arange(row_start, row_end, dtype=np.float32), width
        )
        _, candidate_indices = tree.query(
            np.stack([pixel_x, pixel_y], axis=1), k=candidate_count
        )
        if candidate_count == 1:
            candidate_indices = candidate_indices[:, None]
        distances = weighted_anisotropic_distance(
            pixel_x,
            pixel_y,
            positions,
            weights,
            angles,
            elongations,
            candidate_indices,
        )
        order = np.argsort(distances, axis=1)
        sorted_indices = np.take_along_axis(candidate_indices, order, axis=1)
        sorted_distances = np.take_along_axis(distances, order, axis=1)
        chunk_assignments = first_two_distinct(
            sorted_indices, sorted_distances
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
    positions, weights, angles, elongations = generate_seeds(
        height, width, config, rng
    )
    nearest, nearest_distance, second, second_distance = assign_cells(
        height,
        width,
        positions,
        weights,
        angles,
        elongations,
        config.candidates,
        config.chunk_rows,
    )
    positions, island_components = isolate_cells_across_padding(
        array,
        nearest,
        second,
        positions,
        common.black_threshold,
        config.chunk_rows,
    )
    averages, has_surface = compute_cell_averages(
        array,
        nearest,
        len(positions),
        common.black_threshold,
        config.chunk_rows,
    )
    differentiate_isolated_neighbors(
        positions,
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
