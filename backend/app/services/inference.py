from __future__ import annotations

from pathlib import Path
from threading import Lock

import cv2
import numpy as np
import yaml

from ml.models import MODEL_SPECS, create_model
from ml.models.base import AnomalyModel, Prediction


ROOT = Path(__file__).resolve().parents[3]
CONFIG_DIR = ROOT / "configs" / "models"
MODEL_DIR = ROOT / "artifacts" / "models"


class ModelManager:
    def __init__(self) -> None:
        self._models: dict[tuple[str, str], AnomalyModel] = {}
        self._lock = Lock()

    @staticmethod
    def artifact_path(model_name: str, category: str) -> Path:
        suffix = ".npz" if model_name == "patchcore" else ".pt"
        return MODEL_DIR / model_name / f"{category}{suffix}"

    def ready(self, model_name: str, category: str | None = None) -> bool:
        if category:
            return self.artifact_path(model_name, category).exists()
        return any(self.artifact_path(model_name, item).exists() for item in ("bottle", "tile", "transistor"))

    def get(self, model_name: str, category: str) -> AnomalyModel:
        key = (model_name, category)
        if key in self._models:
            return self._models[key]
        artifact = self.artifact_path(model_name, category)
        if not artifact.exists():
            raise FileNotFoundError(f"model artifact not found: {artifact}")
        with (CONFIG_DIR / f"{model_name}.yaml").open("r", encoding="utf-8") as stream:
            config = yaml.safe_load(stream)
        config.update({"device": "auto", "image_size": 256, "pretrained": True})
        model = create_model(model_name, config)
        model.load(artifact)
        with self._lock:
            self._models[key] = model
        return model

    def predict(self, model_name: str, category: str, image: np.ndarray) -> Prediction:
        return self.get(model_name, category).predict(image, category)


def heatmap_overlay(image: np.ndarray, heatmap: np.ndarray) -> np.ndarray:
    resized = cv2.resize(heatmap, (image.shape[1], image.shape[0]))
    colored = cv2.applyColorMap(np.uint8(np.clip(resized, 0, 1) * 255), cv2.COLORMAP_JET)
    return cv2.addWeighted(image, 0.55, colored, 0.45, 0)


manager = ModelManager()
