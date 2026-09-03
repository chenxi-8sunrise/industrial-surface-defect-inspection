import tempfile
import unittest
from pathlib import Path

from ml.data.mvtec import inspect_mvtec_category


class MVTecInspectionTests(unittest.TestCase):
    def test_counts_normal_anomaly_and_masks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for relative in [
                "bottle/train/good/001.png",
                "bottle/train/good/002.png",
                "bottle/test/good/101.png",
                "bottle/test/broken/102.png",
                "bottle/ground_truth/broken/102_mask.png",
            ]:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"image")
            summary = inspect_mvtec_category(root, "bottle")
            self.assertEqual(summary.train_good, 2)
            self.assertEqual(summary.test_good, 1)
            self.assertEqual(summary.test_anomaly, 1)
            self.assertEqual(summary.masks, 1)
            self.assertEqual(summary.total_test, 2)

    def test_rejects_missing_category(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                inspect_mvtec_category(Path(tmp), "tile")


if __name__ == "__main__":
    unittest.main()

