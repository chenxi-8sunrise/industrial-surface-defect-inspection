from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ml.data.mvtec import inspect_mvtec_category


DATA_ROOT = ROOT / "data" / "raw" / "mvtec_ad"
EXPECTED = {
    "bottle": {"train_good": 209, "test_good": 20, "test_anomaly": 63, "masks": 63},
    "tile": {"train_good": 230, "test_good": 33, "test_anomaly": 84, "masks": 84},
    "transistor": {"train_good": 213, "test_good": 60, "test_anomaly": 40, "masks": 40},
}


def main() -> None:
    summaries = {}
    complete = True
    for category, expected in EXPECTED.items():
        summary = inspect_mvtec_category(DATA_ROOT, category)
        actual = {
            "train_good": summary.train_good,
            "test_good": summary.test_good,
            "test_anomaly": summary.test_anomaly,
            "masks": summary.masks,
        }
        summaries[category] = {"actual": actual, "expected": expected, "complete": actual == expected}
        complete = complete and actual == expected
    print(json.dumps({"complete": complete, "categories": summaries}, ensure_ascii=False, indent=2))
    if not complete:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
