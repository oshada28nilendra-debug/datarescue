# Licenses and provenance

Original DataRescue code: MIT, `LICENSE`. No runtime pip dependencies. Python standard-library components are supplied by the user's Python distribution, not copied into this source package.

`datarescue/httpio.py` adapts the author's MIT-licensed EvidenceRoom transport from the 18 October delivery, with a package-local Error import. It contains no third-party copied competitor implementation. EvidenceRoom's original author/license is the same Oshada Nilendra MIT notice.

Optional local-model verification downloads are **not bundled**:

- llama.cpp b11718, MIT: https://github.com/ggml-org/llama.cpp/blob/master/LICENSE ; checksum-pinned release URL in `scripts/download_model.py`.
- Official Qwen3-1.7B-GGUF Q8_0, Apache-2.0 as declared by the official model card: https://huggingface.co/Qwen/Qwen3-1.7B-GGUF ; pinned revision `90862c4b9d2787eaed51d12237eafdfe7c5f6077`. Review its card, license, compute requirements and intended-use limitations before deployment. No redistribution of weights is done here.
- Development-only Ruff 0.17.1 (MIT), build 1.6.1 (MIT), setuptools (MIT): installed through pip, not vendored into this source package. CI pins tool versions and runs without application secrets.

Competitors and research in `VALIDATION.md` are referenced, not reused as source, data or model weights. Fictional fixtures were authored for this project and released under the repository MIT license. No external evaluation dataset was used.
