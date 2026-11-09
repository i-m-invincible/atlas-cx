# Knowledge publication and the support copilot

## Approved revisions

A document holds active and pending pointers that are constrained to revisions
of that same document and workspace. Managers and administrators can save
drafts. Publishing freezes the title, canonical text, checksum, provenance, and
publisher. The pending pointer records publication intent. The prior active
version stays readable while the worker runs or if indexing fails.

Pasted and UTF-8 TXT or Markdown text becomes LF-delimited canonical text.
Canonical offsets count Unicode code points and the checksum hashes UTF-8
bytes. The worker preserves headings, prefers paragraph boundaries, and uses
the pinned MiniLM tokenizer for at most 180 content tokens and 30 tokens of
overlap. Heading prefixes and special tokens fit within 256 encoder tokens.
The pinned ONNX model applies attention-mask mean pooling and L2 normalization.
The worker verifies the staged chunk count, finite 384-dimensional vectors, and
the source checksum. Under a workspace lock it checks the 500-document and
10,000-chunk caps before activating a complete revision. Archive clears both
pointers and cancels pending publication.

## Durable work and access

The API saves the request and job together. The dispatcher claims rows with
`SKIP LOCKED`, using a 120-second lease and a random attempt token. It uses
`atlas_queue`, which has no document, case, identity, or answer privileges.
The worker uses the non-owner application role in the claimed workspace to
read and commit domain data. It renews the lease every 15 seconds while work
is within its deadline. A stale attempt cannot publish or commit an answer.
Index failures can retry four times in total with scheduled backoff. One out
of four successful claims gives indexing priority. Assistant generation has
one attempt, with a 60-second network timeout and a 90-second processing
budget. The maintenance process fails expired requests and purges question,
answer, citation, and feedback bodies after 30 days.

Forced policies protect each new tenant table, with composite tenant foreign
keys to preserve provenance. Staff can search active revisions. Managers can
read draft history. Assistant history and feedback are private to the
requester. Before retrieval and again before completion the worker verifies
workspace, membership, and the originating staff session. Normal case and
customer permissions remain in their existing services.

## Retrieval, generation, and drafts

PostgreSQL ranks English full-text matches using normalized query lexemes.
Exact cosine retrieval uses active chunks at the pinned embedding revision.
Reciprocal rank fusion combines the top 20 from each list with `1/(60 + rank)`.
Document ID and ordinal break ties. Admission uses cosine similarity of 0.45
or a positive lexical match. The evidence builder removes overlap, selects up
to six chunks and three per article, and caps evidence at 1,400 generation
tokens. Missing embeddings lead to lexical excerpts. Empty evidence leads to
abstention.

Only the question and labelled approved excerpts enter the local generation
prompt. The adapter has no tools and accepts structured claims with source
labels. Citation checks confirm labels and exact source slices. These checks
cannot establish that a claim follows from its evidence. On storage and
reads, active source references are checked again. A changed source suppresses
the answer and affected excerpts. The original provenance IDs remain internal.

The case link opens the Assistant and provides a route back to the same case.
Use draft rechecks the answer and the case, then transfers text through
current-tab memory to the public composer. The case service still requires
an explicit Send reply action and its usual authorization and version checks.
Source passages and answer text render as text, with internal links limited
to known citations.

Generation is disabled by default. The pinned model can run in an isolated
evaluation environment. See the evaluation record for the release decision.
