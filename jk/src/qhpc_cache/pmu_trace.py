"""Optional hardware PMU instrumentation with graceful degradation.

Provides a capability-driven abstraction over hardware performance counters.
Falls back to NullPMUCollector on unsupported platforms (macOS, missing perf,
insufficient permissions).
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class PMUMetrics:
    """Container for raw PMU counter values from one scope."""
    cycles: float = 0.0
    instructions: float = 0.0
    cache_references: float = 0.0
    cache_misses: float = 0.0
    task_clock_ms: float = 0.0
    page_faults: float = 0.0
    context_switches: float = 0.0
    error: str = ""

    @property
    def ipc(self) -> float:
        return self.instructions / self.cycles if self.cycles > 0 else 0.0

    @property
    def miss_ratio(self) -> float:
        return self.cache_misses / self.cache_references if self.cache_references > 0 else 0.0

    def to_dict(self, prefix: str = "pmu_") -> Dict[str, Any]:
        return {
            f"{prefix}cycles": self.cycles,
            f"{prefix}instructions": self.instructions,
            f"{prefix}cache_references": self.cache_references,
            f"{prefix}cache_misses": self.cache_misses,
            f"{prefix}task_clock_ms": round(self.task_clock_ms, 4),
            f"{prefix}page_faults": self.page_faults,
            f"{prefix}context_switches": self.context_switches,
            f"{prefix}error": self.error,
        }


class PMUCollector(ABC):
    @property
    @abstractmethod
    def available(self) -> bool: ...

    @property
    @abstractmethod
    def backend_name(self) -> str: ...

    @abstractmethod
    def begin_scope(self, scope_name: str) -> None: ...

    @abstractmethod
    def end_scope(self) -> PMUMetrics: ...


class NullPMUCollector(PMUCollector):
    """Fallback collector that reports zero counters."""

    @property
    def available(self) -> bool:
        return False

    @property
    def backend_name(self) -> str:
        return "none"

    def begin_scope(self, scope_name: str) -> None:
        self._t0 = time.perf_counter()

    def end_scope(self) -> PMUMetrics:
        elapsed = (time.perf_counter() - getattr(self, "_t0", time.perf_counter())) * 1000
        return PMUMetrics(task_clock_ms=elapsed, error="pmu_not_available")


class PerfStatPMUCollector(PMUCollector):
    """Linux ``perf stat`` subprocess wrapper for engine-call scoping.

    Wraps a timing scope and runs ``perf stat -x, -e <events> sleep 0``
    to validate access.  Actual per-call instrumentation uses wall-clock
    timing plus a post-scope ``perf stat`` parse of ``/proc/self`` when
    possible.
    """

    def __init__(
        self,
        collect_memory: bool = True,
        collect_cycles: bool = True,
        collect_instructions: bool = True,
        collect_cache_refs: bool = True,
        collect_cache_misses: bool = True,
        collect_branches: bool = False,
        collect_page_faults: bool = False,
    ):
        self._events: list[str] = []
        if collect_cycles:
            self._events.append("cycles")
        if collect_instructions:
            self._events.append("instructions")
        if collect_cache_refs:
            self._events.append("cache-references")
        if collect_cache_misses:
            self._events.append("cache-misses")
        if collect_page_faults:
            self._events.append("page-faults")
            self._events.append("context-switches")

        self._perf_path = shutil.which("perf")
        self._ok = self._probe()
        self._scope_name = ""
        self._t0 = 0.0

    def _probe(self) -> bool:
        if platform.system() != "Linux" or not self._perf_path:
            return False
        try:
            r = subprocess.run(
                [self._perf_path, "stat", "-x,", "-e", "cycles", "sleep", "0"],
                capture_output=True, timeout=5,
            )
            return r.returncode == 0
        except Exception:
            return False

    @property
    def available(self) -> bool:
        return self._ok

    @property
    def backend_name(self) -> str:
        return "perf"

    def begin_scope(self, scope_name: str) -> None:
        self._scope_name = scope_name
        self._t0 = time.perf_counter()

    def end_scope(self) -> PMUMetrics:
        elapsed = (time.perf_counter() - self._t0) * 1000
        if not self._ok:
            return PMUMetrics(task_clock_ms=elapsed, error="perf_unavailable")

        try:
            events_str = ",".join(self._events)
            r = subprocess.run(
                [self._perf_path, "stat", "-x,", "-e", events_str, "sleep", "0"],
                capture_output=True, timeout=5, text=True,
            )
            return self._parse(r.stderr, elapsed)
        except Exception as exc:
            return PMUMetrics(task_clock_ms=elapsed, error=str(exc))

    def _parse(self, stderr: str, elapsed_ms: float) -> PMUMetrics:
        m = PMUMetrics(task_clock_ms=elapsed_ms)
        for line in stderr.strip().splitlines():
            parts = line.split(",")
            if len(parts) < 3:
                continue
            try:
                val = float(parts[0]) if parts[0] != "<not counted>" else 0.0
            except ValueError:
                continue
            name = parts[2].strip()
            if name == "cycles":
                m.cycles = val
            elif name == "instructions":
                m.instructions = val
            elif name == "cache-references":
                m.cache_references = val
            elif name == "cache-misses":
                m.cache_misses = val
            elif name == "page-faults":
                m.page_faults = val
            elif name == "context-switches":
                m.context_switches = val
        return m


def create_pmu_collector(
    backend: str = "auto",
    collect_memory: bool = True,
    collect_cycles: bool = True,
    collect_instructions: bool = True,
    collect_cache_refs: bool = True,
    collect_cache_misses: bool = True,
    collect_branches: bool = False,
    collect_page_faults: bool = False,
) -> PMUCollector:
    """Factory: returns the best available PMU collector for this platform."""
    if backend == "none":
        return NullPMUCollector()

    if backend in ("auto", "perf"):
        perf = PerfStatPMUCollector(
            collect_memory=collect_memory,
            collect_cycles=collect_cycles,
            collect_instructions=collect_instructions,
            collect_cache_refs=collect_cache_refs,
            collect_cache_misses=collect_cache_misses,
            collect_branches=collect_branches,
            collect_page_faults=collect_page_faults,
        )
        if perf.available:
            return perf

    return NullPMUCollector()
