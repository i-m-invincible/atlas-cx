# Resume the incomplete M5.1 checkpoint

Latest development evidence: v4 on pinned 1.5B generated 25/27 answerable cases,
with 60/66 supported reviewed claims and 16/27 complete answers. Unanswerable
abstention was only 3/6. The 3B model generated only 1/27 answerable cases,
with two supported claims but no complete answer. Neither is release-ready.
The checked-in review records explicitly identify the reviewer as the assistant,
not an independent human. A v5 development-only ablation removes conditional
decoding while retaining status consistency validation and the same safety gates.
Do not evaluate held-out or independent questions until the candidate is frozen.

Resumed at the user's request on 10 November 2026 (Asia/Kolkata). **M5.1 is
incomplete. Generation remains disabled. Do not start M6.**

Repository: `i-m-invincible/atlas-cx`; branch: `feature/atlas-cx-development`.
The last fully exercised implementation is
`b5bbdec933758e085b3b1273ac0ae91a33b5451b`. The pause was interrupted by the
resume request before a second commit. All saved changes remained in the tree.
The first resume commit preserves those changes and runs ordinary CI, including
the three pending PostgreSQL tests. Model evaluation now requires `[rag-eval]`
in a triggering push's commit message, or an explicit workflow dispatch.
Use `git log -1 --format='%H %s'` for the checkpoint's exact SHA.

## Preserved work and evidence

Resume progress: `70d3ac44e58fb260f1960c069359741a64a57e43` passed all 82
PostgreSQL integration tests, including the three pending M5.1 cases, and five
real-stack browser workflows in CI run 42797900573. Candidate `7639374` changes
only development-driven validation/prompt behavior and the evaluation framework.
Its 116 backend unit/HTTP tests passed locally. The `evidence-claims-4` development
comparison of pinned Qwen 1.5B and research-only Qwen 3B is running. The first
candidate's rejection diagnosis is recorded in M5_1_FAILURE_ANALYSIS.md.
Review those new results before changing the pipeline. The original held-out
questions have not been evaluated or used for tuning during this resume.

- M0–M5 application, migrations, frontend, Compose configuration and source
  specifications are unchanged. Source hash verification passed.
- The original 60-question corpus and its 40/20 partition are byte-identical
  to M5. SHA-256:
  `b9bfffce6fb5c70715ba87f7dafe4339bd6a4ca72ffc92792d6ddac8b175f0bb`.
- Original results remain in `RAG_EVALUATION.md`: held-out retrieval 13/13,
  citation validity 276/276, groundedness 17/36, unanswerable abstention 3/10,
  five manipulated injection responses, zero observed tenant disclosures.
- `M5_1_FAILURE_ANALYSIS.md` classifies every baseline response. The 56 original
  generated responses are preserved in `backend/evaluation/m5-baseline-responses.json`.
- Candidate `evidence-claims-3` adds an explicit schema and examples, claim-level
  supporting quotes, quote/reference/number/duplicate checks, filtering of some
  explicit document instructions, and a bounded second-call critique. Retrieval
  remains `rrf-english-1`. The critique is a heuristic veto, not an entailment
  guarantee or a substitute for manual review. Output budget is split 500/100
  tokens across the two calls. The runtime release gate is still false.
- A frozen M5 provider in `backend/scripts/m5_baseline.py` enables a consistent
  comparison. The evaluator can select a partition/corpus and retain rejected
  raw responses, source excerpts, similarity, and token counters. New review
  tooling requires all evaluated cases, counts fallback as incomplete, and
  refuses to pass groundedness with zero reviewed claims.

## Development-only evaluation completed before the pause

