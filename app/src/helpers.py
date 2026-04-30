import math
import statistics
from pathlib import Path

from .rag.retriever import _store as _rag_store
from .settings import settings


def count_output_files() -> int:
    return len([f for f in Path(settings.OUTPUT_DIR).glob("*") if f.is_file()])


def rag_vector_count() -> int:
    try:
        return _rag_store().total_vectors
    except Exception:
        return -1


def _percentile(vals: list[float], p: float) -> float:
    if not vals:
        return 0.0
    s = sorted(vals)
    return s[max(0, math.ceil(p * len(s)) - 1)]


def compute_stats(vals: list[float]) -> dict:
    if not vals:
        return {"mean": 0, "median": 0, "stdev": 0, "cv": 0.0, "p95": 0, "p99": 0}
    mean  = statistics.mean(vals)
    stdev = statistics.stdev(vals) if len(vals) > 1 else 0
    return {
        "mean":   round(mean),
        "stdev":  round(stdev),
        "cv":     round(stdev / mean * 100, 1) if mean else 0.0,
        "median": round(statistics.median(vals)),
        "p95":    round(_percentile(vals, 0.95)),
        "p99":    round(_percentile(vals, 0.99)),
    }


def pill_html(value: str | None, mapping: dict) -> str:
    v = (value or "").lower()
    for prefix, style in mapping.items():
        if v.startswith(prefix):
            return f'<span style="{style}">{value}</span>'
    return value or "—"


def bar_width_px(ms: float, total: float) -> str:
    return f"{max(int(ms / max(total, 1) * 80), 1)}px"
