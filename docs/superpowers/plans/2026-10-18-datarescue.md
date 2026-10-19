# DataRescue Implementation Plan

> Use superpowers:executing-plans inline with test-first checks and an independent final review.

Goal: produce approved deterministic CSV cleaning and portable replay with real optional AI proposals.
Architecture: separate CSV/profiling, transformation engine, workflow integrity, model transport, rendering and CLI.
Tech stack: Python >=3.11 standard library; optional Ruff for development.
Spec: docs/superpowers/specs/2026-10-18-datarescue.md

## Constraints and review focus

2 MB/5000 records/50 columns/100000 cells/4096 chars per cell/200 per header. 12 operations, 50 mappings, 32 markers, 2 model calls, <=2048 completion tokens and <=120 seconds I/O excluding DNS. Output directories must be new.

Check malicious JSON types/unknown keys; duplicate/drop effects after earlier transforms; approval/preview tampering; CSV formulas/XSS; standalone replay divergence and private sample disclosure.

## Task 1 — deterministic core

Files: datarescue/dataset.py, datarescue/engine.py, tests/test_core.py.
Interfaces: load_csv(Path) -> Table; profile(Table) -> dict; validate_operation(dict, headers) -> dict; transform(Table, operation) -> (Table, delta).
- [ ] Write tests for CSV constraints, leading zeros, profiling and every operation including invalid dates and duplicates.
- [ ] Run them and observe missing behavior fail.
- [ ] Implement the bounded table and engine.
- [ ] Run the entire core suite and inspect exact deltas.

## Task 2 — review and approval flow

Files: datarescue/workflow.py, datarescue/provider.py, datarescue/httpio.py, tests/test_workflow.py, tests/test_provider.py.
Interfaces: propose(Table, provider=None, share_columns=[]) -> proposal; preview(Table, proposal, review) -> preview; approved_result(Table, preview, approval) -> Table.
- [ ] Test strict proposal schema, explicit selection/modification, recomputed preview, stale hashes and malformed/unsupported model output.
- [ ] Test real simulated HTTP serialization/deadline/error paths and value-sharing policy.
- [ ] Implement with finite operations; retain rejected model proposals and generic errors.
- [ ] Run suite and preserve offline/mock/live distinctions.

## Task 3 — user flow, replay and deliver

Files: datarescue/cli.py, datarescue/render.py, datarescue/export.py, tests/test_cli.py, scripts/live_smoke.py, README and CI.
- [ ] Test CLI E2E and no-overwrite; generated standalone script must replay identical bytes and reject changed source.
- [ ] Test report escaping and formula-oriented export policy.
- [ ] Implement browser review/approval downloads, exports and standalone fixed engine.
- [ ] Run actual offline and live-model demos; inspect output semantics and hashes.
- [ ] Run all tests/lint/format/compile/wheel/installed CLI/secret scan; independent review then one regression-tested fix pass.
- [ ] Package source and evidence, update the actual 27-slot ledger, document repository blocker.
