"""Machine-readable batch summary creation."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime
from importlib.metadata import PackageNotFoundError, version
import json
import os
import platform
from pathlib import Path
import tempfile
from typing import Any
from uuid import uuid4

MANIFEST_NAME = "export_summary.json"
MANIFEST_SCHEMA_VERSION = 2


def _fsync_directory(path: Path) -> None:
    """Best-effort durability barrier for an atomically replaced manifest."""

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


def timestamp_now() -> str:
    """Return a timezone-aware ISO-8601 timestamp."""

    return datetime.now().astimezone().isoformat(timespec="seconds")


def option_values(options: Any) -> dict[str, Any]:
    """Convert one dataclass configuration into JSON-compatible values."""

    if not is_dataclass(options) or isinstance(options, type):
        raise TypeError("manifest options must be a dataclass instance")
    return asdict(options)


def new_run_id() -> str:
    """Return an opaque identifier for one batch invocation."""

    return uuid4().hex


def runtime_values() -> dict[str, Any]:
    """Return environment versions needed to reproduce a batch."""

    dependencies: dict[str, str] = {}
    for distribution in ("numpy", "Pillow", "scipy"):
        try:
            dependencies[distribution] = version(distribution)
        except PackageNotFoundError:
            dependencies[distribution] = "not-installed"
        except Exception as error:
            dependencies[distribution] = (
                f"unavailable ({type(error).__name__})"
            )
    try:
        platform_description = platform.platform()
    except Exception as error:
        platform_description = f"unavailable ({type(error).__name__})"
    return {
        "python": platform.python_version(),
        "platform": platform_description,
        "process_id": os.getpid(),
        "dependencies": dependencies,
    }


def write_manifest_atomic(path: Path, payload: dict[str, Any]) -> None:
    """Write formatted JSON and atomically replace the previous manifest."""

    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as manifest:
            json.dump(
                payload,
                manifest,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            manifest.write("\n")
            manifest.flush()
            os.fsync(manifest.fileno())
        os.replace(temporary_path, path)
        _fsync_directory(path.parent)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise
