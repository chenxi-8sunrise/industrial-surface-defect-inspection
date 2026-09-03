from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ml.models import create_model
from ml.models.common import image_paths, load_tensor
from train_model import CONFIG_DIR, DATA_ROOT, artifact_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Calibrate an STFPM decision threshold using only normal training images."
    )
    parser.add_argument("category", choices=("bottle", "tile", "transistor"))
    parser.add_argument("--quantile", type=float, default=0.95)
    args = parser.parse_args()
    if not 0.0 < args.quantile < 1.0:
        raise ValueError("quantile must be between 0 and 1")

    with (CONFIG_DIR / "stfpm.yaml").open("r", encoding="utf-8") as stream:
        config = yaml.safe_load(stream)
    config.update({"device": "auto", "image_size": 256, "pretrained": True})

    output = artifact_path("stfpm", args.category)
    model = create_model("stfpm", config)
    model.load(output)
    old_threshold = float(model.threshold)

    scores: list[float] = []
    train_dir = DATA_ROOT / args.category / "train" / "good"
    for path in image_paths(train_dir):
        tensor = load_tensor(path, model.size, True).unsqueeze(0)
        with torch.no_grad():
            anomaly_map = model._map(tensor)[0, 0].cpu().numpy()
        scores.append(float(np.quantile(anomaly_map, 0.99)))

    model.threshold = float(np.quantile(scores, args.quantile))
    model.save(output)
    record = {
        "model": "stfpm",
        "category": args.category,
        "method": "normal-training-score quantile",
        "score_statistic": "pixel anomaly map 0.99 quantile",
        "calibration_quantile": args.quantile,
        "normal_samples": len(scores),
        "old_threshold": old_threshold,
        "new_threshold": model.threshold,
    }
    record_path = output.with_name(f"{args.category}_threshold_calibration.json")
    record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(record, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
