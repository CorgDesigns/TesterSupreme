"""Three-circle horizontal gradient cascade for each square grid block."""

from __future__ import annotations

from argparse import ArgumentParser, Namespace
from dataclasses import dataclass

from normal_blobs.algorithms.grid_common import (
    paint_circle,
    prepare_component_grid,
    prepare_grid,
)
from normal_blobs.color import interpolate_hsv
from normal_blobs.models import (
    CommonOptions,
    ImageArray,
    RandomStreams,
    ResourceEstimate,
)
from normal_blobs.resources import grid_resource_estimate
from normal_blobs.validation import float_in_range, integer_in_range

NAME = "edge_gradient_cascade"
SUMMARY = "Algorithm 2: three-circle grid cells with horizontal gradients."
DESCRIPTION = """
Algorithm 2 divides each UV island into square blocks and paints three soft
circles per block: left edge, center, and right edge. Edge colors blend toward
the neighboring block, creating a horizontal cascade instead of isolated dots.

Use it for orderly bands, scales, tiles, or panels that should flow sideways.
Smaller blocks create a denser pattern. Black padding and disconnected UV
islands remain hard barriers.
""".strip()
HELP_EPILOG = """
Examples:
  py procedural_normal_blobs.py edge_gradient_cascade --seed 42
  py procedural_normal_blobs.py edge_gradient_cascade --block-size 192 --circle-ratio 0.9

Start with:
  --block-size controls the grid density.
  --circle-ratio controls the diameter of each of the three circles.
""".strip()


@dataclass(frozen=True)
class Config:
    block_size: int
    circle_ratio: float


def estimate_resources(
    height: int, width: int, config: Config
) -> ResourceEstimate:
    """Estimate peak CPU memory before loading the source pixels."""

    return grid_resource_estimate(height, width, bytes_per_pixel=128)


def add_arguments(parser: ArgumentParser) -> None:
    parser.add_argument(
        "--block-size",
        type=integer_in_range(64, 2048),
        default=256,
        metavar="PIXELS",
        help=(
            "Square grid-block size from 64 to 2048. Smaller values produce "
            "more three-circle groups (default: 256)."
        ),
    )
    parser.add_argument(
        "--circle-ratio",
        type=float_in_range(0.01, 1.0),
        default=0.8,
        metavar="RATIO",
        help=(
            "Circle diameter relative to half a block from 0.01 to 1. "
            "Higher values make neighboring circles overlap more "
            "(default: 0.8)."
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
            left_colors: dict[int, np.ndarray] = {}
            for block_x in range(component_grid.blocks_wide):
                y0 = block_y * config.block_size
                y1 = min((block_y + 1) * config.block_size, height)
                x0 = block_x * config.block_size
                x1 = min((block_x + 1) * config.block_size, width)
                center_x = (x0 + x1) / 2.0
                center_y = (y0 + y1) / 2.0
                radius = config.block_size * config.circle_ratio / 4.0
                next_left_colors: dict[int, np.ndarray] = {}
                for component_value in (
                    component_grid.components_by_block.get(
                        (block_y, block_x), ()
                    )
                ):
                    component = int(component_value)
                    own_average = component_grid.averages[
                        (block_y, block_x, component)
                    ]
                    left_color = left_colors.get(component, own_average)
                    right_average = component_grid.averages.get(
                        (block_y, block_x + 1, component)
                    )
                    if right_average is None:
                        right_color = own_average
                    else:
                        right_color = interpolate_hsv(
                            own_average, right_average, 0.5
                        )
                    next_left_colors[component] = right_color
                    paint_circle(
                        output,
                        array,
                        x0,
                        center_y,
                        radius,
                        left_color,
                        common,
                        component_grid.labels,
                        component,
                    )
                    paint_circle(
                        output,
                        array,
                        center_x,
                        center_y,
                        radius,
                        own_average,
                        common,
                        component_grid.labels,
                        component,
                    )
                    paint_circle(
                        output,
                        array,
                        x1,
                        center_y,
                        radius,
                        right_color,
                        common,
                        component_grid.labels,
                        component,
                    )
                left_colors = next_left_colors
        return output

    averages, has_surface, blocks_high, blocks_wide = prepare_grid(
        array, config.block_size, common, rng
    )
    height, width, _ = array.shape
    output = array.copy()
    radius = config.block_size * config.circle_ratio / 4.0

    for block_y in range(blocks_high):
        left_color = None
        for block_x in range(blocks_wide):
            if not has_surface[block_y, block_x]:
                left_color = None
                continue

            y0 = block_y * config.block_size
            y1 = min((block_y + 1) * config.block_size, height)
            x0 = block_x * config.block_size
            x1 = min((block_x + 1) * config.block_size, width)
            center_x = (x0 + x1) / 2.0
            center_y = (y0 + y1) / 2.0
            own_average = averages[block_y, block_x]

            if left_color is None:
                left_color = own_average

            if (
                block_x + 1 < blocks_wide
                and has_surface[block_y, block_x + 1]
            ):
                right_color = interpolate_hsv(
                    own_average, averages[block_y, block_x + 1], 0.5
                )
            else:
                right_color = own_average

            paint_circle(
                output, array, x0, center_y, radius, left_color, common
            )
            paint_circle(
                output, array, center_x, center_y, radius, own_average, common
            )
            paint_circle(
                output, array, x1, center_y, radius, right_color, common
            )
            left_color = right_color

    return output
