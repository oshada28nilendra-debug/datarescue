# DataRescue

**AI-assisted CSV cleaning you can inspect, approve and replay.**

For analysts, research assistants and small teams who need to fix messy exports without silently changing IDs, guessing date locales, or trusting model-generated Python. Python 3.11+, no runtime package dependencies, local-first CLI plus offline browser review screens.

Status: bounded first release. See [verification](docs/VERIFICATION.md) for actual checks, model limitations and publication status. This is not an autonomous data-correctness oracle or a substitute for domain review.

Repository: [oshada28nilendra-debug/datarescue](https://github.com/oshada28nilendra-debug/datarescue). The first release is being published on `feat/datarescue-first-release` for review. The publication check results are recorded in verification.

## What it does

1. Imports a small UTF-8 CSV, preserving every cell as a string, including `001`.
2. Profiles missing markers, whitespace, mixed value patterns, duplicates and suspicious formula/date values.
3. Uses offline rules, an imported recipe, or a genuine compatible AI model to propose allowed operations.
4. Lets you **accept, reject or modify** each proposal in a local HTML workbench or JSON.
5. Computes sequential cell-level changes and removed original record IDs before approval.
6. Exports only after an approval bound to that exact preview, rechecking the original input and all results.
7. Produces a cleaned CSV, audit, quality diagnostics, recipe and standalone reproducible Python script.

AI never supplies executable cleaning code. An understandable but incorrect suggestion can still pass schema validation: a person must assess its meaning.

## Quickstart: no model required

From the extracted source directory:

```bash
python -m venv .venv
# Linux/macOS; Windows: .venv\Scripts\activate
source .venv/bin/activate
python -m pip install .
datarescue plan --input fixtures/orders.csv --offline --out plan
```

Open `plan/review.html` in a browser. Each decision starts at **reject**. Choose accept/reject, or modify operation JSON. Download `review.json` and put it in the current directory. Alternatively copy `plan/review-template.json` and edit decisions by hand.

```bash
datarescue preview --input fixtures/orders.csv --proposals plan/proposals.json --review review.json --out preview
```

Open `preview/preview.html`. Inspect the full changes, invalid-date counts and removed records. Only if correct, check the approval box and download `approval.json`. Alternatively copy `preview/approval-template.json` and explicitly set `approve` to `true` with your local reviewer alias.

```bash
datarescue apply --input fixtures/orders.csv --preview preview/preview.json --approval approval.json --out export
python export/clean.py fixtures/orders.csv replay.csv
```

Every output directory/file must be new. No in-place edits. The standalone replay requires the **exact original bytes**, and checks the resulting hash. It needs only Python's standard library, not an installed DataRescue package.

For a scripted, clearly labelled test demonstration rather than human review:

```bash
PYTHONPATH=. python scripts/offline_demo.py --out demo
```

Expected fixture outcome when the documented recipe is approved: five records become four; `001` remains `001`; `pendng` and `Pending` become `pending`; `03/04/2026` becomes `2026-04-03` only because the recipe explicitly specifies day/month/year; `not-a-date` remains unchanged and is counted. Formula-looking `=1+1` remains raw in canonical output and is prefixed in the separately labelled spreadsheet variant.

## AI-assisted proposals

DataRescue speaks compatible `/v1/chat/completions` HTTP JSON. Start your own local server, then:

```bash
datarescue plan --input fixtures/live-status.csv --model datarescue-qwen3 --share-column status --out ai-plan
```

Default endpoint: `http://127.0.0.1:18081/v1`. By default, only headers, counts and diagnostic metadata are sent, **not example cell values**. `--share-column status` deliberately shares up to eight short distinct values from that column; up to four columns can be shared. Headers and aggregate statistics can themselves be sensitive. Local proposal/audit files contain actual data: keep them private.

Remote model use requires HTTPS and explicit consent:

```bash
# Configure DATARESCUE_API_KEY privately through your shell/secret manager, never in source.
datarescue plan --input input.csv --model YOUR_MODEL --endpoint https://YOUR_PROVIDER/v1 --allow-remote-model --out ai-plan
```

Remote providers may charge you and retain data; review their terms first. No paid API was used for this delivery. No built-in search, upload service or telemetry. The adapter does not use proxy environment variables or follow redirects. TLS verification is enabled. DNS resolution is a system prerequisite outside the absolute socket I/O deadline.

For the checksum-pinned local model test (Linux x64, Python 3.12+, about 2 GB download plus CPU/RAM):

```bash
python scripts/download_model.py --out ../datarescue-model
PYTHONPATH=. python scripts/verify_local.py --model-dir ../datarescue-model --out live-evidence
```

This downloads official Qwen3-1.7B Q8_0 and llama.cpp b11718, verifies SHA-256, starts a loopback-only CPU server, executes the real adapter, and retains evidence. It is a synthetic smoke check, not a benchmark. It can fail if the model produces unusable suggestions; failures are not converted to mock successes. See `delivery/` for this run's actual results and earlier unsuccessful gate attempt.

## Supported recipe operations

| Kind | Parameters | Behavior / risk |
|---|---|---|
| `trim` | `column` | Strip surrounding whitespace; spaces may be meaningful |
| `blank_markers` | `column`, `markers` | Replace only exact listed strings with empty text |
| `replace_exact` | `column`, `mapping` | Exact old→new string map; no fuzzy guessing |
| `case` | `column`, `mode` | Explicit `lower` or `upper` |
| `date_iso` | `column`, `format` | Explicit format to ISO; invalid values retained and counted |
| `drop_exact_duplicates` | none | Keep first identical whole record after preceding operations |

Each operation also requires `kind`; unknown fields are rejected. Date formats: `%Y-%m-%d`, `%d/%m/%Y`, `%m/%d/%Y`, `%Y/%m/%d`. Up to 12 operations, 50 mapping pairs and 32 missing markers. Exact mapping keys/values are at most 200 characters. Repeated records may represent legitimate transactions. Nothing infers missing values or repairs ambiguous dates automatically.

Example reusable recipe (`fixtures/recipe.json`):

```json
{"operations":[{"kind":"trim","column":"status"},{"kind":"replace_exact","column":"status","mapping":{"pendng":"pending","Pending":"pending"}}]}
```

Apply a recipe to another batch only by making **new unapproved proposals**:

```bash
datarescue plan --input next-batch.csv --recipe export/recipe.json --out next-plan
```

This does not reuse old approval. Review and preview again.

## Output contract

`plan`: `proposals.json`, `profile.json`, `review-template.json`, `review.html`.

`preview`: `preview.json`, `preview.html`, `approval-template.json` with `approve:false`.

`apply`: `cleaned.csv` (canonical raw values), `spreadsheet.csv` (separate apostrophe-prefix variant), `recipe.json`, `audit.json`, `quality.json`, `clean.py`.

CSV serialization is canonical UTF-8/LF; original quoting, BOM and line-ending style are not preserved. Values and original source file are preserved unless an approved operation changes them. Original record IDs are 1-based data records, not physical line numbers for multiline cells. Quality counts are diagnostics, not proof of correctness. Changes can legitimately increase a warning count.

**Do not open untrusted `cleaned.csv` directly in spreadsheet software.** Formula-prefix detection is conservative (including negative numbers); the separate spreadsheet variant is not a universal protection across applications or re-saves. See [security](SECURITY.md).

## Limits and failure behavior

UTF-8 comma-delimited CSV only: 2 MB input, 5,000 records, 50 columns, 100,000 cells, 4,096 characters/cell, 200/header. Reject duplicate/blank headers, ragged rows, malformed quoting, NULs, symlink/non-regular input. Preview change-audit budget: 2 MB. JSON input budget: 4 MB. Model context: 24 KB; response: 128 KB; max 2 calls and 2,048 generated tokens per call; I/O timeout up to 120 seconds. No retries by default.

Exit `0`: command produced its documented artifact, not a correctness guarantee. Exit `2`: refused invalid/stale input, unsafe configuration, unavailable path or other input/output error. Exit `3`: a proposal bundle was written with model errors/rejected operations; inspect it, do not treat it as success or approval. A valid empty model proposal means abstention. Output filesystem failure may leave a partial new bundle; it is not a completed export.

## Architecture

`dataset.py`: bounded string-preserving CSV / diagnostics. `engine.py`: pure finite transformations / deltas. `provider.py` + `httpio.py`: real bounded model transport. `workflow.py`: unapproved proposals, strict review, exact preview, approval and recomputation. `render.py`: static local review UI, escaped JSON and DOM text. `export.py`: fixed trusted engine plus literal JSON recipe. `cli.py`: file boundary / exclusive output bundles.

One model call can help resolve categorical variants; no agent swarm or vector database is justified here. The deterministic engine, model adapter and user decisions remain separate. See [validation](docs/VALIDATION.md) for alternatives and why this differs from DataLens.

## Development

```bash
python -m pip install ruff==0.17.1 build==1.6.1
python -m unittest discover -v
python -m ruff check .
python -m ruff format --check .
python -m compileall -q datarescue scripts tests
python -m build --wheel
```

CI definitions are included but not claimed to have run remotely. [Contributing](CONTRIBUTING.md) · [Security](SECURITY.md) · [MIT license](LICENSE) · [Licenses/provenance](docs/LICENSES.md) · [Handoff](docs/HANDOFF.md).
