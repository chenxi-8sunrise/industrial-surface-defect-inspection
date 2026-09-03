from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch.nn import functional as F

from .base import AnomalyModel, Prediction
from .common import ResNet18Features, array_to_tensor, calibrate_map, elapsed_ms, image_paths, load_tensor, merge_features, resolve_device


class PaDiMModel(AnomalyModel):
    name = "padim"

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self.size = int(config.get("image_size", 256))
        self.device = resolve_device(config.get("device", "auto"))
        self.extractor = ResNet18Features(bool(config.get("pretrained", True))).to(self.device)
        self.channel_indices: torch.Tensor | None = None
        self.mean: torch.Tensor | None = None
        self.variance: torch.Tensor | None = None
        self.threshold = float(config.get("threshold", 0.5))

    def _features(self, tensor: torch.Tensor) -> torch.Tensor:
        with torch.no_grad():
            features = merge_features(self.extractor(tensor.to(self.device)))
        if self.channel_indices is None:
            requested = min(int(self.config.get("embedding_dim", 100)), features.shape[1])
            generator = torch.Generator().manual_seed(int(self.config.get("seed", 42)))
            self.channel_indices = torch.randperm(features.shape[1], generator=generator)[:requested]
        return features[:, self.channel_indices.to(features.device)]

    def fit(self, train_dir: Path) -> dict[str, float]:
        feature_sum: torch.Tensor | None = None
        square_sum: torch.Tensor | None = None
        count = 0
        for path in image_paths(train_dir):
            features = self._features(load_tensor(path, self.size, True).unsqueeze(0)).cpu()[0]
            feature_sum = features.clone() if feature_sum is None else feature_sum + features
            square_sum = features.square() if square_sum is None else square_sum + features.square()
            count += 1
        if feature_sum is None or square_sum is None:
            raise ValueError("no training features were extracted")
        self.mean = feature_sum / count
        self.variance = square_sum / count - self.mean.square()
        self.variance = self.variance.clamp_min(0) + float(self.config.get("gaussian_regularization", 0.01))
        scores = []
        for path in image_paths(train_dir):
            features = self._features(load_tensor(path, self.size, True).unsqueeze(0)).cpu()[0]
            distance = torch.sqrt(torch.mean((features - self.mean) ** 2 / self.variance, dim=0))
            scores.append(float(distance.quantile(0.99)))
        self.threshold = float(np.quantile(scores, 0.99))
        self.is_fitted = True
        return {"threshold": self.threshold, "feature_channels": float(self.mean.shape[0])}

    def predict(self, image: np.ndarray, category: str) -> Prediction:
        if self.mean is None or self.variance is None:
            raise RuntimeError("PaDiM model must be fitted or loaded before prediction")
        start = time.perf_counter()
        features = self._features(array_to_tensor(image, self.size, True).unsqueeze(0)).cpu()[0]
        distance = torch.sqrt(torch.mean((features - self.mean) ** 2 / self.variance, dim=0))
        raw = F.interpolate(distance[None, None], size=(self.size, self.size), mode="bilinear", align_corners=False)[0, 0].numpy()
        raw_score = float(np.quantile(raw, 0.99))
        score = float(raw_score / max(raw_score + self.threshold, 1e-8))
        return Prediction(self.name, category, score, raw_score > self.threshold, calibrate_map(raw, self.threshold), elapsed_ms(start))

    def save(self, path: Path) -> None:
        if self.mean is None or self.variance is None:
            raise RuntimeError("cannot save an unfitted PaDiM model")
        path.parent.mkdir(parents=True, exist_ok=True)
        torch.save({
            "mean": self.mean,
            "variance": self.variance,
            "channel_indices": self.channel_indices,
            "threshold": self.threshold,
            "config": self.config,
        }, path)

    def load(self, path: Path) -> None:
        payload = torch.load(path, map_location="cpu", weights_only=False)
        self.mean, self.variance = payload["mean"], payload["variance"]
        self.channel_indices = payload["channel_indices"]
        self.threshold = float(payload["threshold"])
        self.is_fitted = True
