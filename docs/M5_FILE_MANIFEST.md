# M5 changed files

- `backend/alembic/versions/0007_knowledge_assistant.py` adds the knowledge,
  assistant, and jobs schema, policies, and constraints.
- `backend/app/modules/knowledge/` owns canonical text, publication,
  retrieval, the local provider, API routes, and worker execution.
  `backend/app/platform/jobs.py` and `dispatch.py` implement durable leases.
- `frontend/src/features/knowledge/` implements Library, article editing,
  source inspection, job status, and Assistant. The shell, routes, and
  existing support composer connect to those views.
- `compose.yaml`, `infra/api.Dockerfile`, and the environment example
  configure separate worker processes and an optional private Ollama service.
  The locked `ai` dependency group is installed only for worker and evaluation
  runtimes.
- `backend/evaluation/`, `backend/scripts/evaluate_knowledge.py`, and the
  synthetic evaluation workflow contain the corpus and model comparison.
- The M5 unit, integration, and browser tests cover publication, isolation,
  fallback, citation invalidation, and the reviewed reply workflow.
  The M4-to-M5 migration check protects existing recorded events.
- OpenAPI and generated TypeScript contracts describe the new routes. The
  model manifest, architecture decision, roadmap, README, evaluation,
  and verification records describe the milestone and its release limits.
