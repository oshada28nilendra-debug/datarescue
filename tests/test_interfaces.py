import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from datarescue.dataset import Error, load_csv, profile, read_json


class BoundsTests(unittest.TestCase):
    @unittest.skipUnless(hasattr(os, "mkfifo"), "POSIX named pipes required")
    def test_json_fifo_is_rejected_without_blocking(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pipe.json"
            os.mkfifo(path)
            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "from datarescue.dataset import read_json, Error; import sys; "
                    "\ntry: read_json(sys.argv[1])\nexcept Error: sys.exit(2)",
                    str(path),
                ],
                capture_output=True,
                timeout=1,
            )
            self.assertEqual(result.returncode, 2)

    def test_json_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "data.json"
            path.write_text("{}")
            link = Path(tmp) / "link.json"
            link.symlink_to(path)
            with self.assertRaises(Error):
                read_json(link)

    def test_profile_values_are_bounded_and_marked(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "data.csv"
            path.write_text("note\n" + "x" * 1000 + "\n")
            value = profile(load_csv(path))["columns"]["note"]["value_counts"][0]
            self.assertEqual(len(value["value"]), 160)
            self.assertTrue(value["truncated"])
