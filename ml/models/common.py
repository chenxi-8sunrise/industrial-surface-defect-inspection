from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Iterable

import numpy as np
import torch
from PIL import Image
from torch import nn
from torch.nn import functional as F

os.environ.setdefault("TORCH_HOME", str(Path(__file__).resolve().parents[2] / ".cache" / "torch"))

from torchvision import models, transforms


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp"}
IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)


def resolve_device(requested: str = "auto") -> torch.device:
    if requested == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if requested == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but is unavailable")
    return torch.device(requested)


def image_paths(directory: Path) -> list[Path]:
    paths = sorted(p for p in directory.rglob("*") if p.suffix.lower() in IMAGE_SUFFIXES)
    if not paths:
        raise ValueError(f"no images found in {directory}")
    return paths


def image_transform(size: int, normalized: bool) -> transforms.Compose:
    items: list[object] = [transforms.Resize((size, size)), transforms.ToTensor()]
    if normalized:
        items.append(transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD))
    return transforms.Compose(items)


def load_tensor(path: Path, size: int, normalized: bool) -> torch.Tensor:
    with Image.open(path) as image:
        return image_transform(size, normalized)(image.convert("RGB"))


def array_to_tensor(image: np.ndarray, size: int, normalized: bool) -> torch.Tensor:
    if image.ndim == 2:
        image = np.repeat(image[..., None], 3, axis=2)
    if image.ndim != 3 or image.shape[2] not in (3, 4):
        raise ValueError("image must be HxW, HxWx3 or HxWx4")
    pil = Image.fromarray(image[..., :3].astype(np.uint8), mode="RGB")
    return image_transform(size, normalized)(pil)


def normalize_map(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=np.float32)
    low, high = float(values.min()), float(values.max())
    if high - low < 1e-12:
        return np.zeros_like(values, dtype=np.float32)
    return (values - low) / (high - low)


def calibrate_map(values: np.ndarray, threshold: float) -> np.ndarray:
    values = np.maximum(np.asarray(values, dtype=np.float32), 0.0)
    return values / np.maximum(values + float(threshold), 1e-8)


def elapsed_ms(start: float) -> float:
    return (time.perf_counter() - start) * 1000.0


class ResNet18Features(nn.Module):
    def __init__(self, pretrained: bool = True) -> None:
        super().__init__()
        weights = models.ResNet18_Weights.DEFAULT if pretrained else None
        network = models.resnet18(weights=weights)
        self.stem = nn.Sequential(network.conv1, network.bn1, network.relu, network.maxpool)
        self.layer1 = network.layer1
        self.layer2 = network.layer2
        self.layer3 = network.layer3
        for parameter in self.parameters():
            parameter.requires_grad = False
        self.eval()

    def forward(self, x: torch.Tensor) -> list[torch.Tensor]:
        x = self.stem(x)
        first = self.layer1(x)
        second = self.layer2(first)
        third = self.layer3(second)
        return [first, second, third]


def merge_features(features: Iterable[torch.Tensor], target_size: tuple[int, int] | None = None) -> torch.Tensor:
    features = list(features)
    if not features:
        raise ValueError("at least one feature tensor is required")
    size = target_size or features[0].shape[-2:]
    resized = [F.interpolate(feature, size=size, mode="bilinear", align_corners=False) for feature in features]
    return torch.cat(resized, dim=1)
