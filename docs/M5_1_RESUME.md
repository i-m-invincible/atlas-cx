# M5.1 progress and resume instructions

Generation remains disabled. Do not start M6, merge, deploy, or weaken gates.

Branch: `feature/atlas-cx-development`. Candidate source commit:
`3e755750ad12b68477920497f72c6cea322138dd`. Freeze commit: `11c09b2`.
Candidate: pinned Qwen 2.5 1.5B, `evidence-claims-5`. The freeze manifest records
LF-normalized source hashes and the unchanged original corpus SHA-256.

## Completed work

- Preserved M0–M5 architecture, specifications, original 60 questions and 40/20 split.
- All three pending PostgreSQL regressions passed at `70d3ac4`, alongside all
  82 integration tests and five real-stack browser workflows in CI.
- Diagnosed the initial 38 fallbacks/two abstentions. The critic rejected valid
  drafts; exact newline matching caused one false rejection. Quote matching
  now normalizes whitespace only; the critic returns a reason and verdict.
- Compared pinned 1.5B and research-only 3B on the same 40 development questions
  with v4 and v5 decoding. No held-out tuning occurred. Reports and assistant
  review records are in `backend/evaluation/results`.
- Selected v5 1.5B: 63/63 supported claims, 19/27 complete answerable responses,
  26/27 generated answerable responses, but 2/6 unanswerable abstentions.
  v4 1.5B: 60/66 supported, 16/27 complete, 25/27 generated, 3/6 abstention.
  Both 3B trials answered only 1/27 answerable questions, none completely.
- Local v5 checks passed: 116 backend tests, Ruff, mypy, `npm run check`, 29
  frontend tests and build. Sandboxed TestClient stalled and was stopped;
  the loopback-enabled rerun passed. Skips are not passes.
- No production generation, migrations, frontend contracts, tenant boundary,
  source revalidation or human-approved reply workflow was changed.

## Confirmation in progress

`knowledge-confirmation-v1.json` was authored after freeze commit 11c09b2.
It has 40 fictional questions: 15 direct, five multi-passage, ten unanswerable,
five conflict/outdated and five injection. Organizations and policies are new.
It is separate from development data, but the author and reviewer are the same
assistant. This is prospective confirmation, not independent human verification.

The next model workflow evaluates the frozen candidate on the original 20
held-out questions and new corpus. The frozen M5 baseline runs on the same new
corpus with identical 4 GiB/three-core limits. Do not repeat completed development
experiments. The workflow checks frozen source hashes before inference.

## Next steps after an interruption

1. Inspect Git status, commits and Actions before starting anything. Preserve
   changes. Read AGENTS.md, both specifications, failure analysis and RAG docs.
2. Retrieve pending model/CI results and preserve all reports, including rejected
   raw outputs, source excerpts, token counts and timing. Avoid duplicate runs.
3. Review each served assertion/directive against its cited passage using the
   existing rubric. Score completeness separately; fallbacks are incomplete.
   Do not tune the frozen candidate on held-out or confirmation data.
4. Report all denominators, coverage and abstention. Critical failure keeps
   generation disabled. Independent human review is still outstanding.
5. Finish regression/CI verification; update RAG_EVALUATION.md, AI_MODELS.md,
   VERIFICATION.md, ROADMAP.md, ADR 0007 and this record. Commit/push, update
   PR #1, and stop at the M5.1 handoff. No M6 is authorized.

## Reproduction commands

Use an idle disposable migrated PostgreSQL/pgvector database with migration,
`atlas_app` and `atlas_queue` URLs. This host lacks usable Docker/Ollama; actual
model/database evidence comes from disposable GitHub Actions infrastructure.
From `backend`, with the pinned private Ollama runtime/model loaded:

```sh
uv sync --locked --group ai
uv run --group ai alembic upgrade head
uv run --group ai python -m app.modules.knowledge.prepare_models ../.runtime/models
uv run python -m scripts.verify_m51_freeze
uv run --group ai python -m scripts.evaluate_knowledge --generate --log-claims --partition held_out --models ../.runtime/models --output ../.runtime/held-out-evaluation.json
uv run --group ai python -m scripts.evaluate_knowledge --generate --log-claims --partition confirmation --corpus evaluation/knowledge-confirmation-v1.json --models ../.runtime/models --output ../.runtime/confirmation-evaluation.json
# Add --baseline to the same confirmation command for the frozen M5 comparison.
uv run python -m scripts.review_knowledge REPORT.json REVIEW.json
```

Model workflows require `[rag-eval]` in a push message or workflow dispatch.
Normal documentation pushes run CI without inference. Reviews require the
report SHA-256, honest reviewer identity/independence, and every case ID.
Zero claims cannot pass groundedness. Gates remain 85% retrieval, 90%
groundedness, 90% unanswerable abstention, 100% structural citations and zero
cross-workspace disclosures or unauthorized actions.
