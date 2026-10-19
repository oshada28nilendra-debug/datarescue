# DataRescue validation — 18 October 2026

Target users: analysts, research assistants and small organizations receiving recurring small CSV exports.
Pain point: inconsistent categories, whitespace, missing markers and dates require decisions; a plausible AI repair can silently change meaning. Repeatable cleaning also needs an inspectable recipe.

Evidence: [TabClean, 24 June 2026](https://arxiv.org/abs/2606.25388) describes recurring tabular errors and studies reusable guarded repair programs. [RRBench, 23 July 2026](https://arxiv.org/abs/2607.21482) studies local open-weight agents for governance-constrained data preparation. These are research evidence for the problem, not evidence that DataRescue outperforms them or has market demand.

## Alternatives inspected

| Alternative | Observed capability | Our bounded positioning |
| --- | --- | --- |
| [OpenRefine](https://openrefine.org/docs/manual/running/) | Local cleaning, clustering, operation history and JSON replay | A smaller finite-operation recipe whose exact preview and input hashes must match approval |
| [Microsoft Data Wrangler](https://code.visualstudio.com/docs/datascience/data-wrangler) | Visual exploration, change previews, editing and generated Pandas code | No generated Python from the model; export a fixed deterministic stdlib runner plus reviewed recipe |
| [DataPrep.Clean](https://docs.dataprep.ai/user_guide/clean/introduction.html) | Python cleaning and validation functions | Explicit human selection/modification and before/after evidence around a small allowed operation set |
| [TabClean](https://arxiv.org/abs/2606.25388) | LLM-synthesized reusable guarded Python repair programs | Schema-constrained operation proposals, no synthesized executable logic and mandatory human approval |

We do not claim previews, reusable recipes or local processing are novel. Existing tools may already satisfy many users. Our adoption/forking advantage is a hypothesis: a dependency-light, inspectable approval boundary may suit small auditable workflows.

Difference from the user's DataLens: profiling is support functionality here. The main outcome is approved cleaning, exact change/deletion previews, schema-bounded AI proposals, a cleaned CSV and a reproducible standalone script.

Feasibility: use Python's CSV/JSON/date libraries and a genuine compatible HTTP model adapter. Core transformations remain deterministic and run without a model. Real local inference will be checked separately from test doubles.

Risks: category mapping can be semantically wrong; duplicate records may be legitimate; date formats can be ambiguous; CSV formulas can be dangerous in spreadsheets; model suggestions can include malicious instructions or unsupported operations. Counts measure detected patterns, not ground-truth correctness. No automatic imputation, fuzzy entity merging or arbitrary code execution.

Decision: narrow and proceed with a local CLI plus browser review reports, a finite operation vocabulary, digest-bound acceptance and standalone replay. No designated repository exists; deliver the source package and publication steps.
