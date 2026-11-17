"""Batch processing independent of command-line parsing."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
import ctypes
import hashlib
import os
from pathlib import Path
import time
from typing import Any
from uuid import uuid4

from normal_blobs import __version__
from normal_blobs.image_io import (
    capture_padding_snapshot,
    commit_staged_image,
    discover_pngs,
    inspect_png,
    load_normal_image,
    repair_input_normals,
    stage_normal_image,
    validate_padding_preserved,
)
from normal_blobs.manifest import (
    MANIFEST_NAME,
    MANIFEST_SCHEMA_VERSION,
    new_run_id,
    option_values,
    runtime_values,
    timestamp_now,
    write_manifest_atomic,
)
from normal_blobs.models import AlgorithmSpec, CommonOptions, RandomStreams
from normal_blobs.resources import (
    MIB,
    available_system_memory_bytes,
    format_bytes,
    no_effect_resource_estimate,
    safe_cpu_budget_bytes,
)

ALLOWED_SIZES = (1024, 2048, 4096)
ERROR_LOG_NAME = "processing_errors.log"
ERROR_LOG_ARCHIVE_NAME = "processing_errors.previous.log"
MAX_ERROR_LOG_BYTES = 5 * MIB
LOG_LOCK_TIMEOUT_SECONDS = 5.0
STALE_LOG_LOCK_SECONDS = 60.0


@dataclass(frozen=True)
class BatchOptions:
    inputs: list[Path]
    output_dir: Path
    suffix: str
    overwrite: bool
    delete_source: bool
    seed: int | None
    rng_mode: str
    resolution_filter: int | None
    cpu_memory_limit_bytes: int | None
    require_output: bool
    seed_scope: str


@dataclass(frozen=True)
class BatchResult:
    processed: int
    skipped: int
    failed: int
    warnings: int
    manifest_path: Path


@dataclass(frozen=True)
class SourceFingerprint:
    """Filesystem identity used to detect queue-file replacement."""

    device: int
    inode: int
    size: int
    modified_ns: int


def _lock_owner_pid(lock_path: Path) -> int | None:
    """Read the optional owner PID written into an issue-log lock."""

    try:
        first_line = lock_path.read_text(encoding="ascii").splitlines()[0]
        key, value = first_line.split("=", 1)
        if key != "pid":
            return None
        pid = int(value)
    except (OSError, IndexError, ValueError):
        return None
    return pid if pid > 0 else None


def _process_is_alive(pid: int) -> bool:
    """Return conservatively whether a process ID is still running."""

    if os.name == "nt":
        # os.kill(pid, 0) is not a non-destructive probe on Windows: the
        # Windows implementation can route it through TerminateProcess.
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        process_query_limited_information = 0x1000
        error_invalid_parameter = 87
        error_not_found = 1168
        kernel32.OpenProcess.argtypes = [
            ctypes.c_uint32,
            ctypes.c_int,
            ctypes.c_uint32,
        ]
        kernel32.OpenProcess.restype = ctypes.c_void_p
        kernel32.GetExitCodeProcess.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_ulong),
        ]
        kernel32.GetExitCodeProcess.restype = ctypes.c_int
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel32.CloseHandle.restype = ctypes.c_int
        handle = kernel32.OpenProcess(
            process_query_limited_information,
            False,
            pid,
        )
        if not handle:
            error_code = ctypes.get_last_error()
            if error_code in (error_invalid_parameter, error_not_found):
                return False
            # Access-denied and unknown errors are treated as live so a
            # potentially active writer's lock is never reclaimed blindly.
            return True
        try:
            exit_code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(
                handle, ctypes.byref(exit_code)
            ):
                return True
            return exit_code.value == 259  # STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)

    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # The process exists but belongs to another user/session.
        return True
    except OSError:
        # An unknown platform error is safer to treat as live: deleting the
        # lock could allow two writers to rotate/append the same log.
        return True
    return True


def _reclaim_stale_log_lock(lock_path: Path) -> bool:
    """Remove a stale lock only when its recorded owner is not alive."""

    try:
        lock_age = time.time() - lock_path.stat().st_mtime
    except FileNotFoundError:
        return False
    if lock_age <= STALE_LOG_LOCK_SECONDS:
        return False

    owner_pid = _lock_owner_pid(lock_path)
    if owner_pid is not None and _process_is_alive(owner_pid):
        return False
    claim_path = lock_path.with_name(
        f".{lock_path.name}.{uuid4().hex}.reclaim"
    )
    try:
        # Rename is the ownership claim. If another waiter wins first, this
        # raises FileNotFoundError and cannot delete that waiter's new lock.
        os.replace(lock_path, claim_path)
    except FileNotFoundError:
        return False
    try:
        claim_path.unlink(missing_ok=True)
    except OSError:
        # The active lock path is already free; a cleanup failure must not
        # cause this caller to delete or overwrite a newer lock.
        pass
    return True


def write_batch_manifest(
    *,
    path: Path,
    run_id: str,
    started_at: str,
    spec: AlgorithmSpec,
    algorithm_config: Any,
    common: CommonOptions,
    batch: BatchOptions,
    discovered: int,
    processed: int,
    skipped: int,
    failed: int,
    warnings: int,
    files: list[dict[str, Any]],
) -> None:
    """Build and atomically publish the final batch summary."""

    require_output_failure = batch.require_output and processed == 0
    exit_code = 1 if failed or warnings or require_output_failure else 0
    if exit_code and processed:
        outcome = "partial"
    elif exit_code:
        outcome = "failed"
    elif processed == 0:
        outcome = "no_output"
    elif skipped:
        outcome = "partial"
    else:
        outcome = "success"

    payload = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "tool": {
            "name": "procedural_normal_blobs.py",
            "version": __version__,
        },
        "runtime": runtime_values(),
        "run": {
            "id": run_id,
            "started_at": started_at,
            "finished_at": timestamp_now(),
            "outcome": outcome,
            "expected_exit_code": exit_code,
        },
        "algorithm": {
            "name": spec.name,
            "options": option_values(algorithm_config),
        },
        "shared_options": option_values(common),
        "batch_options": {
            "inputs": [str(path.resolve()) for path in batch.inputs],
            "output_dir": str(batch.output_dir.resolve()),
            "suffix": batch.suffix,
            "overwrite": batch.overwrite,
            "delete_source": batch.delete_source,
            "seed": batch.seed,
            "seed_scope": batch.seed_scope,
            "rng_mode": batch.rng_mode,
            "resolution": batch.resolution_filter,
            "cpu_memory_limit_bytes": batch.cpu_memory_limit_bytes,
            "require_output": batch.require_output,
        },
        "counts": {
            "discovered": discovered,
            "processed": processed,
            "skipped": skipped,
            "failed": failed,
            "warnings": warnings,
        },
        "files": files,
    }
    write_manifest_atomic(path, payload)


def fit_config_to_cpu_budget(
    spec: AlgorithmSpec,
    height: int,
    width: int,
    algorithm_config: Any,
    cpu_budget: int,
) -> tuple[Any, Any, int | None]:
    """Reduce chunk rows until the estimate fits without changing pixels."""

    adjusted_config = algorithm_config
    estimate = spec.estimate_resources(height, width, adjusted_config)
    original_chunk_rows = getattr(adjusted_config, "chunk_rows", None)
    chunk_rows = original_chunk_rows
    while (
        estimate.cpu_bytes > cpu_budget
        and isinstance(chunk_rows, int)
        and chunk_rows > 1
    ):
        chunk_rows = max(1, chunk_rows // 2)
        adjusted_config = replace(
            adjusted_config, chunk_rows=chunk_rows
        )
        estimate = spec.estimate_resources(
            height, width, adjusted_config
        )
    if chunk_rows == original_chunk_rows:
        original_chunk_rows = None
    return adjusted_config, estimate, original_chunk_rows


def append_issue(
    log_path: Path, source: Path, category: str, message: str
) -> None:
    """Append one timestamped queue issue without replacing earlier runs."""

    lock_path = log_path.with_name(f".{log_path.name}.lock")
    descriptor: int | None = None
    deadline = time.monotonic() + LOG_LOCK_TIMEOUT_SECONDS
    while descriptor is None:
        try:
            descriptor = os.open(
                lock_path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
            )
        except FileExistsError:
            if _reclaim_stale_log_lock(lock_path):
                continue
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"timed out waiting for issue-log lock {lock_path}"
                )
            time.sleep(0.02)
    try:
        os.write(descriptor, f"pid={os.getpid()}\n".encode("ascii"))
        if (
            log_path.exists()
            and log_path.stat().st_size >= MAX_ERROR_LOG_BYTES
        ):
            archive = log_path.with_name(ERROR_LOG_ARCHIVE_NAME)
            os.replace(log_path, archive)
        timestamp = datetime.now().astimezone().isoformat(
            timespec="seconds"
        )
        safe_source = sanitize_log_field(source)
        safe_category = sanitize_log_field(category)
        safe_message = sanitize_log_field(message)
        with log_path.open("a", encoding="utf-8") as log:
            log.write(
                f"{timestamp}\t{safe_category}\t{safe_source}\t"
                f"{safe_message}\n"
            )
            log.flush()
            os.fsync(log.fileno())
    finally:
        os.close(descriptor)
        lock_path.unlink(missing_ok=True)


def safe_append_issue(
    log_path: Path,
    source: Path,
    category: str,
    message: str,
) -> bool:
    """Attempt to log an issue without aborting the remaining queue."""

    try:
        append_issue(log_path, source, category, message)
    except OSError as error:
        print(f"Could not write issue log {log_path}: {error}")
        return False
    return True


def sanitize_log_field(value: object) -> str:
    """Keep one issue in one tab-separated log record."""

    return (
        str(value)
        .replace("\r", "\\r")
        .replace("\n", "\\n")
        .replace("\t", "\\t")
    )


def sha256_file(path: Path, chunk_size: int = MIB) -> str:
    """Return a bounded-memory SHA-256 digest for an on-disk artifact."""

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def source_fingerprint(source: Path) -> SourceFingerprint:
    """Capture identity and modification information for one queue file."""

    stat = source.stat()
    return SourceFingerprint(
        device=stat.st_dev,
        inode=stat.st_ino,
        size=stat.st_size,
        modified_ns=stat.st_mtime_ns,
    )


def require_unchanged_source(
    source: Path,
    expected: SourceFingerprint,
    phase: str,
) -> None:
    """Reject a source that was replaced or modified during processing."""

    if source_fingerprint(source) != expected:
        raise RuntimeError(
            f"source changed {phase}; output was not committed for this file"
        )


def source_identity_record(
    fingerprint: SourceFingerprint,
    sha256: str,
) -> dict[str, int | str]:
    """Return stable input identity fields for the JSON manifest."""

    return {
        "bytes": fingerprint.size,
        "modified_ns": fingerprint.modified_ns,
        "device": fingerprint.device,
        "inode": fingerprint.inode,
        "sha256": sha256,
    }


def restore_pending_source(
    pending: Path,
    source: Path,
    run_id: str,
) -> str:
    """Restore a failed delete claim without overwriting another queue file."""

    if not pending.exists():
        return "the pending source was no longer present for recovery"
    if not source.exists():
        os.replace(pending, source)
        return f"source was restored to {source}"
    recovery = source.with_name(
        f"{source.stem}.delete-recovery-{run_id}{source.suffix}"
    )
    os.replace(pending, recovery)
    return (
        f"a new file already occupied {source}; the undeleted source was "
        f"recovered as {recovery}"
    )


def consume_unchanged_source(
    source: Path,
    expected: SourceFingerprint,
    run_id: str,
) -> None:
    """Atomically claim, verify, and delete exactly the processed source."""

    require_unchanged_source(source, expected, "before source deletion")
    pending = source.with_name(
        f".{source.name}.{run_id}.delete-pending"
    )
    os.replace(source, pending)
    try:
        if source_fingerprint(pending) != expected:
            raise RuntimeError(
                "source changed while it was being claimed for deletion"
            )
        pending.unlink()
    except Exception as error:
        try:
            recovery_message = restore_pending_source(
                pending, source, run_id
            )
        except OSError as recovery_error:
            recovery_message = (
                f"automatic recovery also failed: {recovery_error}; "
                f"preserve {pending} manually"
            )
        raise RuntimeError(
            f"{error}; {recovery_message}"
        ) from error


def stable_file_seed(seed: int, source: Path) -> int:
    """Derive an order-independent 32-bit seed from the configured seed/name."""

    payload = f"{seed}\0{source.name.casefold()}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:4], "little")


def acquire_destination_lock(destination: Path) -> tuple[int, Path]:
    """Create an exclusive per-destination lock for concurrent batch safety."""

    lock_path = destination.with_name(f".{destination.name}.lock")
    try:
        descriptor = os.open(
            lock_path,
            os.O_CREAT | os.O_EXCL | os.O_WRONLY,
        )
    except FileExistsError as error:
        raise FileExistsError(
            f"{destination} is locked by another run; if no run is active, "
            f"remove the stale lock {lock_path}"
        ) from error
    try:
        os.write(descriptor, f"pid={os.getpid()}\n".encode("ascii"))
    except Exception:
        os.close(descriptor)
        lock_path.unlink(missing_ok=True)
        raise
    return descriptor, lock_path


def release_destination_lock(
    descriptor: int | None,
    lock_path: Path | None,
) -> str | None:
    """Release a destination lock and return cleanup problems."""

    errors = []
    if descriptor is not None:
        try:
            os.close(descriptor)
        except OSError as error:
            errors.append(f"could not close destination lock: {error}")
    if lock_path is not None:
        try:
            lock_path.unlink(missing_ok=True)
        except OSError as error:
            errors.append(f"could not remove destination lock {lock_path}: {error}")
    return "; ".join(errors) if errors else None


def compatible_size_message(
    width: int, height: int, requested_size: int | None
) -> str | None:
    """Return why dimensions should be skipped, or None when accepted."""

    actual = f"{width}x{height}"
    allowed = ", ".join(f"{size}x{size}" for size in ALLOWED_SIZES)
    if width != height or width not in ALLOWED_SIZES:
        return f"incompatible size {actual}; allowed sizes are {allowed}"
    if requested_size is not None and width != requested_size:
        return (
            f"size {actual} does not match requested filter "
            f"{requested_size}x{requested_size}"
        )
    return None


def run_batch(
    spec: AlgorithmSpec,
    algorithm_config: Any,
    common: CommonOptions,
    batch: BatchOptions,
) -> BatchResult:
    """Process discovered inputs, isolating failures to individual files."""

    started_at = timestamp_now()
    run_id = new_run_id()
    try:
        sources = discover_pngs(batch.inputs)
    except (OSError, ValueError) as error:
        batch.output_dir.mkdir(parents=True, exist_ok=True)
        log_path = batch.output_dir / ERROR_LOG_NAME
        manifest_path = batch.output_dir / MANIFEST_NAME
        records = []
        for location in batch.inputs:
            safe_append_issue(
                log_path, location, "PREFLIGHT_ERROR", str(error)
            )
            records.append(
                {
                    "source": str(location.resolve()),
                    "destination": None,
                    "status": "failed",
                    "category": "PREFLIGHT_ERROR",
                    "message": str(error),
                }
            )
        try:
            write_batch_manifest(
                path=manifest_path,
                run_id=run_id,
                started_at=started_at,
                spec=spec,
                algorithm_config=algorithm_config,
                common=common,
                batch=batch,
                discovered=0,
                processed=0,
                skipped=0,
                failed=1,
                warnings=0,
                files=records,
            )
        except Exception as manifest_error:
            print(
                f"Could not write export summary {manifest_path}: "
                f"{manifest_error}"
            )
        raise
    batch.output_dir.mkdir(parents=True, exist_ok=True)
    log_path = batch.output_dir / ERROR_LOG_NAME
    manifest_path = batch.output_dir / MANIFEST_NAME

    def fail_preflight(message: str, related: list[Path]) -> None:
        records = []
        for source in related:
            safe_append_issue(
                log_path, source, "PREFLIGHT_ERROR", message
            )
            records.append(
                {
                    "source": str(source.resolve()),
                    "destination": None,
                    "status": "failed",
                    "category": "PREFLIGHT_ERROR",
                    "message": message,
                }
            )
        try:
            write_batch_manifest(
                path=manifest_path,
                run_id=run_id,
                started_at=started_at,
                spec=spec,
                algorithm_config=algorithm_config,
                common=common,
                batch=batch,
                discovered=len(sources),
                processed=0,
                skipped=0,
                failed=1,
                warnings=0,
                files=records,
            )
        except Exception as manifest_error:
            print(
                f"Could not write export summary {manifest_path}: "
                f"{manifest_error}"
            )
        raise ValueError(message)

    if not sources:
        locations = ", ".join(str(path) for path in batch.inputs)
        print(f"No PNG files found in: {locations}")
        file_records = []
        for location in batch.inputs:
            message = "no PNG files were discovered"
            safe_append_issue(
                log_path,
                location,
                "NO_INPUT",
                message,
            )
            file_records.append(
                {
                    "source": str(location.resolve()),
                    "destination": None,
                    "status": "no_input",
                    "category": "NO_INPUT",
                    "message": message,
                }
            )
        try:
            write_batch_manifest(
                path=manifest_path,
                run_id=run_id,
                started_at=started_at,
                spec=spec,
                algorithm_config=algorithm_config,
                common=common,
                batch=batch,
                discovered=0,
                processed=0,
                skipped=0,
                failed=0,
                warnings=0,
                files=file_records,
            )
        except Exception as error:
            safe_append_issue(
                log_path,
                batch.output_dir,
                "MANIFEST_WRITE_FAILED",
                str(error),
            )
            print(f"Could not write export summary {manifest_path}: {error}")
            return BatchResult(
                processed=0,
                skipped=0,
                failed=1,
                warnings=0,
                manifest_path=manifest_path,
            )
        print(f"Export summary: {manifest_path}")
        return BatchResult(
            processed=0,
            skipped=0,
            failed=0,
            warnings=0,
            manifest_path=manifest_path,
        )

    output_directory = batch.output_dir.resolve()
    source_keys = {
        str(source.resolve()).casefold(): source for source in sources
    }
    overlapping_sources = [
        source
        for source in sources
        if source.resolve().parent == output_directory
    ]
    if overlapping_sources:
        names = ", ".join(source.name for source in overlapping_sources[:3])
        fail_preflight(
            "input PNGs cannot reside in the output directory because an "
            f"export could overwrite a queued source: {names}",
            overlapping_sources,
        )

    destinations: dict[str, tuple[Path, Path]] = {}
    for source in sources:
        destination = batch.output_dir / f"{source.stem}{batch.suffix}.png"
        destination_key = str(destination.resolve()).casefold()
        overlapping_source = source_keys.get(destination_key)
        if overlapping_source is not None:
            fail_preflight(
                f"output {destination} overlaps queued source "
                f"{overlapping_source}; choose a separate output directory "
                "or suffix",
                [source, overlapping_source],
            )
        existing = destinations.get(destination_key)
        if existing is not None:
            existing_source, existing_destination = existing
            fail_preflight(
                "output filename collision: "
                f"{existing_source} and {source} both map to "
                f"{existing_destination}. Use distinct source filenames, "
                "different runs/output folders, or a different --suffix.",
                [existing_source, source],
            )
        destinations[destination_key] = (source, destination)

    batch_rng = RandomStreams(batch.seed, batch.rng_mode)
    processed = 0
    skipped = 0
    failed = 0
    warning_count = 0
    file_records: list[dict[str, Any]] = []

    for source in sources:
        destination = batch.output_dir / f"{source.stem}{batch.suffix}.png"
        file_record: dict[str, Any] = {
            "source": str(source.resolve()),
            "destination": str(destination.resolve()),
        }
        lock_descriptor: int | None = None
        lock_path: Path | None = None
        expected_source: SourceFingerprint | None = None
        try:
            expected_source = source_fingerprint(source)
            width, height = inspect_png(source)
            file_record["dimensions"] = {
                "width": width,
                "height": height,
            }
            size_issue = compatible_size_message(
                width, height, batch.resolution_filter
            )
            if size_issue is not None:
                skipped += 1
                safe_append_issue(
                    log_path, source, "SKIPPED_SIZE", size_issue
                )
                file_record.update(
                    {
                        "status": "skipped",
                        "category": "SKIPPED_SIZE",
                        "message": size_issue,
                    }
                )
                file_records.append(file_record)
                print(f"Skipped {source}: {size_issue}")
                continue

            available_memory = available_system_memory_bytes()
            cpu_budget = safe_cpu_budget_bytes(
                available_memory, batch.cpu_memory_limit_bytes
            )
            if common.blend_strength == 0:
                file_config = algorithm_config
                estimate = no_effect_resource_estimate(height, width)
                original_chunk_rows = None
            else:
                file_config, estimate, original_chunk_rows = (
                    fit_config_to_cpu_budget(
                        spec,
                        height,
                        width,
                        algorithm_config,
                        cpu_budget,
                    )
                )
            estimate = replace(
                estimate,
                cpu_bytes=estimate.cpu_bytes + height * width,
            )
            if original_chunk_rows is not None:
                print(
                    f"Reduced chunk rows for {source.name}: "
                    f"{original_chunk_rows} -> {file_config.chunk_rows} "
                    f"to fit the {format_bytes(cpu_budget)} CPU budget"
                )
            file_record["resources"] = {
                "available_cpu_bytes": available_memory,
                "cpu_budget_bytes": cpu_budget,
                "estimated_peak_cpu_bytes": estimate.cpu_bytes,
                "chunk_rows_requested": getattr(
                    algorithm_config, "chunk_rows", None
                ),
                "chunk_rows_used": getattr(file_config, "chunk_rows", None),
                "processing_mode": (
                    "validation_and_export_only"
                    if common.blend_strength == 0
                    else "algorithm"
                ),
            }
            if estimate.cpu_bytes > cpu_budget:
                available_text = (
                    format_bytes(available_memory)
                    if available_memory is not None
                    else "unknown"
                )
                resource_issue = (
                    f"estimated CPU peak {format_bytes(estimate.cpu_bytes)} "
                    f"exceeds safe CPU budget {format_bytes(cpu_budget)} "
                    f"({available_text} currently available)"
                )
                skipped += 1
                safe_append_issue(
                    log_path,
                    source,
                    "SKIPPED_RESOURCE_LIMIT",
                    resource_issue,
                )
                file_record.update(
                    {
                        "status": "skipped",
                        "category": "SKIPPED_RESOURCE_LIMIT",
                        "message": resource_issue,
                    }
                )
                file_records.append(file_record)
                print(f"Skipped {source}: {resource_issue}")
                continue

            lock_descriptor, lock_path = acquire_destination_lock(
                destination
            )
            if source.resolve() == destination.resolve():
                raise ValueError("source and destination resolve to the same file")
            if destination.exists() and not batch.overwrite:
                raise FileExistsError(
                    f"{destination} already exists (use --overwrite to replace it)"
                )

            source_sha256 = sha256_file(source)
            require_unchanged_source(
                source, expected_source, "before it was loaded"
            )
            image = load_normal_image(source)
            require_unchanged_source(
                source, expected_source, "while it was being loaded"
            )
            loaded_source_sha256 = sha256_file(source)
            if loaded_source_sha256 != source_sha256:
                raise RuntimeError(
                    "source contents changed while it was being loaded; "
                    "output was not committed for this file"
                )
            file_record["input_artifact"] = source_identity_record(
                expected_source, source_sha256
            )
            if image.shape[:2] != (height, width):
                raise RuntimeError(
                    "source dimensions changed after resource preflight"
                )
            repair_stats = repair_input_normals(
                image, common.black_threshold
            )
            if repair_stats.repaired_count:
                repair_message = (
                    f"repaired {repair_stats.repaired_count} of "
                    f"{repair_stats.surface_count} surface normal(s) "
                    f"({repair_stats.repaired_fraction:.2%}); observed "
                    f"lengths {repair_stats.minimum_length:.4f}.."
                    f"{repair_stats.maximum_length:.4f}"
                )
                safe_append_issue(
                    log_path,
                    source,
                    "INPUT_NORMALS_REPAIRED",
                    repair_message,
                )
                file_record.setdefault("notices", []).append(
                    {
                        "category": "INPUT_NORMALS_REPAIRED",
                        "message": repair_message,
                    }
                )
            padding_snapshot = capture_padding_snapshot(
                image,
                common.black_threshold,
            )
            if batch.seed_scope == "file":
                if batch.seed is None:
                    raise ValueError("file seed scope requires a seed")
                rng = RandomStreams(
                    stable_file_seed(batch.seed, source),
                    batch.rng_mode,
                )
            else:
                rng = batch_rng
            if common.blend_strength == 0:
                result = image
            else:
                result = spec.process(image, common, file_config, rng)
            require_unchanged_source(
                source, expected_source, "during processing"
            )
            validate_padding_preserved(
                padding_snapshot,
                result,
            )
            staged = stage_normal_image(
                result,
                destination,
                black_threshold=common.black_threshold,
                require_unit_normals=common.renormalize,
            )
            try:
                require_unchanged_source(
                    source, expected_source, "after export staging"
                )
                staged_source_sha256 = sha256_file(source)
                if staged_source_sha256 != source_sha256:
                    raise RuntimeError(
                        "source contents changed before export commit; "
                        "output was not committed for this file"
                    )
                saved_info = commit_staged_image(staged, destination)
            finally:
                staged.temporary_path.unlink(missing_ok=True)
            file_record["output_artifact"] = {
                "bytes": saved_info.byte_count,
                "sha256": saved_info.sha256,
                "format": "PNG",
                "mode": "RGB",
                "width": width,
                "height": height,
            }
            source_action = "preserved"
            source_changed_after_commit = False
            try:
                require_unchanged_source(
                    source, expected_source, "after export commit"
                )
                committed_source_sha256 = sha256_file(source)
                if committed_source_sha256 != source_sha256:
                    raise RuntimeError(
                        "source contents changed during export commit; "
                        "the committed output must be reviewed before use"
                    )
            except Exception:
                source_changed_after_commit = True
                source_action = "preserved_source_changed"
                warning_count += 1
                message = (
                    "source changed after the output was committed; the "
                    "output corresponds to the earlier source snapshot"
                )
                safe_append_issue(
                    log_path,
                    source,
                    "SOURCE_CHANGED_AFTER_COMMIT",
                    message,
                )
                file_record.setdefault("warnings", []).append(
                    {
                        "category": "SOURCE_CHANGED_AFTER_COMMIT",
                        "message": message,
                    }
                )
            if batch.delete_source and not source_changed_after_commit:
                try:
                    consume_unchanged_source(
                        source, expected_source, run_id
                    )
                    source_action = "consumed"
                except (OSError, RuntimeError) as error:
                    warning_count += 1
                    delete_message = (
                        "output was saved, but the source could not be "
                        f"safely consumed: {error}"
                    )
                    safe_append_issue(
                        log_path,
                        source,
                        "SOURCE_DELETE_FAILED",
                        delete_message,
                    )
                    file_record.setdefault("warnings", []).append(
                        {
                            "category": "SOURCE_DELETE_FAILED",
                            "message": delete_message,
                        }
                    )
                    source_action = "preserved_delete_failed"
        except Exception as error:
            failed += 1
            file_record.update(
                {
                    "status": "failed",
                    "category": "ERROR",
                    "message": str(error),
                }
            )
            file_records.append(file_record)
            safe_append_issue(log_path, source, "ERROR", str(error))
            print(f"Skipped {source}: {error}")
            continue
        finally:
            cleanup_issue = release_destination_lock(
                lock_descriptor, lock_path
            )
            if cleanup_issue is not None:
                warning_count += 1
                safe_append_issue(
                    log_path,
                    source,
                    "LOCK_CLEANUP_FAILED",
                    cleanup_issue,
                )
                file_record.setdefault("warnings", []).append(
                    {
                        "category": "LOCK_CLEANUP_FAILED",
                        "message": cleanup_issue,
                    }
                )
                print(f"Warning for {source}: {cleanup_issue}")

        processed += 1
        height, width, _ = result.shape
        has_warnings = bool(file_record.get("warnings"))
        file_record.update(
            {
                "status": "processed",
                "category": (
                    "PROCESSED_WITH_WARNINGS"
                    if has_warnings
                    else "PROCESSED"
                ),
                "message": (
                    "output saved with post-export warning(s)"
                    if has_warnings
                    else "output saved successfully"
                ),
                "source_action": source_action,
            }
        )
        file_records.append(file_record)
        print(
            f"{source.name} -> {destination} "
            f"({spec.name}; {width}x{height}; {batch.rng_mode} RNG; "
            f"source {source_action})"
        )

    if skipped or failed or warning_count:
        print(
            f"Batch complete: {processed} processed, {skipped} skipped, "
            f"{failed} failed, {warning_count} warning(s). "
            f"Details: {log_path}"
        )
    try:
        write_batch_manifest(
            path=manifest_path,
            run_id=run_id,
            started_at=started_at,
            spec=spec,
            algorithm_config=algorithm_config,
            common=common,
            batch=batch,
            discovered=len(sources),
            processed=processed,
            skipped=skipped,
            failed=failed,
            warnings=warning_count,
            files=file_records,
        )
    except Exception as error:
        failed += 1
        safe_append_issue(
            log_path,
            batch.output_dir,
            "MANIFEST_WRITE_FAILED",
            str(error),
        )
        print(f"Could not write export summary {manifest_path}: {error}")
        return BatchResult(
            processed=processed,
            skipped=skipped,
            failed=failed,
            warnings=warning_count,
            manifest_path=manifest_path,
        )
    print(f"Export summary: {manifest_path}")
    return BatchResult(
        processed=processed,
        skipped=skipped,
        failed=failed,
        warnings=warning_count,
        manifest_path=manifest_path,
    )
