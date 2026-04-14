# execution/model_quality.py
# Shared model-quality check used by CoinSelector and MultiRunner.

import json
from pathlib import Path


def model_quality_ok(
    symbol: str,
    min_f1: float = 0.10,
    min_precision: float = 0.10,
    min_recall: float = 0.10,
) -> tuple[bool, dict]:
    """
    Returns (ok, metrics_dict) for a symbol's trained model.
    metrics_dict contains val_f1, val_precision, val_recall.
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
        ok = f1 >= min_f1 and prec >= min_precision and rec >= min_recall
        return ok, {"val_f1": f1, "val_precision": prec, "val_recall": rec}
    except Exception:
        return False, {}
