import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from datarescue.cli import main
from datarescue.render import render


class DeliveryTests(unittest.TestCase):
    def test_full_cli_approval_export_and_standalone_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "input.csv"
            source.write_text("id,status\n001, pending \n002,done\n002,done\n")
            original = source.read_bytes()
            plan, prev, out = [root / p for p in ("plan", "preview", "export")]
            self.assertEqual(main(["plan", "--input", str(source), "--offline", "--out", str(plan)]), 0)
            proposal = json.loads((plan / "proposals.json").read_text())
            review = {
                "proposal_digest": proposal["digest"],
                "reviewer": "test reviewer",
                "decisions": [{"id": p["id"], "decision": "accept"} for p in proposal["proposals"]],
            }
            reviewfile = root / "review.json"
            reviewfile.write_text(json.dumps(review))
            args = [
                "preview",
                "--input",
                str(source),
                "--proposals",
                str(plan / "proposals.json"),
                "--review",
                str(reviewfile),
                "--out",
                str(prev),
            ]
            self.assertEqual(main(args), 0)
            approval = json.loads((prev / "approval-template.json").read_text())
            approval["approve"] = True
            approvefile = root / "approval.json"
            approvefile.write_text(json.dumps(approval))
            args = [
                "apply",
                "--input",
                str(source),
                "--preview",
                str(prev / "preview.json"),
                "--approval",
                str(approvefile),
                "--out",
                str(out),
            ]
            self.assertEqual(main(args), 0)
            self.assertEqual(source.read_bytes(), original)
            self.assertEqual((out / "cleaned.csv").read_text(), "id,status\n001,pending\n002,done\n")
            result = subprocess.run(
                [sys.executable, "-I", str(out / "clean.py"), str(source), str(root / "replay.csv")],
                capture_output=True,
                timeout=20,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((out / "cleaned.csv").read_bytes(), (root / "replay.csv").read_bytes())
            self.assertNotEqual(main(args), 0)  # never overwrite export
            source.write_text("id,status\n001,changed\n")
            result = subprocess.run(
                [sys.executable, "-I", str(out / "clean.py"), str(source), str(root / "stale.csv")],
                capture_output=True,
                timeout=20,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((root / "stale.csv").exists())

    def test_html_cannot_break_out_of_data_script(self):
        payload = "</script><script>alert(1)</script><img src=x onerror=alert(1)>"
        page = render({"kind": "proposals", "digest": "a", "proposals": [], "evil": payload})
        self.assertNotIn(payload, page)
        self.assertIn("\\u003c/script", page)
        self.assertNotIn("innerHTML", page)

    def test_invalid_input_no_partial_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "bad.csv"
            source.write_text("a,a\n1,2\n")
            self.assertEqual(
                main(["plan", "--offline", "--input", str(source), "--out", str(root / "out")]), 2
            )
            self.assertFalse((root / "out").exists())
