"""Shared averaging, differentiation, and painting for irregular cells."""

from __future__ import annotations

import numpy as np
from scipy.ndimage import label as label_components
from scipy.spatial import cKDTree

from normal_blobs.color import renormalize_pixels, surface_mask, tweak_color
from normal_blobs.models import CommonOptions, ImageArray, RandomStreams

MAX_ISOLATED_CELLS = 1_000_000
MAX_SURFACE_COMPONENTS = 100_000
ISOLATED_KEY_SCRATCH_BYTES = 64 * 1024**2


def isolate_cells_across_padding(
    array: ImageArray,
    nearest_cell: np.ndarray,
    second_cell: np.ndarray,
    positions: np.ndarray,
    black_threshold: float,
    chunk_rows: int,
) -> tuple[np.ndarray, np.ndarray | None]:
    """Give every cell a stable island-specific ID across black padding."""

    surface = surface_mask(array, black_threshold)
    structure = np.asarray(
        [
            [0, 1, 0],
            [1, 1, 1],
            [0, 1, 0],
        ],
        dtype=np.uint8,
    )
    components, component_count = label_components(
        surface, structure=structure
    )
    if component_count <= 1:
        return positions, None
    if component_count > MAX_SURFACE_COMPONENTS:
        raise ValueError(
            f"surface mask contains {component_count} disconnected regions; "
            f"the safe maximum is {MAX_SURFACE_COMPONENTS}"
        )

    cell_count = len(positions)
    # Keep the key table in compact NumPy storage. A Python set of one million
    # boxed integers can consume tens of megabytes before the actual arrays
    # and temporary NumPy buffers are counted.
    observed_keys = np.empty(0, dtype=np.int64)
    for row_start in range(0, array.shape[0], chunk_rows):
        row_end = min(row_start + chunk_rows, array.shape[0])
        chunk_surface = surface[row_start:row_end]
        if not np.any(chunk_surface):
            continue
        component_values = components[row_start:row_end][chunk_surface]
        component_keys = component_values.astype(np.int64) * cell_count
        nearest_values = nearest_cell[row_start:row_end][chunk_surface]
        second_values = second_cell[row_start:row_end][chunk_surface]
        keys = np.concatenate(
            (
                component_keys + nearest_values,
                component_keys + second_values,
            )
        )
        observed_keys = np.union1d(observed_keys, np.unique(keys))
        if len(observed_keys) > MAX_ISOLATED_CELLS:
            raise ValueError(
                "surface fragmentation creates more than "
                f"{MAX_ISOLATED_CELLS} island-specific cells"
            )

    sorted_keys = observed_keys
    isolated_positions = positions[sorted_keys % cell_count]
    isolated_components = (sorted_keys // cell_count).astype(np.int32)

    for row_start in range(0, array.shape[0], chunk_rows):
        row_end = min(row_start + chunk_rows, array.shape[0])
        chunk_surface = surface[row_start:row_end]
        chunk_nearest = nearest_cell[row_start:row_end]
        chunk_second = second_cell[row_start:row_end]
        if not np.any(chunk_surface):
            chunk_nearest.fill(0)
            chunk_second.fill(0)
            continue
        component_values = components[row_start:row_end][chunk_surface]
        nearest_keys = (
            component_values.astype(np.int64) * cell_count
            + chunk_nearest[chunk_surface]
        )
        second_keys = (
            component_values.astype(np.int64) * cell_count
            + chunk_second[chunk_surface]
        )
        chunk_nearest[chunk_surface] = np.searchsorted(
            sorted_keys, nearest_keys
        )
        chunk_second[chunk_surface] = np.searchsorted(
            sorted_keys, second_keys
        )
        chunk_nearest[~chunk_surface] = 0
        chunk_second[~chunk_surface] = 0

    return isolated_positions, isolated_components


def differentiate_isolated_neighbors(
    positions: np.ndarray,
    components: np.ndarray | None,
    averages: ImageArray,
    has_surface: np.ndarray,
    common: CommonOptions,
    rng: RandomStreams,
) -> None:
    """Apply neighbor tweaks without querying cells from another UV island."""

    if components is None:
        differentiate_spatial_neighbors(
            positions, averages, has_surface, common, rng
        )
        return

    order = np.argsort(components, kind="stable")
    sorted_components = components[order]
    boundaries = np.flatnonzero(
        np.r_[True, sorted_components[1:] != sorted_components[:-1], True]
    )
    for start, end in zip(boundaries[:-1], boundaries[1:], strict=True):
        indices = order[start:end]
        component_averages = averages[indices].copy()
        differentiate_spatial_neighbors(
            positions[indices],
            component_averages,
            has_surface[indices],
            common,
            rng,
        )
        averages[indices] = component_averages


def keep_second_cells_inside_islands(
    nearest_cell: np.ndarray,
    nearest_distance: np.ndarray,
    second_cell: np.ndarray,
    second_distance: np.ndarray,
    has_surface: np.ndarray,
    chunk_rows: int,
) -> None:
    """Replace empty island-local second cells with the nearest cell."""

    height = nearest_cell.shape[0]
    for row_start in range(0, height, chunk_rows):
        row_end = min(row_start + chunk_rows, height)
        chunk_second = second_cell[row_start:row_end]
        missing_second = ~has_surface[chunk_second]
        chunk_second[missing_second] = nearest_cell[
            row_start:row_end
        ][missing_second]
        second_distance[row_start:row_end][missing_second] = (
            nearest_distance[row_start:row_end][missing_second]
        )


def compute_cell_averages(
    array: ImageArray,
    nearest_cell: np.ndarray,
    cell_count: int,
    black_threshold: float,
    chunk_rows: int | None = None,
) -> tuple[ImageArray, np.ndarray]:
    """Average all non-padding pixels assigned to each cell."""

    sums = np.zeros((cell_count, 3), dtype=np.float64)
    counts = np.zeros(cell_count, dtype=np.float64)
    height = array.shape[0]
    rows_per_chunk = chunk_rows or height

    for row_start in range(0, height, rows_per_chunk):
        row_end = min(row_start + rows_per_chunk, height)
        flat_pixels = array[row_start:row_end].reshape(-1, 3)
        flat_cells = nearest_cell[row_start:row_end].ravel()
        mask = flat_pixels.sum(axis=-1) > black_threshold
        valid_cells = flat_cells[mask]
        valid_pixels = flat_pixels[mask]
        counts += np.bincount(valid_cells, minlength=cell_count)
        for channel in range(3):
            sums[:, channel] += np.bincount(
                valid_cells,
                weights=valid_pixels[:, channel],
                minlength=cell_count,
            )

    has_surface = counts > 0
    safe_counts = np.where(has_surface, counts, 1)
    return sums / safe_counts[:, None], has_surface


def differentiate_spatial_neighbors(
    positions: np.ndarray,
    averages: ImageArray,
    has_surface: np.ndarray,
    common: CommonOptions,
    rng: RandomStreams,
    neighbor_count: int = 4,
) -> ImageArray:
    """Nudge similar averages associated with nearby seed positions."""

    cell_count = len(positions)
    tree = cKDTree(positions)
    query_count = min(neighbor_count + 1, cell_count)
    _, indices = tree.query(positions, k=query_count)
    if query_count == 1:
        indices = indices[:, None]

    for index in range(cell_count):
        if not has_surface[index]:
            continue
        for neighbor in indices[index][1:]:
            if neighbor <= index or not has_surface[neighbor]:
                continue
            if (
                np.linalg.norm(averages[index] - averages[neighbor])
                < common.similarity_threshold
            ):
                averages[neighbor] = tweak_color(
                    averages[neighbor],
                    common.hue_tweak,
                    common.shade_tweak,
                    rng,
                )
    return averages


def paint_cells(
    array: ImageArray,
    averages: ImageArray,
    nearest_cell: np.ndarray,
    nearest_distance: np.ndarray,
    second_cell: np.ndarray,
    second_distance: np.ndarray,
    edge_softness: float,
    common: CommonOptions,
    chunk_rows: int | None = None,
) -> ImageArray:
    """Fill irregular cells and softly blend their shared boundaries."""

    if common.blend_strength == 0:
        return array.copy()

    output = array.copy()
    height = array.shape[0]
    rows_per_chunk = chunk_rows or height

    for row_start in range(0, height, rows_per_chunk):
        row_end = min(row_start + rows_per_chunk, height)
        source = array[row_start:row_end]
        nearest = nearest_cell[row_start:row_end]
        second = second_cell[row_start:row_end]
        nearest_dist = nearest_distance[row_start:row_end]
        second_dist = second_distance[row_start:row_end]

        mask = surface_mask(source, common.black_threshold)
        primary_color = averages[nearest]
        secondary_color = averages[second]
        amount = (
            np.clip(
                1.0 - (second_dist - nearest_dist) / edge_softness,
                0.0,
                1.0,
            )
            * 0.5
        )
        target = (
            primary_color * (1.0 - amount[..., None])
            + secondary_color * amount[..., None]
        )
        weight = common.blend_strength * mask[..., None]
        blended = source * (1.0 - weight) + target * weight
        if common.renormalize:
            blended = renormalize_pixels(blended, source)
        output[row_start:row_end] = np.where(
            mask[..., None], blended, source
        )

    return output


def first_two_distinct(
    sorted_indices: np.ndarray, sorted_distances: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Select the closest cell and closest different cell for every pixel."""

    nearest_cell = sorted_indices[:, 0]
    nearest_distance = sorted_distances[:, 0]
    differs = sorted_indices != nearest_cell[:, None]
    has_second = differs.any(axis=1)
    second_position = np.argmax(differs, axis=1)
    rows = np.arange(len(sorted_indices))
    second_cell = np.where(
        has_second, sorted_indices[rows, second_position], nearest_cell
    )
    second_distance = np.where(
        has_second, sorted_distances[rows, second_position], nearest_distance
    )
    return nearest_cell, nearest_distance, second_cell, second_distance
