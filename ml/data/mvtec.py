from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp"}


@dataclass(frozen=True)
class DatasetSummary:
    category: str
    train_good: int
    test_good: int
    test_anomaly: int
    masks: int

    @property
    def total_test(self) -> int:
        return self.test_good + self.test_anomaly


def _count_images(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for item in path.rglob("*") if item.suffix.lower() in IMAGE_SUFFIXES)


def inspect_mvtec_category(root: Path, category: str) -> DatasetSummary:
    category_dir = root / category
    if not category_dir.is_dir():
        raise FileNotFoundError(f"MVTec category not found: {category_dir}")
    train_good = _count_images(category_dir / "train" / "good")
    test_good = _count_images(category_dir / "test" / "good")
    test_root = category_dir / "test"
    test_anomaly = sum(
        _count_images(folder)
        for folder in test_root.iterdir()
        if folder.is_dir() and folder.name != "good"
    )
    masks = _count_images(category_dir / "ground_truth")
    if train_good == 0:
        raise ValueError(f"no normal training images found for {category}")
    return DatasetSummary(category, train_good, test_good, test_anomaly, masks)