The already-running workflow completed successfully. This means the runner
finished, **not that the candidate passed quality gates**.
[Run 42687390335](https://github.com/i-m-invincible/atlas-cx/actions/runs/42687390335)

Its 40 actual records are preserved in
`backend/evaluation/results/m51-development-candidate1.json`, including raw
accepted/rejected provider responses. Redundant provider context token-ID arrays
were omitted when recovering the records from the job log. No claim-level
review or tuning against these new results has been performed yet.

| Measure                              | Observed candidate development result |
| ------------------------------------ | ------------------------------------- |
| Hybrid hit / all support             | 27/27 / 26/27                         |
| Structural source citation validity  | 181/181                               |
| Generated responses                  | 0/40                                  |
| Sources-only fallback                | 38/40                                 |
| Unanswerable abstention              | 2/6                                   |
| Observed cross-workspace disclosures | 0                                     |
| Generation-call latency p50 / p95    | 9.53 / 15.64 seconds                  |
| Direct end-to-end p50 / p95          | 9.27 / 14.95 seconds                  |

The candidate has not established useful generated answers. Do not interpret
zero served hallucinations as success. Diagnose the rejection traces first.
The recorded errors are `unsupported_claim` for 32 cases and `invalid_citations`
for six; the other two had no admitted evidence.
No new held-out or independent confirmation run has occurred. No new independent
dataset has been created. No stronger model has been run.

## Tests and CI

- At `b5bbdec`, Ruff lint/format, mypy and 112 backend unit/HTTP tests passed.
  `npm run check` passed, including 29 frontend tests and the production build.
  Local Chromium passed 41 tests and skipped five Compose tests.
- Both complete CI runs on that commit passed, including the original 79
  PostgreSQL/pgvector tests as `atlas_app`, queue-role tests, migrations,
  containers, contracts and five real-stack browser scenarios.
  [Branch CI](https://github.com/i-m-invincible/atlas-cx/actions/runs/42687390561) ·
  [PR CI](https://github.com/i-m-invincible/atlas-cx/actions/runs/42687399647)
- After that commit, the two new review-aggregation tests passed. The first
  resume commit passed the complete 114-unit/82-integration CI suite. The next
  candidate adds two unit checks (116 unit/HTTP tests passed locally).
- Local Docker/PostgreSQL/Ollama remain unavailable. Real database/model runs
  used disposable GitHub Actions infrastructure. No paid service or deployment
  was created. Nothing was merged to main.

## Exact next steps

1. Read AGENTS.md, PRODUCT_SPEC.md, DESIGN_SYSTEM.md, RAG_EVALUATION.md,
   AI_MODELS.md, VERIFICATION.md and this record. Confirm the branch, clean
   tree, false generation gate and original corpus hash. Do not reset changes.
2. Review the saved development report's `error` and `trace` fields against
   the actual sources. Determine why every attempted generation fell back.
   Fix only observed general failures, using the original development subset.
   Do not tune on the original held-out questions. Preserve every candidate's
   results, including rejected outputs and answerability/completeness failures.
3. Check the newly added evaluator/reporting code and tests. Run relevant unit
   tests, then the normal CI and the three new non-owner PostgreSQL tests.
   A normal development commit triggers CI. The model workflow is explicitly
   gated by `[rag-eval]` in the push commit message and currently evaluates
   **development only**. A workflow dispatch also runs it.
4. Compare the frozen original prompt and the improved candidate on the same
   dataset, artifacts and inference resources. The current workflow runs only
   development. Do not claim full evaluation from its green status.
5. If Qwen 1.5B remains inadequate, the investigated evaluation-only candidate
   is Qwen 2.5 3B Q4_K_M. It is **not configured or downloaded**. Its manifest is
   `sha256:357c53fb659c5076de1d65ccb0b397446227b71a42be9d1603d46168015c9e4b`;
   model layer is 1,929,903,008 bytes. Tokenizer revision
   `aa8e72537993ba99e69dfaafa59ed015b17504d1` has the same tokenizer checksum as
   the pinned 1.5B tokenizer. Official manifest/checksum/license were read.
   It has the Qwen research-only license. Do not silently replace the app model
   or assume commercial release rights. Enforce and measure the existing 4 GiB,
   three-core Ollama budget before a comparison. The first candidate runner
   selected three inference threads but did not impose a cgroup memory cap.
6. Freeze candidate source hashes before creating a separate, prospectively
   unseen confirmation corpus with new policies and attacks. Preserve the
   original 60 questions and held-out split. Evaluate baseline and candidates
   consistently, then review all emitted assertions/directives for support,
   conditions, completeness and manipulation. Author/reviewer independence
   must be disclosed; no independent human review exists yet.
7. Keep the existing release gates: at least 85% held-out retrieval, 90%
   groundedness, 90% unanswerable abstention, 100% structural citations, and
   zero disclosures or unauthorized actions. Report coverage, completeness,
   latency, costs and fallbacks. Reject an all-abstention/fallback outcome.
8. After evidence is credible, update all M5.1 records, architecture decisions
   and PR #1. If any critical gate fails, retain source-only release behavior.
   Do not start M6, merge or deploy.

## Evaluation commands

Run from `backend` against an **idle disposable migrated PostgreSQL/pgvector**
database, with `MIGRATION_DATABASE_URL`, `TEST_DATABASE_URL` (`atlas_app`) and
`QUEUE_DATABASE_URL` (`atlas_queue`) set. Never use production data. On this
Windows host, set `UV_CACHE_DIR` to a writable workspace cache if necessary.

```sh
uv sync --locked --group ai
uv run --group ai alembic upgrade head
uv run --group ai python -m app.modules.knowledge.prepare_models ../.runtime/models
uv run --group ai python -m scripts.evaluate_knowledge --partition development --models ../.runtime/models --output ../.runtime/retrieval-evaluation.json
# With the pinned private Ollama runtime/model available:
uv run --group ai python -m scripts.evaluate_knowledge --generate --log-claims --partition development --models ../.runtime/models --output ../.runtime/candidate-evaluation.json
uv run --group ai python -m scripts.evaluate_knowledge --generate --baseline --log-claims --partition development --models ../.runtime/models --output ../.runtime/baseline-evaluation.json
# Only after freezing the pipeline: use --partition all for the original 60;
# use --corpus PATH --partition confirmation for the separate new corpus.
uv run python -m scripts.review_knowledge REPORT.json REVIEW.json
```

The review file needs the report's SHA-256, reviewer identity, an honest
`independent_human_review` boolean and one entry per case with `id`,
`supported_claims`, `reviewed_claims`, `complete`, `manipulated`, and `notes`.
Do not infer groundedness from the model's critique flags.

Suggested resume instruction: "Resume the incomplete M5.1 checkpoint on
feature/atlas-cx-development. Follow docs/M5_1_RESUME.md, diagnose the saved
development-only rejection traces, and keep generation disabled until the
unchanged release gates have credible independent evidence. Do not start M6."
