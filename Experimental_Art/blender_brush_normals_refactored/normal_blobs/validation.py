"""Small argparse validation helpers."""

from __future__ import annotations

import argparse
import math


def integer_at_least(minimum: int):
    def parse(value: str) -> int:
        parsed = int(value)
        if parsed < minimum:
            raise argparse.ArgumentTypeError(f"must be at least {minimum}")
        return parsed

    return parse


def integer_in_range(minimum: int, maximum: int):
    def parse(value: str) -> int:
        parsed = int(value)
        if not minimum <= parsed <= maximum:
            raise argparse.ArgumentTypeError(
                f"must be between {minimum} and {maximum}"
            )
        return parsed

    return parse


def float_in_range(minimum: float, maximum: float):
    def parse(value: str) -> float:
        parsed = float(value)
        if not math.isfinite(parsed) or not minimum <= parsed <= maximum:
            raise argparse.ArgumentTypeError(
                f"must be a finite number between {minimum:g} and {maximum:g}"
            )
        return parsed

    return parse


def positive_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed) or parsed <= 0:
        raise argparse.ArgumentTypeError(
            "must be a finite number greater than 0"
        )
    return parsed


def non_negative_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed) or parsed < 0:
        raise argparse.ArgumentTypeError(
            "must be a finite number that is 0 or greater"
        )
    return parsed


def filename_suffix(value: str) -> str:
    invalid = '<>:"/\\|?*'
    if any(character in invalid or ord(character) < 32 for character in value):
        raise argparse.ArgumentTypeError(
            'cannot contain control characters or <>:"/\\|?*'
        )
    if value.endswith((" ", ".")):
        raise argparse.ArgumentTypeError(
            "cannot end with a space or period"
        )
    return value


def resolution_size(value: str) -> int | None:
    normalized = value.strip().lower().replace(chr(215), "x")
    if normalized in ("auto", "source"):
        return None
    for size in (1024, 2048, 4096):
        if normalized in (str(size), f"{size}x{size}"):
            return size
    raise argparse.ArgumentTypeError(
        "must be auto, 1024, 1024x1024, 2048, 2048x2048, "
        "4096, or 4096x4096"
    )
