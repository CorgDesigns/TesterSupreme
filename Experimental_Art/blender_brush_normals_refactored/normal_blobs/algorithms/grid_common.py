"""Shared grid calculations for the two block-based algorithms."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.ndimage import label as label_components

from normal_blobs.color import renormalize_pixels, surface_mask, tweak_color
from normal_blobs.models import CommonOptions, ImageArray, RandomStreams

MAX_SURFACE_COMPONENTS = 100_000


@dataclass
class ComponentGrid:
    """Block averages keyed by both grid position and UV island."""

    labels: np.ndarray
    averages: dict[tuple[int, int, int], np.ndarray]
    components_by_block: dict[tuple[int, int], np.ndarray]
    blocks_high: int
    blocks_wide: int


def prepare_component_grid(
    array: ImageArray,
    block_size: int,
    common: CommonOptions,
    rng: RandomStreams,
) -> ComponentGrid | None:
    """Build island-specific block averages, or None for one surface region."""

    surface = surface_mask(array, common.black_threshold)
    structure = np.asarray(
        [
            [0, 1, 0],
            [1, 1, 1],
            [0, 1, 0],
        ],
        dtype=np.uint8,
    )
    labels, component_count = label_components(
        surface, structure=structure
    )
    if component_count <= 1:
        return None
    if component_count > MAX_SURFACE_COMPONENTS:
        raise ValueError(
            f"surface mask contains {component_count} disconnected regions; "
            f"the safe maximum is {MAX_SURFACE_COMPONENTS}"
        )

    height, width, _ = array.shape
    blocks_high = (height + block_size - 1) // block_size
    blocks_wide = (width + block_size - 1) // block_size
    averages: dict[tuple[int, int, int], np.ndarray] = {}
    components_by_block: dict[tuple[int, int], np.ndarray] = {}
    for block_y in range(blocks_high):
        for block_x in range(blocks_wide):
            y0 = block_y * block_size
            y1 = min((block_y + 1) * block_size, height)
            x0 = block_x * block_size
            x1 = min((block_x + 1) * block_size, width)
            block_labels = labels[y0:y1, x0:x1]
            component_ids = np.unique(block_labels[block_labels > 0])
            if len(component_ids) == 0:
                continue
            components_by_block[(block_y, block_x)] = component_ids
            block = array[y0:y1, x0:x1]
            for component in component_ids:
                mask = block_labels == component
                averages[
                    (block_y, block_x, int(component))
                ] = block[mask].mean(axis=0)

    for block_y in range(blocks_high):
        for block_x in range(blocks_wide):
            for component in components_by_block.get(
                (block_y, block_x), ()
            ):
                key = (block_y, block_x, int(component))
                current = averages[key]
                for neighbor_y, neighbor_x in (
                    (block_y, block_x + 1),
                    (block_y + 1, block_x),
                ):
                    neighbor_key = (
                        neighbor_y,
                        neighbor_x,
                        int(component),
                    )
                    neighbor = averages.get(neighbor_key)
                    if neighbor is None:
                        continue
                    if (
                        np.linalg.norm(current - neighbor)
                        < common.similarity_threshold
                    ):
                        averages[neighbor_key] = tweak_color(
                            neighbor,
                            common.hue_tweak,
                            common.shade_tweak,
                            rng,
                        )

    return ComponentGrid(
        labels=labels,
        averages=averages,
        components_by_block=components_by_block,
        blocks_high=blocks_high,
        blocks_wide=blocks_wide,
    )


def compute_block_averages(
    array: ImageArray, block_size: int, black_threshold: float
) -> tuple[ImageArray, np.ndarray, int, int]:
    """Average non-padding pixels in every square grid block."""

    height, width, _ = array.shape
    blocks_high = (height + block_size - 1) // block_size
    blocks_wide = (width + block_size - 1) // block_size
    averages = np.zeros((blocks_high, blocks_wide, 3), dtype=np.float64)
    has_surface = np.zeros((blocks_high, blocks_wide), dtype=bool)

    for block_y in range(blocks_high):
        for block_x in range(blocks_wide):
            y0 = block_y * block_size
            y1 = min((block_y + 1) * block_size, height)
            x0 = block_x * block_size
            x1 = min((block_x + 1) * block_size, width)
            block = array[y0:y1, x0:x1]
            mask = surface_mask(block, black_threshold)
            if mask.any():
                averages[block_y, block_x] = block[mask].mean(axis=0)
                has_surface[block_y, block_x] = True

    return averages, has_surface, blocks_high, blocks_wide


def differentiate_grid_neighbors(
    averages: ImageArray,
    has_surface: np.ndarray,
    common: CommonOptions,
    rng: RandomStreams,
) -> ImageArray:
    """Nudge similar right/bottom neighbors once in grid traversal order."""

    blocks_high, blocks_wide = has_surface.shape
    for block_y in range(blocks_high):
        for block_x in range(blocks_wide):
            if not has_surface[block_y, block_x]:
                continue
            current = averages[block_y, block_x]
            for neighbor_y, neighbor_x in (
                (block_y, block_x + 1),
                (block_y + 1, block_x),
            ):
                if (
                    neighbor_y >= blocks_high
                    or neighbor_x >= blocks_wide
                    or not has_surface[neighbor_y, neighbor_x]
                ):
                    continue
                neighbor = averages[neighbor_y, neighbor_x]
                if np.linalg.norm(current - neighbor) < common.similarity_threshold:
                    averages[neighbor_y, neighbor_x] = tweak_color(
                        neighbor, common.hue_tweak, common.shade_tweak, rng
                    )
    return averages


def paint_circle(
    output: ImageArray,
    source: ImageArray,
    center_x: float,
    center_y: float,
    radius: float,
    color: np.ndarray,
    common: CommonOptions,
    component_labels: np.ndarray | None = None,
    component: int | None = None,
) -> None:
    """Blend one soft circle into output, preserving black UV padding."""

    height, width, _ = source.shape
    x0 = max(0, int(center_x - radius))
    x1 = min(width, int(center_x + radius) + 1)
    y0 = max(0, int(center_y - radius))
    y1 = min(height, int(center_y + radius) + 1)
    if x0 >= x1 or y0 >= y1:
        return

    region = source[y0:y1, x0:x1]
    mask = surface_mask(region, common.black_threshold)
    if component_labels is not None and component is not None:
        mask &= component_labels[y0:y1, x0:x1] == component
    if not mask.any():
        return

    yy, xx = np.mgrid[y0:y1, x0:x1]
    distance = np.sqrt((xx - center_x) ** 2 + (yy - center_y) ** 2)
    falloff = np.clip(1.0 - distance / radius, 0.0, 1.0)
    weight = (falloff * common.blend_strength * mask)[..., None]
    blended = region * (1.0 - weight) + color * weight
    if common.renormalize:
        normalized = renormalize_pixels(blended, region)
        blended = np.where(weight > 0, normalized, blended)

    previous = output[y0:y1, x0:x1]
    output[y0:y1, x0:x1] = np.where(mask[..., None], blended, previous)


def prepare_grid(
    array: ImageArray,
    block_size: int,
    common: CommonOptions,
    rng: RandomStreams,
) -> tuple[ImageArray, np.ndarray, int, int]:
    """Compute and differentiate the grid shared by both block algorithms."""

    height, width, _ = array.shape
    if block_size > min(height, width):
        raise ValueError(
            f"Block size {block_size} is larger than this image ({width}x{height})"
        )
    averages, has_surface, blocks_high, blocks_wide = compute_block_averages(
        array, block_size, common.black_threshold
    )
    differentiate_grid_neighbors(averages, has_surface, common, rng)
    return averages, has_surface, blocks_high, blocks_wide
