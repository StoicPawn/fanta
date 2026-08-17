from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Callable

import pandas as pd

CACHE_DIR = Path(os.getenv("FANTA_CACHE_DIR", ".cache/fanta_lab"))


def _safe_key(namespace: str, key: str) -> str:
    digest = hashlib.sha256(f"{namespace}|{key}".encode()).hexdigest()[:24]
    return f"{namespace.replace('/', '_')}-{digest}"


def _paths(namespace: str, key: str) -> tuple[Path, Path]:
    stem = _safe_key(namespace, key)
    return CACHE_DIR / f"{stem}.json", CACHE_DIR / f"{stem}.parquet"


def cache_status(namespace: str, key: str, ttl_seconds: int) -> dict[str, Any]:
    meta_path, data_path = _paths(namespace, key)
    if not meta_path.exists() or not data_path.exists():
        return {"exists": False, "fresh": False, "age_seconds": None, "expires_in": None}
    try:
        meta = json.loads(meta_path.read_text())
        created = float(meta.get("created_at", 0))
    except Exception:
        created = data_path.stat().st_mtime
    age = max(0.0, time.time() - created)
    return {
        "exists": True,
        "fresh": age <= ttl_seconds,
        "age_seconds": age,
        "expires_in": max(0.0, ttl_seconds - age),
    }


def read_dataframe(namespace: str, key: str, ttl_seconds: int, allow_stale: bool = False) -> pd.DataFrame | None:
    status = cache_status(namespace, key, ttl_seconds)
    if not status["exists"] or (not status["fresh"] and not allow_stale):
        return None
    _, data_path = _paths(namespace, key)
    try:
        return pd.read_parquet(data_path)
    except Exception:
        return None


def write_dataframe(namespace: str, key: str, df: pd.DataFrame, metadata: dict[str, Any] | None = None) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    meta_path, data_path = _paths(namespace, key)
    df.to_parquet(data_path, index=False)
    meta = {"created_at": time.time(), "rows": int(len(df)), **(metadata or {})}
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2))


def cached_dataframe(
    namespace: str,
    key: str,
    ttl_seconds: int,
    loader: Callable[[], pd.DataFrame],
    *,
    force_refresh: bool = False,
    stale_if_error: bool = True,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    if not force_refresh:
        hit = read_dataframe(namespace, key, ttl_seconds)
        if hit is not None:
            return hit, {"cache": "hit", **cache_status(namespace, key, ttl_seconds)}
    try:
        df = loader()
        write_dataframe(namespace, key, df)
        return df, {"cache": "refresh", **cache_status(namespace, key, ttl_seconds)}
    except Exception:
        if stale_if_error:
            stale = read_dataframe(namespace, key, ttl_seconds, allow_stale=True)
            if stale is not None:
                return stale, {"cache": "stale-fallback", **cache_status(namespace, key, ttl_seconds)}
        raise


def purge_cache() -> int:
    if not CACHE_DIR.exists():
        return 0
    removed = 0
    for p in CACHE_DIR.glob("*"):
        if p.is_file():
            p.unlink(missing_ok=True)
            removed += 1
    return removed
