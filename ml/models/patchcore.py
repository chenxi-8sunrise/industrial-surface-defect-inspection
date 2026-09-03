from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import numpy as np
import torch
from sklearn.neighbors import NearestNeighbors
from torch.nn import functional as F

from .base import AnomalyModel, Prediction
from .common import ResNet18Features, array_to_tensor, calibrate_map, elapsed_ms, image_paths, load_tensor, merge_features, resolve_device


class PatchCoreModel(AnomalyModel):
    name = "patchcore"

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self.size = int(config.get("image_size", 256))
        self.device = resolve_device(config.get("device", "auto"))
        self.extractor = ResNet18Features(bool(config.get("pretrained", True))).to(self.device)
        self.channel_indices: np.ndarray | None = None
        self.memory_bank: np.ndarray | None = None
        self.index: NearestNeighbors | None = None
        self.threshold = float(config.get("threshold", 0.5))

    def _patches(self, tensor: torch.Tensor) -> tuple[np.ndarray, tuple[int, int]]:
        with torch.no_grad():
            merged = merge_features(self.extractor(tensor.to(self.device))[1:])
        if self.channel_indices is None:
            requested = min(int(self.config.get("projection_dim", 128)), merged.shape[1])
            rng = np.random.default_rng(int(self.config.get("seed", 42)))
            self.channel_indices = np.sort(rng.choice(merged.shape[1], size=requested, replace=False))
        merged = merged[:, self.channel_indices]
        merged = F.normalize(merged, p=2, dim=1)
        height, width = merged.shape[-2:]
        patches = merged[0].permute(1, 2, 0).reshape(-1, merged.shape[1]).cpu().numpy().astype(np.float32)
        return patches, (height, width)

    def _build_index(self) -> None:
        if self.memory_bank is None:
            raise RuntimeError("memory bank is unavailable")
        self.index = NearestNeighbors(n_neighbors=int(self.config.get("neighbors", 1)), metric="euclidean")
        self.index.fit(self.memory_bank)

    def fit(self, train_dir: Path) -> dict[str, float]:
        all_patches = [self._patches(load_tensor(path, self.size, True).unsqueeze(0))[0] for path in image_paths(train_dir)]
        bank = np.concatenate(all_patches, axis=0)
        ratio = float(self.config.get("coreset_ratio", 0.1))
        count = max(1, min(len(bank), int(len(bank) * ratio)))
        rng = np.random.default_rng(int(self.config.get("seed", 42)))
        selected = rng.choice(len(bank), size=count, replace=False)
        self.memory_bank = bank[selected]
        self._build_index()
        train_scores = []
        for patches in all_patches:
            distances, _ = self.index.kneighbors(patches)
            train_scores.append(float(np.quantile(distances.mean(axis=1), 0.99)))
        self.threshold = float(np.quantile(train_scores, 0.99))
        self.is_fitted = True
        return {"threshold": self.threshold, "memory_patches": float(len(self.memory_bank))}

    def predict(self, image: np.ndarray, category: str) -> Prediction:
        if self.index is None:
            raise RuntimeError("PatchCore model must be fitted or loaded before prediction")
        start = time.perf_counter()
        patches, grid = self._patches(array_to_tensor(image, self.size, True).unsqueeze(0))
        distances, _ = self.index.kneighbors(patches)
        patch_scores = distances.mean(axis=1).reshape(grid)
        raw = F.interpolate(torch.from_numpy(patch_scores)[None, None], size=(self.size, self.size), mode="bilinear", align_corners=False)[0, 0].numpy()
        raw_score = float(np.quantile(raw, 0.99))
        score = float(raw_score / max(raw_score + self.threshold, 1e-8))
        return Prediction(self.name, category, score, raw_score > self.threshold, calibrate_map(raw, self.threshold), elapsed_ms(start))

    def save(self, path: Path) -> None:
        if self.memory_bank is None:
            raise RuntimeError("cannot save an unfitted PatchCore model")
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            path,
            memory_bank=self.memory_bank,
            channel_indices=self.channel_indices,
            threshold=np.array([self.threshold]),
        )

    def load(self, path: Path) -> None:
        payload = np.load(path)
        self.memory_bank = payload["memory_bank"].astype(np.float32)
        self.channel_indices = payload["channel_indices"].astype(np.int64)
        self.threshold = float(payload["threshold"][0])
        self._build_index()
        self.is_fitted = True
