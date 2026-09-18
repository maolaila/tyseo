"""Atomic evidence writes survive transient Windows file-handle contention."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from core import read_json, save_json


class JsonWrite(unittest.TestCase):
    def test_retry_locked_destination_without_losing_record(self):
        real_replace = os.replace
        attempts = []
        def replace(source, target):
            attempts.append((source, target))
            if len(attempts) < 3:
                raise PermissionError("temporary lock")
            real_replace(source, target)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "evidence.json"
            with patch("core.os.replace", side_effect=replace):
                save_json(path, {"status": "needs_review"})
            self.assertEqual(len(attempts), 3)
            self.assertEqual(read_json(path), {"status": "needs_review"})


if __name__ == "__main__":
    unittest.main()
