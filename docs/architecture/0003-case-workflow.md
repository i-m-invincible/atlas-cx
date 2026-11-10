# Case workflow and portal boundary

Status: implemented for M2. This extends the historical M1 decision record.
The authoritative specifications and wireframe PDF remain unchanged.

## Transaction and concurrency

The cases module owns cases, messages, resolution cycles, transitions, read
markers, and workspace case-number counters. The workspace module owns published
case configuration. The additive `0004_case_workflow` migration uses frozen DDL
and defaults so future ORM changes cannot rewrite an old migration's behavior.
Existing workspaces with an active administrator receive the default published
configuration; operator bootstrap seeds it for new workspaces. Publication is
immutable at the database boundary. M2 provides read-only defaults; the
configuration editor and five-preset catalog belong to M3.

Each mutation commits the case, message, cycle, transition, audit event, and
idempotency metadata together. Case numbers use a locked per-workspace counter;
UUIDs identify API resources. Messages use a database sequence for stable ascending
ordering. Application-role grants prohibit updates and deletes on messages and
transitions. A resolution remains attached to its original cycle when reopening
creates the next cycle.

Mandatory `If-Match` versions detect a stale editor or competing claim. Missing
versions return 428 and stale versions return 409. Creation, messages, and state
transitions also require an `Idempotency-Key`. For 24 hours, the same principal,
concrete route, key, and canonical payload replay the committed result without
another message or transition. Changed payloads conflict. Replay checks run after
current authorization and before version/state checks; an old key cannot recover
revoked access. Only hashes and resource references are retained, not secret
response bodies. Idempotency prevents duplicate retries; versions prevent lost
updates. They solve different problems.

The existing user/workspace/session lock order is retained. Authenticated work
still serializes conservatively within a workspace. Concurrency correctness is
tested; throughput and capacity have not been measured. No external service calls
occur inside these transactions.

## Privacy and authorization

Every new tenant table has forced RLS. Composite foreign keys prevent cross-tenant
references and enforce that a requester belongs to the case's customer. Staff
visibility is workspace-wide; teams constrain eligible assignment rather than
creating private case silos. Viewers can read and advance their own read marker.
Administrators and managers can close a resolved case; agents cannot close it.

Portal RLS permits only cases belonging to the verified contact and public
messages in those cases. It grants no direct portal writes or access to internal
configuration, cycle history, idempotency records, or read markers. A contact
sharing the same customer receives no access to another contact's requests.

A portal service first resolves the owned case or bound contact under portal
RLS. It then enters the bounded `case_storage` context using the same non-owner
application role and verified workspace, temporarily selecting staff storage
scope for the atomic internal writes and projection. The repository retains its
explicit requester predicate during this context. The context flushes before
restoring portal scope; pooled connections retain no scope after transaction end.
This is trusted service code, not a client-selectable audience or database role
escalation. Direct SQL integration tests verify that ordinary portal scope fails
closed on private rows and writes.

Separate staff and portal response models provide a second boundary. Portal
responses omit owner, team, customer records, priority, internal activity times,
targets, private history, and hidden field definitions/defaults. Portal message
responses can contain only public visibility. Portal list ordering uses creation
time, so a private note cannot become a visible activity signal.

Role deactivation/demotion transfers active responsibilities atomically. Team
changes reject incompatible active assignments. Archiving a customer or contact
with active cases is rejected. Closed cases reject edits, messages, and state
changes; the portal offers a related new request instead.

## States and clocks

Semantic states are fixed: new, open, pending_customer, resolved, and closed.
Opening requires an eligible active assignee. A first public staff response can
open and claim a new case. Asking for information posts a public question in the
same transaction that pauses resolution. A portal reply resumes pending work;
staff resumption needs a reason. Resolution requires an assignee, public summary,
resolution code, and any required pinned fields. An ordinary public reply cannot
silently reopen resolved work. Reopening requires an explicit staff reason or
portal message; closing requires a manager/administrator reason and is terminal.

Targets are snapshots of the creation configuration and priority. Subsequent
category, priority, and assignment edits do not reset them. First response starts
at creation, never pauses, and completes only on a qualifying public staff reply,
information request, or resolution. Internal notes and initial descriptions do
not count. Each resolution cycle has its own active elapsed time, excluding
pending-customer pauses. Every exit from pending settles the pause, including
direct resolution. Overdue means strictly greater than the target. Paused work
shows remaining active time without a fixed due date. Reopening preserves prior
resolution records and uses the original target for the new cycle.

## Browser behavior

Support and portal routes load separately. Query keys include workspace and
audience. Visible pages poll every 15 seconds; hidden pages stop polling. Reply
and note drafts stay separately in memory. Delivery appears only after API
confirmation. Retries reuse the payload's key, and version conflicts require
explicit review and resubmission. Unsent drafts guard navigation and unload.
Read markers advance only after messages load and never move backwards.

At wide desktop sizes the queue and customer context are each 280px and the
conversation receives the remaining space. At 1024px, Details replaces the third
pane. Small layouts use queue → conversation navigation; Back restores filters
and the selected link's focus. Native dialogs contain keyboard focus, preserve
drafts on Keep editing, and occupy the viewport at 700px and below. Existing
Organic tokens, self-hosted fonts, visible focus, and reduced-motion rules apply.

M2 does not add ratings, tasks, CSV imports, event analytics, health computation,
knowledge retrieval, AI generation, or email delivery. The portal advertises no
rating capability. Release load/restore and full screen-reader review remain M7.
