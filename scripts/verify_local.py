"""Start checksum-pinned CPU runtime and exercise the real adapter in one process namespace."""

import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path

from download_model import MODEL_SHA, RUNTIME_SHA
from live_smoke import run

from datarescue.dataset import Error
from datarescue.httpio import request_bytes


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--model-dir", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    root = a.model_dir.resolve()
    if sha(root / "model.gguf") != MODEL_SHA or sha(root / "runtime.tar.gz") != RUNTIME_SHA:
        raise RuntimeError("Model/runtime checksum mismatch")
    a.out.mkdir(parents=True, exist_ok=False)
    command = [
        str(root / "llama-b11718/llama-server"),
        "-m",
        str(root / "model.gguf"),
        "--host",
        "127.0.0.1",
        "--port",
        "18081",
        "--alias",
        "datarescue-qwen3",
        "-t",
        "4",
        "-c",
        "8192",
        "-np",
        "1",
        "-ngl",
        "0",
        "--reasoning-budget",
        "0",
    ]
    # No paid API or external data transport. Only an authored fixture is sent to loopback.
    with (a.out / "runtime.log").open("wb") as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
        try:
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError("Local runtime exited; inspect runtime.log")
                try:
                    status, _, _ = request_bytes("http://127.0.0.1:18081/health", timeout=2)
                    if status == 200:
                        break
                except Error:
                    pass
                time.sleep(0.5)
            else:
                raise RuntimeError("Local runtime did not become healthy")
            run(a.out / "smoke", "http://127.0.0.1:18081/v1")
        finally:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
    provenance = json.loads((root / "provenance.json").read_text())
    provenance.update(
        {
            "command": command,
            "runtime_executable_sha256": sha(root / "llama-b11718/llama-server"),
            "paid_api_calls": 0,
            "api_key_used": False,
        }
    )
    (a.out / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")


if __name__ == "__main__":
    main()
