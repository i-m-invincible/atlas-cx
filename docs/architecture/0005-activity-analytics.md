# 0005 Customer activity and operational reporting

## Ingestion and access

An administrator defines each event key and its scalar property rules. A key
may be disabled. Changing whether a definition counts as activity affects
future events. Earlier events retain their stored activity flag.

The ingestion credential is an opaque 256-bit random value. The API returns it
once, stores its SHA-256 digest, and displays only a prefix and metadata later.
The React form holds the one-time value in component state. The bearer endpoint
uses the exact digest to find a workspace and scopes its transaction before
reading customers or events. Staff operations keep the existing session, Origin,
and CSRF controls. Portal access never grants access to this timeline or reports.

The API bounds the streamed JSON body at 1 MiB, accepts 1 to 100 events, and
bounds each canonical property object at 8 KiB. It checks types, enabled
definitions, active external customer IDs, and inclusive occurrence limits of
90 days ago through five minutes ahead for new events. The database limits
batches per credential in one-minute windows. An authenticated batch that
fails a domain check still consumes rate capacity.

The unique key is workspace plus external event ID. SHA-256 covers the external
customer ID, event name, UTC instant, and sorted compact JSON properties.
Property ordering and timestamp offsets do not change identity. Different
scalar types and exact string contents are significant. The API returns
existing IDs for exact replays, including after a definition is disabled. A
conflict rolls back every event write in the batch. Ingestion locks the
workspace before the credential, sharing the ordering used by staff mutations.
This also serializes competing submissions of the same workspace ID. Events
write no identity, billing, or case fields.

Forced RLS constrains the new tenant tables and uses composite workspace foreign
keys. Staff read bounded event projections. Ingestion can look up eligible
customers and definitions, append events, and update the usage of its own key.
The application role cannot edit or delete event rows. Retention is a scoped
operator command using the migration role. It deletes rows received more than
180 days ago. Idempotency is bounded by retained event records.

## Reports

The report refreshes the existing staff session, then verifies session and
membership in a PostgreSQL repeatable-read transaction. All report queries use
one transaction timestamp for both `generated_at` and `as_of`. The overview
returns its trend from that transaction. A later drilldown or export uses the
same filters and a new read snapshot, as it is a separate request.

Date inputs use IANA local midnight. Offset timestamps are also accepted.
The window includes its start and excludes its end, spans at most 366 local
days, and defaults to 30 local calendar days including today. Observations
after the report time are excluded. Trend buckets use local calendar days or
Monday-start weeks and include zero counts. Current category and team filters
apply to historical records using their case's current assignment. Archived
customers remain in historical reports.

| Measure                        | Calculation                                                                                                                                                                                                     |
| ------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| New cases and category volume  | Case creation in the window. Category keys group across versions and use the latest pinned label in the cohort.                                                                                                 |
| Current backlog and unassigned | Current new, open, or pending cases. Unassigned counts new cases without an assignee. Neither count uses the creation window.                                                                                   |
| First response                 | Elapsed seconds from creation to first public staff response for responses in the window. Target met includes equality. Unanswered overdue is a separate current count.                                         |
| Resolution                     | Each cycle resolved in the window contributes elapsed seconds less pauses. Target met includes equality. Current overdue cycles use active elapsed time through as-of and paused cycles are counted separately. |
| Seven-day reopen               | Resolved cycles with at least seven elapsed days of observation are eligible. A subsequent cycle opened within seven elapsed days contributes to the numerator. Immature cycles are shown separately.           |
| CSAT and feedback coverage     | CSAT counts ratings 4 or 5 among submissions in the period. Coverage counts resolved cycles in the period with a rating submitted by as-of, including the immature cohort.                                      |
| On-time follow-ups             | Non-cancelled tasks due within the period and by as-of. The numerator completed by the due time.                                                                                                                |

PostgreSQL `percentile_cont` supplies median and p90. Interpolation may produce
fractional seconds. Empty duration and rate cohorts have null values and
explicit counts. Manager/admin exports cap at 10,000 records, include the report
scope and definition, neutralize spreadsheet formulas, and write an audit event.

## Storage and limits

The workspace/external ID unique index handles bounded replay lookups. The
workspace/customer/occurrence/ID index supports descending activity pages and
the workspace/receipt index supports retention. Workspace-leading time indexes
cover creation, first response, feedback submission, and task due cohorts.
An entity lookup index connects task audit history to the Customer 360 timeline.
Existing case, message, and resolution-cycle indexes serve the remaining joins.

Activity Analytics filters actual events for one customer. Service shows
operational measures. Health, cross-customer product-event aggregates, and
automated event retention scheduling are future work. No throughput or latency
benchmark was run for M4.
