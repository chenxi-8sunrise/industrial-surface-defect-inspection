from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F
from torch.utils.data import DataLoader, TensorDataset

from .base import AnomalyModel, Prediction
from .common import ResNet18Features, array_to_tensor, calibrate_map, elapsed_ms, image_paths, load_tensor, resolve_device


class STFPMModel(AnomalyModel):
    name = "stfpm"

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self.size = int(config.get("image_size", 256))
        self.device = resolve_device(config.get("device", "auto"))
        pretrained = bool(config.get("pretrained", True))
        self.teacher = ResNet18Features(pretrained).to(self.device)
        self.student = ResNet18Features(False).to(self.device)
        for parameter in self.student.parameters():
            parameter.requires_grad = True
        self.threshold = float(config.get("threshold", 0.5))

    @staticmethod
    def _loss(teacher: list[torch.Tensor], student: list[torch.Tensor]) -> torch.Tensor:
        terms = []
        for teacher_feature, student_feature in zip(teacher, student):
            teacher_norm = F.normalize(teacher_feature, dim=1)
            student_norm = F.normalize(student_feature, dim=1)
            terms.append(torch.mean((teacher_norm - student_norm) ** 2))
        return sum(terms)

    def _map(self, tensor: torch.Tensor) -> torch.Tensor:
        with torch.no_grad():
            teacher_features = self.teacher(tensor.to(self.device))
            student_features = self.student(tensor.to(self.device))
        maps = []
        for teacher_feature, student_feature in zip(teacher_features, student_features):
            distance = torch.mean((F.normalize(teacher_feature, dim=1) - F.normalize(student_feature, dim=1)) ** 2, dim=1, keepdim=True)
            maps.append(F.interpolate(distance, size=(self.size, self.size), mode="bilinear", align_corners=False))
        return torch.stack(maps).sum(dim=0)

    def fit(self, train_dir: Path) -> dict[str, float]:
        tensors = torch.stack([load_tensor(path, self.size, True) for path in image_paths(train_dir)])
        loader = DataLoader(TensorDataset(tensors), batch_size=int(self.config.get("batch_size", 16)), shuffle=True)
        optimizer = torch.optim.Adam(self.student.parameters(), lr=float(self.config.get("learning_rate", 4e-4)))
        self.student.train()
        last_loss = 0.0
        epoch_losses = []
        training_start = time.perf_counter()
        for _ in range(int(self.config.get("epochs", 30))):
            batch_losses = []
            for (batch,) in loader:
                batch = batch.to(self.device)
                with torch.no_grad():
                    teacher_features = self.teacher(batch)
                student_features = self.student(batch)
                loss = self._loss(teacher_features, student_features)
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
                last_loss = float(loss.detach().cpu())
                batch_losses.append(last_loss)
            epoch_losses.append(float(np.mean(batch_losses)))
        self.student.eval()
        scores = []
        for (batch,) in loader:
            amap = self._map(batch)
            scores.extend(amap.flatten(1).quantile(0.99, dim=1).cpu().tolist())
        self.threshold = float(np.quantile(scores, 0.99))
        self.is_fitted = True
        return {
            "loss": last_loss,
            "threshold": self.threshold,
            "epoch_losses": epoch_losses,
            "training_seconds": time.perf_counter() - training_start,
        }

    def predict(self, image: np.ndarray, category: str) -> Prediction:
        if not self.is_fitted:
            raise RuntimeError("STFPM model must be fitted or loaded before prediction")
        start = time.perf_counter()
        tensor = array_to_tensor(image, self.size, True).unsqueeze(0)
        raw = self._map(tensor)[0, 0].cpu().numpy()
        raw_score = float(np.quantile(raw, 0.99))
        score = float(raw_score / max(raw_score + self.threshold, 1e-8))
        return Prediction(self.name, category, score, raw_score > self.threshold, calibrate_map(raw, self.threshold), elapsed_ms(start))

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        torch.save({"state_dict": self.student.state_dict(), "threshold": self.threshold, "config": self.config}, path)

    def load(self, path: Path) -> None:
        payload = torch.load(path, map_location=self.device, weights_only=False)
        self.student.load_state_dict(payload["state_dict"])
        self.student.eval()
        self.threshold = float(payload["threshold"])
        self.is_fitted = True
