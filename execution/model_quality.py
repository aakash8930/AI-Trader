# execution/model_quality.py
# Shared model-quality check used by CoinSelector and MultiRunner.

import json
from pathlib import Path


def model_quality_ok(
    symbol: str,
    min_f1: float = 0.15,
    min_precision: float = 0.15,
    min_recall: float = 0.10,
    allow_high_recall_compensation: bool = True,
) -> tuple[bool, dict]:
    """
    Returns (ok, metrics_dict) for a symbol's trained model.
    metrics_dict contains val_f1, val_precision, val_recall.

    Key change: allow symbols with high recall (>0.60) to pass even if
    precision is slightly below threshold—these models catch many opportunities
    and the strategy engine's other filters (ADX, RSI, edge) provide safety.
    """
    metadata_path = Path("models") / symbol.replace("/", "_") / "metadata.json"
    if not metadata_path.exists():
        return False, {}

    try:
        data = json.loads(metadata_path.read_text(encoding="utf-8"))
        metrics = data.get("metrics", {})
        f1 = float(metrics.get("val_f1", 0.0))
        prec = float(metrics.get("val_precision", 0.0))
        rec = float(metrics.get("val_recall", 0.0))

        # Base check
        ok = f1 >= min_f1 and prec >= min_precision and rec >= min_recall

        # Compensation rule: high-recall models (>0.60) can pass with lower precision
        # This prevents discarding models that catch many opportunities just because
        # they have modest precision—the strategy filters handle false positives.
        if allow_high_recall_compensation and not ok:
            if rec >= 0.60 and prec >= 0.12 and f1 >= 0.12:
                ok = True

        return ok, {"val_f1": f1, "val_precision": prec, "val_recall": rec}
    except Exception:
        return False, {}
