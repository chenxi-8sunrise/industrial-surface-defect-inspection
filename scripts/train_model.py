from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

import numpy as np
import torch
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ml.models import create_model


CONFIG_DIR = ROOT / "configs" / "models"
DATA_ROOT = ROOT / "data" / "raw" / "mvtec_ad"
MODEL_ROOT = ROOT / "artifacts" / "models"


def artifact_path(model_name: str, category: str) -> Path:
    suffix = ".npz" if model_name == "patchcore" else ".pt"
    return MODEL_ROOT / model_name / f"{category}{suffix}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Train one anomaly-detection model on one MVTec AD category.")
    parser.add_argument("model", choices=("cae", "padim", "patchcore", "stfpm"))
    parser.add_argument("category", choices=("bottle", "tile", "transistor"))
    parser.add_argument("--epochs", type=int)
    args = parser.parse_args()

    with (CONFIG_DIR / f"{args.model}.yaml").open("r", encoding="utf-8") as stream:
        config = yaml.safe_load(stream)
    config.update({"device": "auto", "image_size": 256, "pretrained": True, "seed": 42})
    if args.epochs is not None:
        if args.epochs < 1:
            raise ValueError("epochs must be positive")
        config["epochs"] = args.epochs

    random.seed(config["seed"])
    np.random.seed(config["seed"])
    torch.manual_seed(config["seed"])

    train_dir = DATA_ROOT / args.category / "train" / "good"
    if not train_dir.is_dir():
        raise FileNotFoundError(f"training data not found: {train_dir}")
    model = create_model(args.model, config)
    training = model.fit(train_dir)
    output = artifact_path(args.model, args.category)
    model.save(output)
    record = {"model": args.model, "category": args.category, "artifact": str(output), "training": training}
    output.with_suffix(output.suffix + ".json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(record, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
