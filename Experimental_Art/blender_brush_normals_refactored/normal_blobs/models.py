"""Shared configuration and algorithm metadata."""

from __future__ import annotations

from argparse import ArgumentParser, Namespace
from collections.abc import Callable
from dataclasses import dataclass
import random
from typing import Any

import numpy as np
from numpy.typing import NDArray

ImageArray = NDArray[np.float64]


class RandomStreams:
    """Random-number streams supporting original and modern behavior.

    Legacy mode deliberately keeps NumPy geometry randomness separate from
    Python's color-tweak randomness, matching the original monolithic script.
    Modern mode uses one NumPy Generator for both.
    """

    def __init__(self, seed: int | None, mode: str) -> None:
        if mode == "legacy":
            self._numpy = np.random.RandomState(seed)
            self._color = random.Random(seed)
        elif mode == "modern":
            self._numpy = np.random.default_rng(seed)
            self._color = None
        else:
            raise ValueError(f"Unknown RNG mode: {mode!r}")

    def uniform(self, *args: Any, **kwargs: Any) -> Any:
        return self._numpy.uniform(*args, **kwargs)

    def color_uniform(self, low: float, high: float) -> float:
        if self._color is not None:
            return self._color.uniform(low, high)
        return float(self._numpy.uniform(low, high))


@dataclass(frozen=True)
class CommonOptions:
    """Options that affect every processing algorithm."""

    black_threshold: float
    blend_strength: float
    similarity_threshold: float
    hue_tweak: float
    shade_tweak: float
    renormalize: bool


@dataclass(frozen=True)
class ResourceEstimate:
    """Predicted peak allocation for one algorithm and input image."""

    cpu_bytes: int
    gpu_bytes: int | None = None


@dataclass(frozen=True)
class AlgorithmSpec:
    """Connect one algorithm module to the command-line dispatcher."""

    name: str
    summary: str
    description: str
    help_epilog: str
    add_arguments: Callable[[ArgumentParser], None]
    make_config: Callable[[Namespace], Any]
    process: Callable[[ImageArray, CommonOptions, Any, RandomStreams], ImageArray]
    estimate_resources: Callable[[int, int, Any], ResourceEstimate]
