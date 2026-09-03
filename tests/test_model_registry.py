import unittest

from ml.models.registry import MODEL_SPECS, list_models


class ModelRegistryTests(unittest.TestCase):
    def test_has_four_distinct_owner_models(self):
        self.assertEqual(set(MODEL_SPECS), {"cae", "padim", "patchcore", "stfpm"})
        owners = [spec.owner for spec in list_models()]
        self.assertEqual(sorted(owners), ["A", "B", "C", "D"])
        self.assertEqual(len({spec.class_name for spec in list_models()}), 4)

    def test_training_and_feature_models_are_both_present(self):
        flags = {spec.requires_training for spec in list_models()}
        self.assertEqual(flags, {False, True})


if __name__ == "__main__":
    unittest.main()

