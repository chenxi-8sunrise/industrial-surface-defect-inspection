import numpy as np
import pytest

from ml.evaluation.metrics import compute_metrics


def test_compute_metrics_returns_expected_binary_scores() -> None:
    metrics = compute_metrics(
        image_labels=[0, 1, 1, 0],
        image_scores=[0.1, 0.9, 0.8, 0.2],
        image_predictions=[0, 1, 1, 0],
        pixel_labels=[np.zeros((2, 2)), np.ones((2, 2))],
        pixel_scores=[np.zeros((2, 2)), np.ones((2, 2))],
        inference_times=[10.0, 14.0, 12.0, 12.0],
    )
    assert metrics.image_auroc == pytest.approx(1.0)
    assert metrics.pixel_auroc == pytest.approx(1.0)
    assert metrics.f1 == pytest.approx(1.0)
    assert metrics.inference_ms == pytest.approx(12.0)
    assert metrics.samples == 4


def test_compute_metrics_rejects_mismatched_image_inputs() -> None:
    with pytest.raises(ValueError, match="equal lengths"):
        compute_metrics([0], [0.1, 0.2], [0], [np.zeros((1, 1))], [np.zeros((1, 1))], [1.0])
