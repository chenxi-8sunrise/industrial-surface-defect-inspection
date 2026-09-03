from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ml.evaluation import evaluate_category
from ml.models import create_model

from train_model import CONFIG_DIR, DATA_ROOT, artifact_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate one trained model on one MVTec AD category.")
    parser.add_argument("model", choices=("cae", "padim", "patchcore", "stfpm"))
    parser.add_argument("category", choices=("bottle", "tile", "transistor"))
    args = parser.parse_args()

    with (CONFIG_DIR / f"{args.model}.yaml").open("r", encoding="utf-8") as stream:
        config = yaml.safe_load(stream)
    config.update({"device": "auto", "image_size": 256, "pretrained": True})
    model = create_model(args.model, config)
    model.load(artifact_path(args.model, args.category))
    metrics = evaluate_category(
        model,
        DATA_ROOT / args.category,
        args.category,
        ROOT / "artifacts" / "results" / args.model / args.category,
    )
    print(json.dumps(metrics.as_dict(), ensure_ascii=False, indent=2, allow_nan=True))


if __name__ == "__main__":
    main()
