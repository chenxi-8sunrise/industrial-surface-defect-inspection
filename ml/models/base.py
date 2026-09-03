from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


@dataclass(frozen=True)
class Prediction:
    model: str
    category: str
    anomaly_score: float
    is_anomaly: bool
    heatmap: np.ndarray
    inference_ms: float

    def __post_init__(self) -> None:
        if self.heatmap.ndim != 2:
            raise ValueError("heatmap must be a two-dimensional array")
        if not 0.0 <= self.anomaly_score <= 1.0:
            raise ValueError("anomaly_score must be normalized to [0, 1]")
        if self.inference_ms < 0:
            raise ValueError("inference_ms cannot be negative")


class AnomalyModel(ABC):
    name: str

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.is_fitted = False

    @abstractmethod
    def fit(self, train_dir: Path) -> dict[str, Any]:
        """Fit the model using normal training images."""

    @abstractmethod
    def predict(self, image: np.ndarray, category: str) -> Prediction:
        """Return an image-level score and pixel-level heatmap."""

    @abstractmethod
    def save(self, path: Path) -> None:
        """Persist trained parameters."""

    @abstractmethod
    def load(self, path: Path) -> None:
        """Load trained parameters."""
