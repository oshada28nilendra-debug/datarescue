"""Run fresh local checks, retain actual logs/status, and test installed wheel outside source."""

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    out = root / "delivery/checks"
    out.mkdir(parents=True, exist_ok=True)
    checks = {}

    def run(name, command, cwd=root, env=None):
        result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, timeout=180)
        (out / f"{name}.txt").write_text(result.stdout + result.stderr)
        checks[name] = {
            "exit_code": result.returncode,
            "command": command,
            "log": f"delivery/checks/{name}.txt",
        }
        print(name, result.returncode, flush=True)
        return result

    run("tests", [sys.executable, "-m", "unittest", "discover", "-v"])
    run("lint", [sys.executable, "-m", "ruff", "check", "."])
    run("format", [sys.executable, "-m", "ruff", "format", "--check", "."])
    run("compile", [sys.executable, "-m", "compileall", "-q", "datarescue", "scripts", "tests"])
    run("wheel", [sys.executable, "-m", "build", "--wheel"])
    wheel = root / "dist/datarescue_workbench-0.1.0-py3-none-any.whl"
    with tempfile.TemporaryDirectory(prefix="datarescue-install-") as tmp:
        target = Path(tmp) / "package"
        run(
            "install",
            [sys.executable, "-m", "pip", "install", "--no-deps", "--target", str(target), str(wheel)],
        )
        env = dict(os.environ, PYTHONPATH=str(target))
        run(
            "installed-profile",
            [sys.executable, "-m", "datarescue", "profile", "--input", str(root / "fixtures/orders.csv")],
            cwd=tmp,
            env=env,
        )
        run(
            "installed-e2e",
            [sys.executable, str(root / "scripts/offline_demo.py"), "--out", str(Path(tmp) / "demo")],
            cwd=tmp,
            env=env,
        )
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "python": sys.version,
        "checks": checks,
        "all_passed": all(c["exit_code"] == 0 for c in checks.values()),
        "wheel_sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
        "tests_expected": 36,
        "live_model_evidence": "delivery/live-model-attempt-2/smoke/verification.json",
        "remote_ci_run": False,
        "browser_execution_verified": False,
        "browser_blocker": "Playwright Chromium download returned invalid/truncated archives",
    }
    (root / "delivery/verification.json").write_text(json.dumps(report, indent=2) + "\n")
    raise SystemExit(0 if report["all_passed"] else 1)


if __name__ == "__main__":
    main()
