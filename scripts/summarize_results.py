from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULT_ROOT = ROOT / "artifacts" / "results"
MODELS = ("cae", "padim", "patchcore", "stfpm")
CATEGORIES = ("bottle", "tile", "transistor")
FIELDS = ("image_auroc", "pixel_auroc", "precision", "recall", "f1", "inference_ms")


def main() -> None:
    rows: list[dict[str, object]] = []
    for model in MODELS:
        for category in CATEGORIES:
            path = RESULT_ROOT / model / category / "metrics.json"
            if not path.exists():
                raise FileNotFoundError(f"result not found: {path}")
            metrics = json.loads(path.read_text(encoding="utf-8"))
            rows.append({"model": model, "category": category, **metrics})

    RESULT_ROOT.mkdir(parents=True, exist_ok=True)
    with (RESULT_ROOT / "metrics_summary.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    averages = []
    for model in MODELS:
        selected = [row for row in rows if row["model"] == model]
        averages.append({
            "model": model,
            **{field: sum(float(row[field]) for row in selected) / len(selected) for field in FIELDS},
        })
    with (RESULT_ROOT / "model_averages.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(averages[0]))
        writer.writeheader()
        writer.writerows(averages)
    print(RESULT_ROOT / "metrics_summary.csv")


if __name__ == "__main__":
    main()
