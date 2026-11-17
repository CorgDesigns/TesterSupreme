"""Portable resource checks used before large image allocations."""

from __future__ import annotations

import ctypes
import os
from pathlib import Path
import sys

from normal_blobs.models import ResourceEstimate

MIB = 1024**2
GIB = 1024**3
SYSTEM_MEMORY_FRACTION = 0.75
UNKNOWN_SYSTEM_BUDGET = 2 * GIB


def _read_positive_integer(path: Path) -> int | None:
    """Read one non-negative integer resource value, if available."""

    try:
        value = path.read_text(encoding="ascii").strip()
    except (OSError, UnicodeError):
        return None
    if not value or value == "max":
        return None
    try:
        parsed = int(value)
    except ValueError:
        return None
    return parsed if parsed >= 0 else None


def _cgroup_available_memory_bytes() -> int | None:
    """Return memory left in the current Linux cgroup, when discoverable."""

    if sys.platform == "win32":
        return None

    roots = [Path("/sys/fs/cgroup")]
    try:
        cgroup_lines = Path("/proc/self/cgroup").read_text(
            encoding="ascii"
        ).splitlines()
    except (OSError, UnicodeError):
        cgroup_lines = []

    for line in cgroup_lines:
        fields = line.split(":", 2)
        if len(fields) == 3 and fields[0] == "0":
            relative = fields[2].lstrip("/")
            if relative:
                roots.append(Path("/sys/fs/cgroup") / relative)

    limits: list[int] = []
    for root in roots:
        # cgroup v2
        limit = _read_positive_integer(root / "memory.max")
        current = _read_positive_integer(root / "memory.current")
        if limit is not None and current is not None:
            limits.append(max(0, limit - current))

        # cgroup v1, commonly mounted under /sys/fs/cgroup/memory.
        memory_root = root / "memory"
        limit = _read_positive_integer(memory_root / "memory.limit_in_bytes")
        current = _read_positive_integer(memory_root / "memory.usage_in_bytes")
        if limit is not None and current is not None:
            limits.append(max(0, limit - current))

    return min(limits) if limits else None


def available_system_memory_bytes() -> int | None:
    """Return currently available physical RAM without optional dependencies."""

    if sys.platform == "win32":
        class MemoryStatus(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = MemoryStatus()
        status.dwLength = ctypes.sizeof(status)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return int(status.ullAvailPhys)

    host_available: int | None = None
    meminfo = Path("/proc/meminfo")
    try:
        lines = meminfo.read_text(encoding="ascii").splitlines()
    except (OSError, UnicodeError):
        lines = []
    for line in lines:
        if line.startswith("MemAvailable:"):
            try:
                host_available = int(line.split()[1]) * 1024
            except (IndexError, ValueError):
                pass
            break

    cgroup_available = _cgroup_available_memory_bytes()
    if host_available is not None and cgroup_available is not None:
        return min(host_available, cgroup_available)
    if cgroup_available is not None:
        return cgroup_available
    if host_available is not None:
        return host_available

    try:
        pages = os.sysconf("SC_AVPHYS_PAGES")
        page_size = os.sysconf("SC_PAGE_SIZE")
    except (AttributeError, OSError, ValueError):
        return None
    return int(pages * page_size)


def safe_cpu_budget_bytes(
    available_bytes: int | None,
    configured_limit_bytes: int | None,
) -> int:
    """Reserve 25% of available RAM and honor a lower user limit."""

    if available_bytes is None:
        automatic_limit = UNKNOWN_SYSTEM_BUDGET
    else:
        automatic_limit = max(
            0, int(available_bytes * SYSTEM_MEMORY_FRACTION)
        )
    if configured_limit_bytes is None:
        return automatic_limit
    return min(automatic_limit, configured_limit_bytes)


def format_bytes(value: int) -> str:
    """Format resource sizes for logs and console messages."""

    if value >= GIB:
        return f"{value / GIB:.2f} GiB"
    return f"{value / MIB:.0f} MiB"


def grid_resource_estimate(
    height: int,
    width: int,
    bytes_per_pixel: int,
) -> ResourceEstimate:
    """Conservative peak estimate for block/grid algorithms."""

    pixels = height * width
    cpu_bytes = 64 * MIB + pixels * bytes_per_pixel
    return ResourceEstimate(cpu_bytes=int(cpu_bytes))


def no_effect_resource_estimate(
    height: int,
    width: int,
) -> ResourceEstimate:
    """Estimate load, validation, and export memory for a zero-strength run."""

    pixels = height * width
    return ResourceEstimate(cpu_bytes=int(64 * MIB + pixels * 40))
