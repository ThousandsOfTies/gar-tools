from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


WEB_BRIDGE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WEB_BRIDGE_DIR))

from metrics import MAX_METRICS_BYTES, MetricsError, load_metrics  # noqa: E402


class MetricsTest(unittest.TestCase):
    def test_loads_regular_json_object(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "test-product.json").write_text(json.dumps({"frames": {"sent": 3}}), encoding="utf-8")
            self.assertEqual({"frames": {"sent": 3}}, load_metrics(root, "test-product"))

    def test_rejects_missing_symlink_large_and_non_object_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(MetricsError, "does not exist"):
                load_metrics(root, "test-product")
            target = root / "target.json"
            target.write_text("{}", encoding="utf-8")
            (root / "test-product.json").symlink_to(target)
            with self.assertRaisesRegex(MetricsError, "non-symlink"):
                load_metrics(root, "test-product")
            (root / "test-product.json").unlink()
            (root / "test-product.json").write_bytes(b"x" * (MAX_METRICS_BYTES + 1))
            with self.assertRaisesRegex(MetricsError, "size limit"):
                load_metrics(root, "test-product")
            (root / "test-product.json").write_text("[]", encoding="utf-8")
            with self.assertRaisesRegex(MetricsError, "root must be an object"):
                load_metrics(root, "test-product")
            (root / "test-product.json").write_text('{"value":NaN}', encoding="utf-8")
            with self.assertRaisesRegex(MetricsError, "valid JSON"):
                load_metrics(root, "test-product")
            with self.assertRaisesRegex(MetricsError, "application name"):
                load_metrics(root, "../outside")


if __name__ == "__main__":
    unittest.main()
