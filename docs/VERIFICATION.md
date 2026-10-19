# Verification — DataRescue, 18 October 2026 evening

## Latest result — GitHub publication verified, 19 October

Bounded release status: **verified, PR #1 open for user review/merge**. Implementation commit `f97a20386ed09dd4d96e5c14255d265e06e522dd` is published on `feat/datarescue-first-release`; its tree matches the prepared local release. The following evidence/documentation commit changes no implementation behavior.

- [Ordinary CI and browser](https://github.com/oshada28nilendra-debug/datarescue/actions/runs/39179045342): 36 tests passed, zero skips, per Python 3.11/3.12/3.13, plus lint, formatting, compilation, wheel installation and offline cleaning/replay. All three decoded Python job logs were inspected.
- The same run's actual Chromium 149.0.7827.55 job passed: five proposals default to reject; accept/reject/modify decisions download correctly; the operation editor enables for modification; unchecked approval is blocked; explicit approval downloads with the matching digest; no browser page errors were reported. The prior browser execution blocker is resolved. This is a synthetic headless check, not user research or an accessibility certification.
- [Real local-model CI](https://github.com/oshada28nilendra-debug/datarescue/actions/runs/39179045344): checksum-pinned llama.cpp b11718 + official Qwen3-1.7B Q8_0, one actual request (697 prompt / 224 completion tokens). The fictional categorical repair passed scripted review/preview/export and byte-identical replay. Its invalid per-column duplicate-removal suggestion was rejected; unnecessary trims were not selected. No paid model API/key was used.

The actual downloaded model artifact matched the GitHub SHA-256 digest. Its proposals, preview, canonical output and replay were inspected; the output hash is `aa1f99fb5e48ddac7b921aa327e27dc28503a619b4de82ae0be5484dc780c576`. The exported fixed-engine script was replayed locally again and produced that exact hash. Retained artifacts: `delivery/github-live-model/` (the actual exported Python source uses a `.txt` suffix to preserve it as evidence). Machine-readable evidence and browser checks: `delivery/github-verification.json`. A local Gitleaks scan passed before publication.

The user explicitly permitted publication after changing email privacy on 19 October. New API-created commits use the account email in public metadata; the earlier noreply local bundles are separate commits. PR review/merge remains with the user. No broad efficacy, complete-security or production-readiness claim is made. Remote paid-provider behavior and real-world business-rule accuracy remain unevaluated.

## Historical archive-stage records

## Publication continuation — designated repository

The user designated `oshada28nilendra-debug/datarescue` on 18 October. The repository had only its initial README, with no license or AGENTS instructions. The archive was restored on `feat/datarescue-first-release`, using the verified GitHub noreply email for commits. Hosted CI and PR results are pending first publication. Ordinary CI now includes a real Chromium review/download check, and the separate real local-model workflow also runs for same-repository implementation PRs. Historical statements below that no repository was designated refer to the archive checkpoint.

Status: **implementation delivered; local model fixture verified; browser and repository checks outstanding**. No production-readiness, complete-security or general cleaning-accuracy claim.

## Actual executed checks

The final local check runner is `python scripts/verify_release.py`. It records commands, exit codes, Python version, wheel hash and logs in `delivery/verification.json` and `delivery/checks/`. Expected suite after independent-review regression fix: 36 tests, zero skips on this Linux/Python 3.12 environment. POSIX FIFO test is explicitly skipped on systems without named-pipe support; other Python versions are configured in CI, not locally exercised here.

The suite covers deterministic operations, preserved IDs and multiline strings, malformed CSV, size/cell bounds, missing/date/duplicate diagnostics, exact mappings, stale source/preview, reject-by-default, explicit approval, modification, forged preview recomputation, finite model schemas, provider authentication/rate-limit/malformed failures, sharing opt-in, actual loopback HTTP and redirect behavior, response-size bounds, absolute slow-drip timeout, script-breakout escaping, CLI end-to-end flow, output refusal, installed-independent standalone replay, and JSON FIFO/symlink rejection. Model wire-format tests use labelled test doubles, not live calls.

Ruff check/format, compileall, wheel build, isolated target installation outside the source directory, installed CLI profile, and installed CLI scripted offline flow/replay are checked separately. The fixed engine is shipped in the wheel and included literally in exported scripts; no model-generated code is executed. Gitleaks 8.30.1 `dir` scan is retained as `delivery/gitleaks.json`; no secrets are intentionally configured in this project. A clean scanner result is not proof no sensitive information could exist or be disclosed in future user data.

## Offline authored demonstration

`delivery/offline-demo/` retains original plan, explicitly SCRIPTED test review/approval, preview, exported cleaned/spreadsheet CSV, recipe, audit and standalone replay. Five records become four. Sequential changed-cell counts are 1, 2, 1, 4, 0; final step removes original record 5. One invalid date remains and is counted. Leading-zero IDs remain intact. The replay matches canonical output bytes, SHA-256 `c04546cbaae131ea2d43de6349a7ef6960cca3305ca0da3c6d7e59d0171bbd7e`.

## Actual local model integration

Official Qwen3-1.7B Q8_0 with llama.cpp b11718 ran on CPU, loopback only, with checksum-verified runtime archive and model weights. `scripts/download_model.py` pins URLs and SHA-256. `delivery/live-model-attempt-2/provenance.json` retains executable hash and runtime command; runtime logs are retained. No DATARESCUE_API_KEY was configured and no paid API was used. The model was not supplied arbitrary real customer data.

Final gate: **one real compatible HTTP request**, 697 prompt tokens, 224 completion tokens, 921 total as reported by the runtime. The model proposed a `replace_exact` repair of fictional `pendng`/`Pending` to `pending`, plus identity mappings. The scripted fixture reviewer selected only that operation, recomputed/approved its preview, exported, and replayed byte-identically. Leading-zero ID `001` remained intact. Actual output hash: `aa1f99fb5e48ddac7b921aa327e27dc28503a619b4de82ae0be5484dc780c576`.

The model also suggested unnecessary trimming and an invalid `drop_exact_duplicates` operation with a column parameter. The validator rejected the invalid operation; the fixture reviewer rejected unnecessary suggestions. This demonstrates why schema checks and human domain review are both required. It does not prove all valid model suggestions are useful or safe.

An earlier actual call produced the same useful repair but the initial smoke gate was too strict about identity mappings and failed. `delivery/live-model-attempt-1/` retains that result and runtime log. The gate was corrected to accept the observed harmless identity pairs, not to bypass operation validation. Across the two attempts: two actual inference calls, each 697/224 tokens. Only the final run completed the full gate. Scripted approval is not represented as actual human review. No benchmark dataset or efficacy rate was measured.

## Not verified / not implemented

- Browser execution/visual/accessibility: blocked. Playwright module was available, Chromium was absent, and the browser download failed with invalid/truncated archives. `scripts/browser_smoke.cjs` is supplied but has not passed. Render escaping tests do not prove browser interactions.
- Hosted CI, publication, PR, deployment: not run/created; no designated DataRescue repository. CI files are supplied only.
- Remote model/TLS/authentication: real adapter implemented; failure-path tests passed, but only local HTTP inference was actually exercised.
- General business-rule correctness, hallucination rate and performance on real/large datasets: not measured. No claim of statistical efficacy.
- No fuzzy entity resolution, imputation, automatic date-locale inference, arbitrary Python proposal, Excel import, cloud sync, authenticated multi-user approvals or large-file streaming.

See `REVIEW.md` for the independent finding and regression-tested fix; `HANDOFF.md` for publication and follow-up steps.
