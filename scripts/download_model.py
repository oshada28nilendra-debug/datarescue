"""Deliberate download of checksum-pinned public runtime/model; no API credential.

Optional verification helper requires Python 3.12+ for safe tar extraction.
Runtime/model are external dependencies and are never bundled with source.
"""

import argparse
import hashlib
import json
import tarfile
import urllib.request
from pathlib import Path

RUNTIME = "https://github.com/ggml-org/llama.cpp/releases/download/b11718/llama-b11718-bin-ubuntu-x64.tar.gz"
RUNTIME_SHA = "99f83b15cea9a4fb8945516c276b5f42b11608f82104fc6fa98a541cac826de7"
MODEL = (
    "https://huggingface.co/Qwen/Qwen3-1.7B-GGUF/resolve/"
    "90862c4b9d2787eaed51d12237eafdfe7c5f6077/Qwen3-1.7B-Q8_0.gguf"
)
MODEL_SHA = "061b54daade076b5d3362dac252678d17da8c68f07560be70818cace6590cb1a"


def download(url, path, expected):
    sha = hashlib.sha256()
    with urllib.request.urlopen(url, timeout=40) as response, path.open("xb") as stream:
        while data := response.read(1048576):
            stream.write(data)
            sha.update(data)
    if sha.hexdigest() != expected:
        raise RuntimeError("Download checksum mismatch; do not execute downloaded content")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    download(RUNTIME, args.out / "runtime.tar.gz", RUNTIME_SHA)
    with tarfile.open(args.out / "runtime.tar.gz") as archive:
        archive.extractall(args.out, filter="data")
    print("Runtime checksum verified and extracted", flush=True)
    download(MODEL, args.out / "model.gguf", MODEL_SHA)
    metadata = {
        "runtime_url": RUNTIME,
        "runtime_sha256": RUNTIME_SHA,
        "model_url": MODEL,
        "model_sha256": MODEL_SHA,
        "model": "Qwen3-1.7B Q8_0",
        "runtime": "llama.cpp b11718",
    }
    (args.out / "provenance.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print("Official model downloaded and checksum verified", flush=True)


if __name__ == "__main__":
    main()
