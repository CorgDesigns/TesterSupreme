"""Color and normal-vector operations shared by the algorithms."""

from __future__ import annotations

import colorsys

import numpy as np
from numpy.typing import ArrayLike

from normal_blobs.models import ImageArray, RandomStreams


def surface_mask(array: ImageArray, black_threshold: float) -> np.ndarray:
    """Return pixels that contain surface data instead of black UV padding."""

    return array.sum(axis=-1) > black_threshold


def renormalize_pixels(
    array: ImageArray,
    fallback: ImageArray | None = None,
) -> ImageArray:
    """Restore unit length, using source normals when an average cancels."""

    vectors = (array / 255.0) * 2.0 - 1.0
    lengths = np.linalg.norm(vectors, axis=-1, keepdims=True)
    safe_lengths = np.where(lengths < 1e-6, 1.0, lengths)
    normalized = vectors / safe_lengths
    if fallback is not None:
        fallback_vectors = (fallback / 255.0) * 2.0 - 1.0
        fallback_lengths = np.linalg.norm(
            fallback_vectors, axis=-1, keepdims=True
        )
        safe_fallback_lengths = np.where(
            fallback_lengths < 1e-6, 1.0, fallback_lengths
        )
        normalized = np.where(
            lengths < 1e-6,
            fallback_vectors / safe_fallback_lengths,
            normalized,
        )
    return (normalized + 1.0) * 0.5 * 255.0


def tweak_color(
    rgb: ArrayLike,
    hue_shift: float,
    shade_shift: float,
    rng: RandomStreams,
) -> np.ndarray:
    """Randomly nudge hue/value to distinguish similar neighboring cells."""

    red, green, blue = np.clip(rgb, 0, 255) / 255.0
    hue, saturation, value = colorsys.rgb_to_hsv(red, green, blue)
    hue = (hue + rng.color_uniform(-hue_shift, hue_shift)) % 1.0
    value = float(
        np.clip(
            value
            + rng.color_uniform(-shade_shift, shade_shift) / 255.0,
            0.0,
            1.0,
        )
    )
    result = colorsys.hsv_to_rgb(hue, saturation, value)
    return np.asarray(result) * 255.0


def interpolate_hsv(rgb_a: ArrayLike, rgb_b: ArrayLike, amount: float) -> np.ndarray:
    """Blend two colors along the shortest path around the HSV hue wheel."""

    red_a, green_a, blue_a = np.clip(rgb_a, 0, 255) / 255.0
    red_b, green_b, blue_b = np.clip(rgb_b, 0, 255) / 255.0
    hue_a, saturation_a, value_a = colorsys.rgb_to_hsv(
        red_a, green_a, blue_a
    )
    hue_b, saturation_b, value_b = colorsys.rgb_to_hsv(
        red_b, green_b, blue_b
    )

    hue_delta = hue_b - hue_a
    if hue_delta > 0.5:
        hue_delta -= 1.0
    elif hue_delta < -0.5:
        hue_delta += 1.0

    hue = (hue_a + hue_delta * amount) % 1.0
    saturation = saturation_a + (saturation_b - saturation_a) * amount
    value = value_a + (value_b - value_a) * amount
    return np.asarray(colorsys.hsv_to_rgb(hue, saturation, value)) * 255.0
