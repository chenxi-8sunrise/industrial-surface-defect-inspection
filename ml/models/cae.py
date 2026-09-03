from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from .base import AnomalyModel, Prediction
from .common import array_to_tensor, calibrate_map, elapsed_ms, image_paths, load_tensor, resolve_device


class _AutoEncoder(nn.Module):
    def __init__(self, latent_channels: int = 128) -> None:
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Conv2d(3, 32, 4, 2, 1), nn.ReLU(inplace=True),
            nn.Conv2d(32, 64, 4, 2, 1), nn.ReLU(inplace=True),
            nn.Conv2d(64, latent_channels, 4, 2, 1), nn.ReLU(inplace=True),
        )
        self.decoder = nn.Sequential(
            nn.ConvTranspose2d(latent_channels, 64, 4, 2, 1), nn.ReLU(inplace=True),
            nn.ConvTranspose2d(64, 32, 4, 2, 1), nn.ReLU(inplace=True),
            nn.ConvTranspose2d(32, 3, 4, 2, 1), nn.Sigmoid(),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.decoder(self.encoder(x))


class CAEModel(AnomalyModel):
    name = "cae"

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self.size = int(config.get("image_size", 256))
        self.device = resolve_device(config.get("device", "auto"))
        self.network = _AutoEncoder(int(config.get("latent_channels", 128))).to(self.device)
        self.residual_mean: torch.Tensor | None = None
        self.residual_std: torch.Tensor | None = None
        self.threshold = float(config.get("threshold", 0.5))

    def fit(self, train_dir: Path) -> dict[str, float]:
        tensors = torch.stack([load_tensor(path, self.size, False) for path in image_paths(train_dir)])
        loader = DataLoader(TensorDataset(tensors), batch_size=int(self.config.get("batch_size", 16)), shuffle=True)
        optimizer = torch.optim.Adam(self.network.parameters(), lr=float(self.config.get("learning_rate", 1e-3)))
        epochs = int(self.config.get("epochs", 30))
        self.network.train()
        last_loss = 0.0
        epoch_losses = []
        training_start = time.perf_counter()
        for _ in range(epochs):
            batch_losses = []
            for (batch,) in loader:
                batch = batch.to(self.device)
                reconstruction = self.network(batch)
                loss = torch.mean(torch.abs(reconstruction - batch))
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
                last_loss = float(loss.detach().cpu())
                batch_losses.append(last_loss)
            epoch_losses.append(float(np.mean(batch_losses)))
        self.network.eval()
        residual_sum = torch.zeros((self.size, self.size), dtype=torch.float32)
        residual_square_sum = torch.zeros_like(residual_sum)
        residual_count = 0
        with torch.no_grad():
            for (batch,) in loader:
                batch = batch.to(self.device)
                diff = torch.mean(torch.abs(self.network(batch) - batch), dim=1).cpu()
                residual_sum += diff.sum(dim=0)
                residual_square_sum += diff.square().sum(dim=0)
                residual_count += diff.shape[0]
        self.residual_mean = residual_sum / residual_count
        variance = (residual_square_sum / residual_count - self.residual_mean.square()).clamp_min(0)
        self.residual_std = torch.sqrt(variance) + float(self.config.get("residual_regularization", 0.01))

        errors = []
        with torch.no_grad():
            for (batch,) in loader:
                batch = batch.to(self.device)
                diff = torch.mean(torch.abs(self.network(batch) - batch), dim=1).cpu()
                calibrated = torch.clamp_min(diff - self.residual_mean, 0) / self.residual_std
                errors.extend(calibrated.flatten(1).quantile(0.99, dim=1).tolist())
        self.threshold = float(np.quantile(errors, float(self.config.get("score_quantile", 0.99))))
        self.is_fitted = True
        return {
            "loss": last_loss,
            "threshold": self.threshold,
            "epoch_losses": epoch_losses,
            "training_seconds": time.perf_counter() - training_start,
        }

    def predict(self, image: np.ndarray, category: str) -> Prediction:
        if not self.is_fitted:
            raise RuntimeError("CAE model must be fitted or loaded before prediction")
        if self.residual_mean is None or self.residual_std is None:
            raise RuntimeError("CAE residual calibration is unavailable")
        start = time.perf_counter()
        tensor = array_to_tensor(image, self.size, False).unsqueeze(0).to(self.device)
        with torch.no_grad():
            reconstruction = self.network(tensor)
            residual = torch.mean(torch.abs(reconstruction - tensor), dim=1)[0].cpu()
            raw = (torch.clamp_min(residual - self.residual_mean, 0) / self.residual_std).numpy()
        raw_score = float(np.quantile(raw, 0.99))
        score = float(raw_score / max(raw_score + self.threshold, 1e-8))
        return Prediction(self.name, category, score, raw_score > self.threshold, calibrate_map(raw, self.threshold), elapsed_ms(start))

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        torch.save({
            "state_dict": self.network.state_dict(),
            "residual_mean": self.residual_mean,
            "residual_std": self.residual_std,
            "threshold": self.threshold,
            "config": self.config,
        }, path)

    def load(self, path: Path) -> None:
        payload = torch.load(path, map_location=self.device, weights_only=False)
        self.network.load_state_dict(payload["state_dict"])
        self.residual_mean = payload["residual_mean"]
        self.residual_std = payload["residual_std"]
        self.threshold = float(payload["threshold"])
        self.network.eval()
        self.is_fitted = True
