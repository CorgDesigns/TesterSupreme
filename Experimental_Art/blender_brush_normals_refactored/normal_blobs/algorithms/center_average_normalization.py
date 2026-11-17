"""One soft, average-colored circle per square grid block."""

from __future__ import annotations

from argparse import ArgumentParser, Namespace
from dataclasses import dataclass

import numpy as np

from normal_blobs.algorithms.grid_common import (
    paint_circle,
    prepare_component_grid,
    prepare_grid,
)
from normal_blobs.color import renormalize_pixels, surface_mask
from normal_blobs.models import (
    CommonOptions,
    ImageArray,
    RandomStreams,
    ResourceEstimate,
)
from normal_blobs.resources import grid_resource_estimate
from normal_blobs.validation import float_in_range, integer_in_range

NAME = "center_average_normalization"
SUMMARY = "Algorithm 1: soft average-normal circles on a regular grid."
DESCRIPTION = """
Algorithm 1 divides each UV island into square blocks, averages the object-space
normals inside each block, and paints one soft circle at the block center.

Use it for calm, regular dot or dimple patterns with the lowest configuration
complexity. Smaller blocks produce more circles; a larger circle ratio covers
more of each block. Black padding and disconnected UV islands remain isolated.
""".strip()
HELP_EPILOG = """
Examples:
  py procedural_normal_blobs.py center_average_normalization --seed 42
  py procedural_normal_blobs.py center_average_normalization --block-size 128 --circle-ratio 0.65

Start with:
  --block-size controls how many grid cells are created.
  --circle-ratio controls how much of each cell the soft circle covers.
""".strip()


@dataclass(frozen=True)
class Config:
    block_size: int
    circle_ratio: float


def estimate_resources(
    height: int, width: int, config: Config
) -> ResourceEstimate:
    """Estimate peak CPU memory before loading the source pixels."""

    return grid_resource_estimate(height, width, bytes_per_pixel=96)


def add_arguments(parser: ArgumentParser) -> None:
    parser.add_argument(
        "--block-size",
        type=integer_in_range(64, 2048),
        default=256,
        metavar="PIXELS",
        help=(
            "Square grid-block size from 64 to 2048. Smaller values create "
            "more circles; larger values create fewer, broader cells "
            "(default: 256)."
        ),
    )
    parser.add_argument(
        "--circle-ratio",
        type=float_in_range(0.01, 1.0),
        default=0.8,
        metavar="RATIO",
        help=(
            "Circle diameter relative to its block from 0.01 to 1. Higher "
            "values fill more of the grid cell (default: 0.8)."
        ),
    )


def make_config(args: Namespace) -> Config:
    return Config(block_size=args.block_size, circle_ratio=args.circle_ratio)


def process(
    array: ImageArray,
    common: CommonOptions,
    config: Config,
    rng: RandomStreams,
) -> ImageArray:
    component_grid = prepare_component_grid(
        array, config.block_size, common, rng
    )
    if component_grid is not None:
        height, width, _ = array.shape
        output = array.copy()
        for block_y in range(component_grid.blocks_high):
            for block_x in range(component_grid.blocks_wide):
                y0 = block_y * config.block_size
                y1 = min((block_y + 1) * config.block_size, height)
                x0 = block_x * config.block_size
                x1 = min((block_x + 1) * config.block_size, width)
                center_x = (x0 + x1) / 2.0
                center_y = (y0 + y1) / 2.0
                radius = (
                    min(x1 - x0, y1 - y0)
                    * config.circle_ratio
                    / 2.0
                )
                for component in component_grid.components_by_block.get(
                    (block_y, block_x), ()
                ):
                    paint_circle(
                        output,
                        array,
                        center_x,
                        center_y,
                        radius,
                        component_grid.averages[
                            (block_y, block_x, int(component))
                        ],
                        common,
                        component_grid.labels,
                        int(component),
                    )
        return output

    averages, has_surface, blocks_high, blocks_wide = prepare_grid(
        array, config.block_size, common, rng
    )
    height, width, _ = array.shape
    output = array.copy()

    for block_y in range(blocks_high):
        for block_x in range(blocks_wide):
            if not has_surface[block_y, block_x]:
                continue

            y0 = block_y * config.block_size
            y1 = min((block_y + 1) * config.block_size, height)
            x0 = block_x * config.block_size
            x1 = min((block_x + 1) * config.block_size, width)
            center_x = (x0 + x1) / 2.0
            center_y = (y0 + y1) / 2.0
            radius = min(x1 - x0, y1 - y0) * config.circle_ratio / 2.0

            region = array[y0:y1, x0:x1]
            mask = surface_mask(region, common.black_threshold)
            yy, xx = np.mgrid[y0:y1, x0:x1]
            distance = np.sqrt((xx - center_x) ** 2 + (yy - center_y) ** 2)
            falloff = np.clip(1.0 - distance / radius, 0.0, 1.0)
            weight = (falloff * common.blend_strength * mask)[..., None]
            blended = (
                region * (1.0 - weight)
                + averages[block_y, block_x] * weight
            )
            if common.renormalize:
                normalized = renormalize_pixels(blended, region)
                blended = np.where(weight > 0, normalized, blended)
            output[y0:y1, x0:x1] = np.where(
                mask[..., None], blended, region
            )

    return output
