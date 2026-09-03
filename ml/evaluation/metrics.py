from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
from sklearn.metrics import f1_score, precision_score, recall_score, roc_auc_score


@dataclass(frozen=True)
class EvaluationMetrics:
    image_auroc: float
    pixel_auroc: float
    precision: float
    recall: float
    f1: float
    inference_ms: float
    samples: int

    def as_dict(self) -> dict[str, float | int]:
        return asdict(self)


def _safe_auroc(labels: np.ndarray, scores: np.ndarray) -> float:
    if np.unique(labels).size < 2:
        return float("nan")
    return float(roc_auc_score(labels, scores))


def compute_metrics(
    image_labels: list[int],
    image_scores: list[float],
    image_predictions: list[int],
    pixel_labels: list[np.ndarray],
    pixel_scores: list[np.ndarray],
    inference_times: list[float],
) -> EvaluationMetrics:
    labels = np.asarray(image_labels, dtype=np.uint8)
    scores = np.asarray(image_scores, dtype=np.float32)
    predictions = np.asarray(image_predictions, dtype=np.uint8)
    if not (len(labels) == len(scores) == len(predictions) == len(inference_times)):
        raise ValueError("image evaluation inputs must have equal lengths")
    if not labels.size:
        raise ValueError("at least one evaluated image is required")

    flat_pixel_labels = np.concatenate([item.astype(np.uint8).ravel() for item in pixel_labels])
    flat_pixel_scores = np.concatenate([item.astype(np.float32).ravel() for item in pixel_scores])
    return EvaluationMetrics(
        image_auroc=_safe_auroc(labels, scores),
        pixel_auroc=_safe_auroc(flat_pixel_labels, flat_pixel_scores),
        precision=float(precision_score(labels, predictions, zero_division=0)),
        recall=float(recall_score(labels, predictions, zero_division=0)),
        f1=float(f1_score(labels, predictions, zero_division=0)),
        inference_ms=float(np.mean(inference_times)),
        samples=int(len(labels)),
    )
