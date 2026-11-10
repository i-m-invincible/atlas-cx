# Configuration, follow-ups, and customer imports

## Published configuration

Workspace administrators copy one of five starter definitions or edit a copy
of the current version. SaaS, service business, e-commerce, education, and
subscription business use the same schema and case service. Starter templates
carry categories, typed fields, state labels, and the specified priority
targets. Routing references are selected from the destination workspace's
active teams because team IDs cannot travel between workspaces.

Draft updates require the saved version. Publication validates field defaults,
options, visibility and bounds, team references, and the feedback manager.
It switches the workspace pointer and writes the audit event and replay metadata
in one transaction. The existing database trigger protects published versions.
An active routing team must be replaced in a new configuration before it can
be archived. Existing cases keep their configuration ID and target snapshots.
The portal uses separate public fields and never receives hidden defaults.

## Follow-ups and feedback

Staff can read workspace tasks. Administrators, managers, and agents can create,
assign, complete, cancel, and reopen them. Due dates are stored as aware timestamps
and displayed in the workspace timezone. Only open or in-progress tasks can be
overdue. Completion records the staff member, time, and a required note.
Reopening clears the completion fields and leaves an audit entry. Incomplete
tasks block customer archive and transfer with other active responsibilities
when the owner loses access.

A portal requester can rate the latest cycle while the case is resolved.
The service establishes ownership under portal RLS before entering the case
storage context. The case version, feedback, audit entries, and optional
follow-up commit together. Ratings of 1 or 2 generate one task due 48 elapsed
hours after the rating. Assignment tries the eligible case assignee, then the
eligible customer owner, then the configured feedback manager. Unique constraints
on the cycle and task feedback reference protect against duplicates beyond the
replay window. The portal response contains the rating and comment. Staff review
receives the related task link.

## Staged CSV imports

An administrator or manager uploads one UTF-8 CSV through a bounded multipart
request. The parser caps the file at 1 MiB and 1,000 data rows. Validation applies
the customer schema, resolves owners within the workspace, and returns normalized
values, row errors, and counts. The preview stores the expected customer IDs and
versions. Validation writes the staging and audit records.

Commit requires a matching staging version and an idempotency key. It rechecks
the preview against current customers and memberships before applying rows in a
single savepoint. Any write conflict rolls back all customer mutations while the
outer transaction records a failed import. An existing external ID identifies a
customer update. Blank optional cells preserve saved values, and the declared
kind must agree with the existing customer. The import creates customer records
only.

Staging expires after 24 hours. Expired row content is withheld from reads and
purged on subsequent import writes or by the scoped operator command. Status
and counts are retained. The migration adds forced RLS, composite foreign keys,
and the constraints for these three tables. It leaves previous revisions intact.
