from __future__ import annotations

import csv
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from ml.models.base import AnomalyModel
from ml.models.common import IMAGE_SUFFIXES

from .metrics import EvaluationMetrics, compute_metrics


def _mask_for(root: Path, defect_type: str, image_path: Path, size: int) -> np.ndarray:
    if defect_type == "good":
        return np.zeros((size, size), dtype=np.uint8)
    candidate = root / "ground_truth" / defect_type / f"{image_path.stem}_mask.png"
    if not candidate.exists():
        raise FileNotFoundError(f"ground-truth mask not found: {candidate}")
    with Image.open(candidate) as source:
        mask = np.asarray(source.convert("L"))
    return (cv2.resize(mask, (size, size), interpolation=cv2.INTER_NEAREST) > 0).astype(np.uint8)


def evaluate_category(
    model: AnomalyModel,
    category_dir: Path,
    category: str,
    output_dir: Path,
) -> EvaluationMetrics:
    size = int(model.config.get("image_size", 256))
    test_root = category_dir / "test"
    if not test_root.is_dir():
        raise FileNotFoundError(f"test directory not found: {test_root}")
    output_dir.mkdir(parents=True, exist_ok=True)
    visualization_dir = output_dir / "visualizations"
    visualization_dir.mkdir(exist_ok=True)

    labels: list[int] = []
    scores: list[float] = []
    predictions: list[int] = []
    masks: list[np.ndarray] = []
    heatmaps: list[np.ndarray] = []
    inference_times: list[float] = []
    rows: list[dict[str, object]] = []

    for defect_dir in sorted(path for path in test_root.iterdir() if path.is_dir()):
        is_anomaly = int(defect_dir.name != "good")
        image_paths = sorted(path for path in defect_dir.iterdir() if path.suffix.lower() in IMAGE_SUFFIXES)
        for image_index, image_path in enumerate(image_paths):
            with Image.open(image_path) as source:
                image = np.asarray(source.convert("RGB"))
            result = model.predict(image, category)
            labels.append(is_anomaly)
            scores.append(result.anomaly_score)
            predictions.append(int(result.is_anomaly))
            mask = _mask_for(category_dir, defect_dir.name, image_path, size)
            masks.append(mask)
            heatmaps.append(result.heatmap)
            inference_times.append(result.inference_ms)
            rows.append({
                "image": str(image_path.relative_to(category_dir)),
                "defect_type": defect_dir.name,
                "label": is_anomaly,
                "score": round(result.anomaly_score, 6),
                "prediction": int(result.is_anomaly),
                "inference_ms": round(result.inference_ms, 3),
            })
            if image_index < 2:
                original = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
                resized_map = cv2.resize(result.heatmap, (original.shape[1], original.shape[0]))
                colored = cv2.applyColorMap(np.uint8(np.clip(resized_map, 0, 1) * 255), cv2.COLORMAP_JET)
                overlay = cv2.addWeighted(original, 0.55, colored, 0.45, 0)
                panel = np.hstack((original, colored, overlay))
                encoded, buffer = cv2.imencode(".jpg", panel)
                if not encoded:
                    raise ValueError("failed to encode evaluation visualization")
                buffer.tofile(visualization_dir / f"{defect_dir.name}_{image_path.stem}.jpg")

    metrics = compute_metrics(labels, scores, predictions, masks, heatmaps, inference_times)
    with (output_dir / "predictions.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with (output_dir / "metrics.json").open("w", encoding="utf-8") as stream:
        json.dump(metrics.as_dict(), stream, ensure_ascii=False, indent=2, allow_nan=True)
    return metrics
