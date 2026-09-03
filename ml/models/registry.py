from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import Any

from .base import AnomalyModel


@dataclass(frozen=True)
class ModelSpec:
    name: str
    owner: str
    title: str
    module: str
    class_name: str
    requires_training: bool


MODEL_SPECS: dict[str, ModelSpec] = {
    "cae": ModelSpec("cae", "A", "卷积自编码器", "ml.models.cae", "CAEModel", True),
    "padim": ModelSpec("padim", "B", "PaDiM特征分布模型", "ml.models.padim", "PaDiMModel", False),
    "patchcore": ModelSpec("patchcore", "C", "PatchCore记忆库模型", "ml.models.patchcore", "PatchCoreModel", False),
    "stfpm": ModelSpec("stfpm", "D", "STFPM教师-学生模型", "ml.models.stfpm", "STFPMModel", True),
}


def list_models() -> list[ModelSpec]:
    return list(MODEL_SPECS.values())


def create_model(name: str, config: dict[str, Any]) -> AnomalyModel:
    normalized = name.strip().lower()
    if normalized not in MODEL_SPECS:
        allowed = ", ".join(MODEL_SPECS)
        raise ValueError(f"unknown model '{name}', expected one of: {allowed}")
    spec = MODEL_SPECS[normalized]
    module = import_module(spec.module)
    model_class = getattr(module, spec.class_name)
    return model_class(config)

