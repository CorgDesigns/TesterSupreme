"""PNG loading, saving, and input discovery."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
from uuid import uuid4

import numpy as np
from PIL import Image

from normal_blobs.models import ImageArray

MAX_INPUT_REPAIR_FRACTION = 0.01
MIN_REPAIRABLE_NORMAL_LENGTH = 0.1
# The lowest possible RGB sum of an encoded unit vector is about 161.7
# before 8-bit quantization. Staying below 150 leaves room for quantization
# while preventing valid, strongly negative normals from becoming padding.
MAX_SAFE_BLACK_THRESHOLD = 150.0


def _fsync_directory(path: Path) -> None:
    """Best-effort durability barrier for a completed atomic rename."""

    # Windows does not support opening directories as fsync-able file
    # descriptors. The file itself is flushed below; POSIX additionally gets
    # the directory-entry durability barrier needed after os.replace().
    if os.name == "nt":
        return
    try:
        descriptor = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


@dataclass(frozen=True)
class NormalRepairStats:
    """Summary of automatic input-normal repairs."""

    surface_count: int
    repaired_count: int
    minimum_length: float
    maximum_length: float

    @property
    def repaired_fraction(self) -> float:
        if self.surface_count == 0:
            return 0.0
        return self.repaired_count / self.surface_count


@dataclass(frozen=True)
class SavedImageInfo:
    """Identity of the exact PNG bytes committed by an atomic save."""

    byte_count: int
    sha256: str


@dataclass(frozen=True)
class StagedImage:
    """A verified PNG waiting for an explicit atomic commit."""

    temporary_path: Path
    info: SavedImageInfo


@dataclass(frozen=True)
class PaddingSnapshot:
    """Compact masks and value digest for source padding before processing."""

    shape: tuple[int, int, int]
    chunk_rows: int
    packed_masks: tuple[bytes, ...]
    values_sha256: str


def load_normal_image(path: Path) -> ImageArray:
    """Load a PNG as RGB, rejecting any meaningful alpha information."""

    with Image.open(path) as image:
        if image.mode == "RGBA":
            alpha_minimum, alpha_maximum = image.getchannel("A").getextrema()
            if alpha_minimum != 255 or alpha_maximum != 255:
                raise ValueError(
                    "PNG alpha contains non-opaque values; only fully opaque "
                    "RGBA can be converted safely to RGB"
                )
        return np.asarray(image.convert("RGB"), dtype=np.float64)


def inspect_png(path: Path) -> tuple[int, int]:
    """Validate supported PNG storage and return its dimensions."""

    with Image.open(path) as image:
        if image.format != "PNG":
            raise ValueError(
                f"file has a .png extension but its actual format is "
                f"{image.format or 'unknown'}"
            )
        if getattr(image, "n_frames", 1) != 1:
            raise ValueError("animated PNGs are not supported")
        if "transparency" in image.info:
            raise ValueError("PNG transparency is not supported")
        size = image.size

    with path.open("rb") as stream:
        header = stream.read(26)
    if len(header) < 26 or header[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("invalid PNG header")
    bit_depth = header[24]
    color_type = header[25]
    if bit_depth != 8:
        raise ValueError(
            f"PNG bit depth is {bit_depth}; only 8-bit PNGs are supported"
        )
    if color_type not in (2, 6):
        raise ValueError(
            "PNG must use truecolor RGB or RGBA; "
            f"found PNG color type {color_type}"
        )
    return size


def validate_normal_image(
    array: ImageArray,
    black_threshold: float,
    require_unit_normals: bool,
    chunk_rows: int = 128,
    description: str = "normal output",
) -> None:
    """Reject corrupt output arrays using bounded temporary memory."""

    if not isinstance(array, np.ndarray):
        raise ValueError(f"{description} must be a NumPy array")
    if array.ndim != 3 or array.shape[2] != 3:
        raise ValueError(
            f"{description} must have shape (height, width, 3), got {array.shape}"
        )
    if array.shape[0] == 0 or array.shape[1] == 0:
        raise ValueError(f"{description} cannot be empty")
    if not np.issubdtype(array.dtype, np.number):
        raise ValueError(f"{description} must be numeric, got {array.dtype}")
    if chunk_rows < 1:
        raise ValueError("validation chunk_rows must be at least 1")

    invalid_count = 0
    minimum = np.inf
    maximum = -np.inf
    surface_count = 0
    non_unit_count = 0
    minimum_length = np.inf
    maximum_length = -np.inf
    for row_start in range(0, array.shape[0], chunk_rows):
        chunk = array[row_start : row_start + chunk_rows]
        finite = np.isfinite(chunk)
        invalid_count += int(finite.size - np.count_nonzero(finite))
        if not finite.all():
            continue

        minimum = min(minimum, float(chunk.min()))
        maximum = max(maximum, float(chunk.max()))
        surface = chunk.sum(axis=-1) > black_threshold
        surface_count += int(np.count_nonzero(surface))
        if require_unit_normals and np.any(surface):
            vectors = (chunk[surface] / 255.0) * 2.0 - 1.0
            lengths = np.linalg.norm(vectors, axis=-1)
            non_unit_count += int(
                np.count_nonzero((lengths < 0.95) | (lengths > 1.05))
            )
            minimum_length = min(minimum_length, float(lengths.min()))
            maximum_length = max(maximum_length, float(lengths.max()))

    if invalid_count:
        raise ValueError(
            f"{description} contains {invalid_count} non-finite value(s)"
        )

    tolerance = 1e-6
    if minimum < -tolerance or maximum > 255.0 + tolerance:
        raise ValueError(
            f"{description} values must remain in RGB range 0..255; "
            f"observed {minimum:g}..{maximum:g}"
        )

    if surface_count == 0:
        raise ValueError(f"{description} contains no surface-normal pixels")
    if require_unit_normals and non_unit_count:
        raise ValueError(
            f"{description} contains "
            f"{non_unit_count} non-unit surface normal(s); "
            f"observed lengths {minimum_length:.4f}.."
            f"{maximum_length:.4f}"
        )


def repair_input_normals(
    array: ImageArray,
    black_threshold: float,
    *,
    max_repair_fraction: float = MAX_INPUT_REPAIR_FRACTION,
    minimum_repairable_length: float = MIN_REPAIRABLE_NORMAL_LENGTH,
    chunk_rows: int = 128,
) -> NormalRepairStats:
    """Repair a small number of non-unit input normals in bounded chunks."""

    validate_normal_image(
        array,
        black_threshold,
        require_unit_normals=False,
        chunk_rows=chunk_rows,
        description="input normal map",
    )
    surface_count = 0
    repair_count = 0
    unsafe_count = 0
    minimum_length = np.inf
    maximum_length = -np.inf

    for row_start in range(0, array.shape[0], chunk_rows):
        chunk = array[row_start : row_start + chunk_rows]
        surface = chunk.sum(axis=-1) > black_threshold
        if not np.any(surface):
            continue
        vectors = (chunk[surface] / 255.0) * 2.0 - 1.0
        lengths = np.linalg.norm(vectors, axis=-1)
        invalid = (lengths < 0.95) | (lengths > 1.05)
        surface_count += len(lengths)
        repair_count += int(np.count_nonzero(invalid))
        unsafe_count += int(
            np.count_nonzero(lengths < minimum_repairable_length)
        )
        minimum_length = min(minimum_length, float(lengths.min()))
        maximum_length = max(maximum_length, float(lengths.max()))

    stats = NormalRepairStats(
        surface_count=surface_count,
        repaired_count=repair_count,
        minimum_length=minimum_length,
        maximum_length=maximum_length,
    )
    if unsafe_count:
        raise ValueError(
            "input normal map contains "
            f"{unsafe_count} near-zero surface normal(s) below repairable "
            f"length {minimum_repairable_length:g}"
        )
    if stats.repaired_fraction > max_repair_fraction:
        raise ValueError(
            "input normal map requires repair for "
            f"{repair_count} of {surface_count} surface normal(s) "
            f"({stats.repaired_fraction:.2%}), exceeding the safe "
            f"{max_repair_fraction:.2%} limit; observed lengths "
            f"{minimum_length:.4f}..{maximum_length:.4f}"
        )
    if repair_count == 0:
        return stats

    for row_start in range(0, array.shape[0], chunk_rows):
        chunk = array[row_start : row_start + chunk_rows]
        flat = chunk.reshape(-1, 3)
        surface = flat.sum(axis=-1) > black_threshold
        if not np.any(surface):
            continue
        pixels = flat[surface]
        vectors = (pixels / 255.0) * 2.0 - 1.0
        lengths = np.linalg.norm(vectors, axis=-1)
        invalid = (lengths < 0.95) | (lengths > 1.05)
        if not np.any(invalid):
            continue
        vectors[invalid] /= lengths[invalid, None]
        pixels[invalid] = (vectors[invalid] + 1.0) * 127.5
        flat[surface] = pixels

    validate_normal_image(
        array,
        black_threshold,
        require_unit_normals=True,
        chunk_rows=chunk_rows,
        description="repaired input normal map",
    )
    return stats


def capture_padding_snapshot(
    source: ImageArray,
    black_threshold: float,
    *,
    chunk_rows: int = 128,
) -> PaddingSnapshot:
    """Capture original padding without retaining another full RGB image."""

    digest = hashlib.sha256()
    packed_masks = []
    for row_start in range(0, source.shape[0], chunk_rows):
        source_chunk = source[row_start : row_start + chunk_rows]
        padding = source_chunk.sum(axis=-1) <= black_threshold
        packed_masks.append(
            np.packbits(padding.reshape(-1), bitorder="little").tobytes()
        )
        if np.any(padding):
            digest.update(
                np.ascontiguousarray(
                    source_chunk[padding],
                    dtype=np.float64,
                ).tobytes()
            )
    return PaddingSnapshot(
        shape=source.shape,
        chunk_rows=chunk_rows,
        packed_masks=tuple(packed_masks),
        values_sha256=digest.hexdigest(),
    )


def validate_padding_preserved(
    snapshot: PaddingSnapshot,
    result: ImageArray,
) -> None:
    """Refuse an export if processing changed any captured padding value."""

    if not isinstance(result, np.ndarray) or result.shape != snapshot.shape:
        actual_shape = getattr(result, "shape", None)
        raise ValueError(
            "processed result shape changed from "
            f"{snapshot.shape} to {actual_shape}"
        )
    digest = hashlib.sha256()
    mask_index = 0
    for row_start in range(0, result.shape[0], snapshot.chunk_rows):
        result_chunk = result[row_start : row_start + snapshot.chunk_rows]
        pixel_count = result_chunk.shape[0] * result_chunk.shape[1]
        packed = np.frombuffer(
            snapshot.packed_masks[mask_index], dtype=np.uint8
        )
        padding = np.unpackbits(
            packed,
            count=pixel_count,
            bitorder="little",
        ).reshape(result_chunk.shape[:2]).astype(bool)
        if np.any(padding):
            digest.update(
                np.ascontiguousarray(
                    result_chunk[padding],
                    dtype=np.float64,
                ).tobytes()
            )
        mask_index += 1
    if digest.hexdigest() != snapshot.values_sha256:
        raise ValueError(
            "algorithm changed one or more black-padding pixel values; "
            "export refused to prevent UV-island crossing"
        )


def stage_normal_image(
    array: ImageArray,
    path: Path,
    *,
    black_threshold: float = 10.0,
    require_unit_normals: bool = True,
) -> StagedImage:
    """Validate and stage an RGB PNG without replacing the destination."""

    validate_normal_image(array, black_threshold, require_unit_normals)

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.stem}.{uuid4().hex}.tmp{path.suffix}")
    try:
        pixels = np.empty(array.shape, dtype=np.uint8)
        for row_start in range(0, array.shape[0], 128):
            row_end = min(row_start + 128, array.shape[0])
            pixels[row_start:row_end] = np.clip(
                array[row_start:row_end], 0, 255
            ).astype(np.uint8)
        Image.fromarray(pixels, mode="RGB").save(temporary)
        with temporary.open("rb+") as encoded_file:
            encoded_file.flush()
            os.fsync(encoded_file.fileno())
        with Image.open(temporary) as encoded:
            if encoded.format != "PNG":
                raise ValueError(
                    f"temporary export format is {encoded.format or 'unknown'}, "
                    "expected PNG"
                )
            if encoded.mode != "RGB":
                raise ValueError(
                    f"temporary export mode is {encoded.mode}, expected RGB"
                )
            if encoded.size != (array.shape[1], array.shape[0]):
                raise ValueError(
                    f"temporary export size is {encoded.size}, expected "
                    f"{(array.shape[1], array.shape[0])}"
                )
            encoded.verify()
        digest = hashlib.sha256()
        with temporary.open("rb") as encoded_file:
            while chunk := encoded_file.read(1024**2):
                digest.update(chunk)
        saved_info = SavedImageInfo(
            byte_count=temporary.stat().st_size,
            sha256=digest.hexdigest(),
        )
        return StagedImage(temporary_path=temporary, info=saved_info)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def commit_staged_image(staged: StagedImage, path: Path) -> SavedImageInfo:
    """Atomically commit a previously verified staged PNG."""

    os.replace(staged.temporary_path, path)
    _fsync_directory(path.parent)
    return staged.info


def save_normal_image(
    array: ImageArray,
    path: Path,
    *,
    black_threshold: float = 10.0,
    require_unit_normals: bool = True,
) -> SavedImageInfo:
    """Validate and atomically save an RGB PNG, verifying it before commit."""

    staged = stage_normal_image(
        array,
        path,
        black_threshold=black_threshold,
        require_unit_normals=require_unit_normals,
    )
    try:
        return commit_staged_image(staged, path)
    finally:
        staged.temporary_path.unlink(missing_ok=True)


def discover_pngs(inputs: list[Path]) -> list[Path]:
    """Expand input files/directories into a stable, de-duplicated PNG list."""

    discovered: list[Path] = []
    seen: set[str] = set()

    for item in inputs:
        if not item.exists():
            raise FileNotFoundError(f"Input does not exist: {item}")

        if item.is_dir():
            candidates = sorted(
                (path for path in item.iterdir() if path.suffix.lower() == ".png"),
                key=lambda path: path.name.lower(),
            )
        elif item.is_file() and item.suffix.lower() == ".png":
            candidates = [item]
        else:
            raise ValueError(f"Input is not a PNG file or directory: {item}")

        for candidate in candidates:
            key = str(candidate.resolve()).casefold()
            if key not in seen:
                seen.add(key)
                discovered.append(candidate)

    return discovered
