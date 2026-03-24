"""In-memory cache store with lightweight diagnostics for prototype experiments."""

from __future__ import annotations

import csv
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class CacheAccessLog:
    timestamp: float
    key: str
    hit: bool
    engine_name: str = ""
    compute_time_ms: float = 0.0
    feature_vector: str = ""
    policy_approved_reuse: Optional[bool] = None
    operation: str = "lookup"


class SimpleCacheStore:
    """In-memory key-value store with explicit hit/miss and put diagnostics."""

    def __init__(self, enable_logging: bool = True) -> None:
        self._store: Dict[str, Any] = {}
        self._hits: int = 0
        self._misses: int = 0
        self._lookup_count: int = 0
        self._put_count: int = 0
        self._overwrite_count: int = 0
        self._miss_after_policy_approved_count: int = 0
        self._key_access_counts: Dict[str, int] = {}
        self._access_log: List[CacheAccessLog] = []
        self._logging = enable_logging

    def make_key(self, features: dict) -> str:
        return json.dumps(features, sort_keys=True)

    def has(self, features: dict) -> bool:
        key = self.make_key(features)
        return key in self._store

    def _record_lookup(
        self,
        *,
        key: str,
        hit: bool,
        engine_name: str,
        policy_approved_reuse: Optional[bool],
    ) -> None:
        self._lookup_count += 1
        self._key_access_counts[key] = self._key_access_counts.get(key, 0) + 1
        if hit:
            self._hits += 1
        else:
            self._misses += 1
            if policy_approved_reuse is True:
                self._miss_after_policy_approved_count += 1
        if self._logging:
            self._access_log.append(
                CacheAccessLog(
                    timestamp=time.time(),
                    key=key,
                    hit=hit,
                    engine_name=engine_name,
                    feature_vector=key[:200],
                    policy_approved_reuse=policy_approved_reuse,
                    operation="lookup",
                )
            )

    def try_get(
        self,
        features: dict,
        *,
        engine_name: str = "",
        policy_approved_reuse: Optional[bool] = None,
    ) -> Tuple[bool, Any]:
        """Single-lookup cache API returning ``(hit, value_or_none)``."""
        key = self.make_key(features)
        hit = key in self._store
        self._record_lookup(
            key=key,
            hit=hit,
            engine_name=engine_name,
            policy_approved_reuse=policy_approved_reuse,
        )
        if hit:
            return True, self._store[key]
        return False, None

    def get(
        self,
        features: dict,
        engine_name: str = "",
        policy_approved_reuse: Optional[bool] = None,
    ) -> Any:
        hit, value = self.try_get(
            features,
            engine_name=engine_name,
            policy_approved_reuse=policy_approved_reuse,
        )
        if hit:
            return value
        raise KeyError(self.make_key(features))

    def put(
        self,
        features: dict,
        value: Any,
        engine_name: str = "",
        compute_time_ms: float = 0.0,
    ) -> None:
        key = self.make_key(features)
        existed = key in self._store
        self._put_count += 1
        if existed:
            self._overwrite_count += 1
        self._store[key] = value
        if self._logging:
            self._access_log.append(
                CacheAccessLog(
                    timestamp=time.time(),
                    key=key,
                    hit=False,
                    engine_name=engine_name,
                    compute_time_ms=compute_time_ms,
                    feature_vector=key[:200],
                    operation="put",
                )
            )

    def stats(self) -> dict:
        total_lookup = self._lookup_count
        hit_rate = float(self._hits) / float(total_lookup) if total_lookup > 0 else 0.0
        miss_rate = float(self._misses) / float(total_lookup) if total_lookup > 0 else 0.0
        unique_lookup_keys = len(self._key_access_counts)
        repeated_lookup_keys = sum(
            1 for _key, count in self._key_access_counts.items() if int(count) > 1
        )
        return {
            "hits": self._hits,
            "misses": self._misses,
            "entries": len(self._store),
            "put_count": self._put_count,
            "overwrite_count": self._overwrite_count,
            "lookup_count": self._lookup_count,
            "unique_lookup_keys": unique_lookup_keys,
            "repeated_lookup_keys": repeated_lookup_keys,
            "hit_rate": hit_rate,
            "miss_rate": miss_rate,
            "miss_after_policy_approved_count": self._miss_after_policy_approved_count,
            "total_accesses": len(self._access_log),
        }

    def top_repeated_keys(self, top_n: int = 5) -> List[dict]:
        """Return top repeated keys by lookup access count."""
        items = sorted(
            self._key_access_counts.items(),
            key=lambda kv: (-kv[1], kv[0]),
        )
        out: List[dict] = []
        for key, count in items[: max(1, int(top_n))]:
            out.append({"key_hash": key[:32], "access_count": int(count)})
        return out

    @property
    def access_log(self) -> List[CacheAccessLog]:
        return self._access_log

    def flush_access_log_csv(self, path: Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(
                [
                    "timestamp",
                    "key_hash",
                    "operation",
                    "hit",
                    "engine_name",
                    "compute_time_ms",
                    "policy_approved_reuse",
                ]
            )
            for entry in self._access_log:
                key_hash = entry.key[:32] if len(entry.key) > 32 else entry.key
                w.writerow(
                    [
                        entry.timestamp,
                        key_hash,
                        entry.operation,
                        entry.hit,
                        entry.engine_name,
                        entry.compute_time_ms,
                        entry.policy_approved_reuse,
                    ]
                )
        return path

    def clear_log(self) -> None:
        self._access_log.clear()

    def clear(self) -> None:
        self._store.clear()
        self._hits = 0
        self._misses = 0
        self._lookup_count = 0
        self._put_count = 0
        self._overwrite_count = 0
        self._miss_after_policy_approved_count = 0
        self._key_access_counts.clear()
        self._access_log.clear()
