# Claim evidence and bounded generation review

M5.1 retains the modular monolith, tenant-scoped retrieval, publication rules,
source revalidation, requester-only history and explicit human reply approval.
No schema migration, frontend contract change or new provider is required.

The original structural checks accepted valid labels attached to unsupported
claims. The first M5.1 candidate attached quotes and added a same-model critique,
but the critic returned five false booleans on every reviewed development draft.
Its zero generated answers were a utility failure, not a quality success.

`evidence-claims-4` makes an insufficient answer structurally incompatible with
nonempty claims during constrained decoding. An answered claim contains source
labels and supporting complete sentences before its answer text. Quotes match
whole tokens after whitespace normalization and map back to the original source
offsets. This tolerates newline formatting without accepting changed words,
numbers, punctuation, case or clipped conditions. Source authorization still
checks the original canonical excerpts; normalized matching grants no access.

Deterministic checks reject unknown labels, edited quotes, sentence fragments,
new numeric literals, repeated claims, question echoes and explicit instruction
payloads. These checks cannot prove semantic entailment. A second model call
gives a short rationale and one verdict for support, completeness, conflicting
sources or unsafe instruction-following. It is a fallible veto, not a confidence
score or the release-review judge. Critique rejection preserves authorized
source excerpts. It does not retry or silently repair the generated answer.

The two calls share a 600-output-token budget (450 draft, 150 critique), retain
the 4,096-token context, and use the remainder of a 60-second generation budget
for the critique. Source and membership checks run again before storage and
on reads. A changed source suppresses the answer even if the model approved it.

Instruction screening removes some explicit control-plane payloads from model
evidence, while ordinary policy imperatives remain valid. This is not a complete
prompt-injection detector. The model still has no tools, credentials, remote
fetch capability or mutation path. Conflicting active documents remain evidence
to resolve explicitly; rank order is not publication authority. Superseded
revisions are excluded by the existing database query.

The frozen original adapter is kept only in the evaluation scripts. A pinned
Qwen 3B research-model subclass also exists only there. The application continues
to select the pinned 1.5B profile and keeps its release gate closed. Comparative
inference uses a private Ollama process capped at 4 GiB and three CPU cores.

Evaluation artifacts retain rejected raw responses, selected sources and timing
counters for fictional data. Production workers have no observation callback
and log content-free categories only. Review records cover every evaluated
case, including abstention and fallback; no claims means no groundedness pass.
The release decision and limitations belong in RAG_EVALUATION.md. No gate is
weakened by this architecture change.
