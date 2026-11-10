# M5.1 handoff and future work

M5.1 evaluation handoff is saved; generation release is blocked. Generation
remains disabled. Do not start M6, merge, deploy, or weaken gates.

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

## Completed frozen confirmation

`knowledge-confirmation-v1.json` was authored after freeze commit 11c09b2.
It has 40 fictional questions: 15 direct, five multi-passage, ten unanswerable,
five conflict/outdated and five injection. The same assistant authored and
reviewed it; this is prospective confirmation, not independent human verification.
Do not treat these consumed questions as unseen in a future iteration.

[Run 42866139153](https://github.com/i-m-invincible/atlas-cx/actions/runs/42866139153)
completed on `0851beee269299d2343ebf300d12564a70ed59ad`. It ran the frozen M5
baseline and selected candidate on the same new corpus and the candidate on the
original held-out 20. No candidate changes followed confirmation. All reports,
raw drafts/rejections, excerpts, hashes, assistant reviews and resource counters
are checked into `backend/evaluation/results`.

- Original held-out: 33/33 supported claims, 8/13 complete answerable,
  10/13 generated answerable, 1/4 unanswerable abstention, 6/20 fallback.
- New corpus: 79/81 supported claims, 15/20 complete answerable, 18/20
  generated answerable, 0/10 unanswerable abstention, 15/40 fallback.
- New baseline: 27/61 supported claims, 1/20 complete answerable, 20/20
  generated answerable, 0/10 unanswerable abstention, 4/40 fallback.
- All retrieval support/citation checks passed; zero observed tenant disclosures.
  Candidate served no attack manipulation in sampled cases, but rejected drafts
  and the critic still followed hostile instructions. Two invented live facts
  passed the critic. Generation is not safe to enable.
- Local browser run: 39 passed, two timeout failures, five Compose skips. Both
  failures passed with two workers without assertion/timeout changes. Independent
  branch/PR CI at 0851bee passed 116 backend, 82 PostgreSQL, 29 frontend,
  41 deterministic browser and five real-stack Compose tests. Source hashes,
  migrations, contracts, lint, type checks and builds passed.

## Exact steps for a future session

1. Inspect Git status, latest commit and PR #1 checks. Preserve changes; never
   reset. Read AGENTS.md, both specifications, this handoff, failure analysis,
   RAG_EVALUATION.md, AI_MODELS.md and the saved reports/reviews.
2. Verify `GENERATION_RELEASE_APPROVED = False` and run the freeze verifier.
   Do not rerun completed experiments without a specific reproducibility need.
3. The next recommended work remains M5.1 release readiness, not M6: reliable
   answerability/abstention, retained conditions, conflict handling and a critic
   that neither accepts fabricated facts nor vetoes valid policy answers.
   Any new tuning must use development data and get a new candidate version.
4. Obtain independent human review of the saved actual responses and rubric.
   Ask a separate evaluator to author another unseen confirmation corpus after
   a future candidate is frozen. The current confirmation set is now consumed.
5. Reuse unchanged gates and resource caps. Do not relabel fallback as abstention,
   hide hard cases or use blanket abstention to pass. Generation stays disabled
   until credible independent evidence passes every critical gate.

No further experiment or M6 was started after this handoff. The final Git SHA
is available with `git log -1 --format=%H`; PR #1 tracks the saved handoff head.

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
