import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

from ml.models.cae import CAEModel
from ml.models.padim import PaDiMModel
from ml.models.patchcore import PatchCoreModel
from ml.models.stfpm import STFPMModel


def _training_images(root: Path) -> Path:
    train = root / "train"
    train.mkdir()
    rng = np.random.default_rng(42)
    for index in range(2):
        image = rng.integers(0, 255, size=(64, 64, 3), dtype=np.uint8)
        Image.fromarray(image).save(train / f"{index}.png")
    return train


def _assert_prediction(model, image):
    result = model.predict(image, "bottle")
    assert result.model == model.name
    assert result.category == "bottle"
    assert result.heatmap.shape == (64, 64)
    assert 0.0 <= result.anomaly_score <= 1.0


def test_four_models_fit_and_predict_on_cpu():
    config = {"image_size": 64, "device": "cpu", "pretrained": False, "epochs": 1, "batch_size": 2, "coreset_ratio": 0.2}
    image = np.full((64, 64, 3), 127, dtype=np.uint8)
    with tempfile.TemporaryDirectory() as tmp:
        train = _training_images(Path(tmp))
        for model in [CAEModel(config), PaDiMModel(config), PatchCoreModel(config), STFPMModel(config)]:
            metrics = model.fit(train)
            assert "threshold" in metrics
            _assert_prediction(model, image)
