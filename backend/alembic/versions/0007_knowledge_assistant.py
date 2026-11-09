# ruff: noqa: E501
"""Workspace knowledge, assistant provenance, and leased background work."""

from alembic import op

revision = "0007_knowledge_assistant"
down_revision = "0006_activity_analytics"
branch_labels = None
depends_on = None

DDL = [
    """CREATE TABLE knowledge_documents (
    title VARCHAR(200) NOT NULL,
    active_version_id UUID,
    pending_version_id UUID,
    archived_at TIMESTAMP WITH TIME ZONE,
    created_by_member_id UUID NOT NULL,
    version INTEGER NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    id UUID NOT NULL,
    workspace_id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    UNIQUE (workspace_id, id),
    FOREIGN KEY(workspace_id, created_by_member_id) REFERENCES memberships (workspace_id, id),
    CHECK (version > 0 AND length(btrim(title)) BETWEEN 1 AND 200),
    CHECK (archived_at IS NULL OR (active_version_id IS NULL AND pending_version_id IS NULL)),
    FOREIGN KEY(workspace_id) REFERENCES workspaces (id)
)""",
    """CREATE INDEX ix_knowledge_documents_recent ON knowledge_documents (workspace_id, created_at, id)""",
    """CREATE TABLE knowledge_versions (
    document_id UUID NOT NULL,
    revision_number INTEGER NOT NULL,
    title VARCHAR(200) NOT NULL,
    source_kind VARCHAR(10) NOT NULL,
    source_name VARCHAR(200),
    content_text TEXT NOT NULL,
    content_sha256 VARCHAR(64) NOT NULL,
    status VARCHAR(12) NOT NULL,
    embedding_model_revision VARCHAR(100),
    error_code VARCHAR(50),
    published_by_member_id UUID,
    indexed_at TIMESTAMP WITH TIME ZONE,
    version INTEGER NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    id UUID NOT NULL,
    workspace_id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    UNIQUE (workspace_id, id),
    UNIQUE (workspace_id, document_id, id),
    UNIQUE (workspace_id, document_id, revision_number),
    FOREIGN KEY(workspace_id, document_id) REFERENCES knowledge_documents (workspace_id, id),
    FOREIGN KEY(workspace_id, published_by_member_id) REFERENCES memberships (workspace_id, id),
    CHECK (version > 0 AND revision_number > 0),
    CHECK (source_kind IN ('pasted','txt','markdown')),
    CHECK (status IN ('draft','queued','indexing','ready','failed')),
    CHECK (length(content_text) BETWEEN 1 AND 200000),
    CHECK (length(btrim(title)) BETWEEN 1 AND 200 AND content_sha256 ~ '^[0-9a-f]{64}$'),
    CHECK ((status = 'ready') = (indexed_at IS NOT NULL AND embedding_model_revision IS NOT NULL)),
    FOREIGN KEY(workspace_id) REFERENCES workspaces (id)
)""",
    """CREATE TABLE knowledge_chunks (
    version_id UUID NOT NULL,
    ordinal INTEGER NOT NULL,
    heading_path JSONB NOT NULL,
    start_offset INTEGER NOT NULL,
    end_offset INTEGER NOT NULL,
    content TEXT NOT NULL,
    token_count INTEGER NOT NULL,
    embedding VECTOR(384) NOT NULL,
    embedding_model_revision VARCHAR(100) NOT NULL,
    search_tsvector TSVECTOR GENERATED ALWAYS AS (to_tsvector('english'::regconfig, content)) STORED NOT NULL,
    id UUID NOT NULL,
    workspace_id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    UNIQUE (workspace_id, id),
    UNIQUE (workspace_id, version_id, id),
    UNIQUE (workspace_id, version_id, ordinal),
    FOREIGN KEY(workspace_id, version_id) REFERENCES knowledge_versions (workspace_id, id),
    CHECK (ordinal >= 0 AND start_offset >= 0 AND end_offset > start_offset),
    CHECK (char_length(content) = end_offset - start_offset AND token_count BETWEEN 1 AND 180),
    CHECK (jsonb_typeof(heading_path) = 'array'),
    FOREIGN KEY(workspace_id) REFERENCES workspaces (id)
)""",
    """CREATE INDEX ix_knowledge_chunk_search ON knowledge_chunks USING gin (search_tsvector)""",
    """CREATE TABLE assistant_requests (
    requested_by_member_id UUID NOT NULL,
    requested_by_session_id UUID NOT NULL,
    question TEXT,
    case_id UUID,
    state VARCHAR(12) NOT NULL,
    answer_text TEXT,
    mode VARCHAR(16),
    source_count INTEGER NOT NULL,
    abstention_reason VARCHAR(50),
    model_id VARCHAR(120),
    prompt_version VARCHAR(40) NOT NULL,
    retrieval_version VARCHAR(40) NOT NULL,
    error_code VARCHAR(50),
    completed_at TIMESTAMP WITH TIME ZONE,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    id UUID NOT NULL,
    workspace_id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    CHECK (source_count BETWEEN 0 AND 6),
    UNIQUE (workspace_id, id),
    UNIQUE (workspace_id, id, requested_by_member_id),
    FOREIGN KEY(workspace_id, requested_by_member_id) REFERENCES memberships (workspace_id, id),
    FOREIGN KEY(workspace_id, case_id) REFERENCES cases (workspace_id, id),
    CHECK (state IN ('queued','running','completed','failed')),
    CHECK (mode IS NULL OR mode IN ('generated','sources_only','abstained')),
    CHECK (question IS NULL OR length(question) BETWEEN 1 AND 2000),
    FOREIGN KEY(workspace_id) REFERENCES workspaces (id)
)""",
    """CREATE INDEX ix_assistant_member_requests ON assistant_requests (workspace_id, requested_by_member_id, state, created_at)""",
    """CREATE TABLE assistant_citations (
    request_id UUID NOT NULL,
    label VARCHAR(5) NOT NULL,
    document_id UUID NOT NULL,
    version_id UUID NOT NULL,
    chunk_id UUID NOT NULL,
    excerpt TEXT,
    start_offset INTEGER NOT NULL,
    end_offset INTEGER NOT NULL,
    rank INTEGER NOT NULL,
    id UUID NOT NULL,
    workspace_id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    UNIQUE (workspace_id, request_id, label),
    UNIQUE (workspace_id, request_id, rank),
    FOREIGN KEY(workspace_id, request_id) REFERENCES assistant_requests (workspace_id, id),
    FOREIGN KEY(workspace_id, document_id, version_id) REFERENCES knowledge_versions (workspace_id, document_id, id),
    FOREIGN KEY(workspace_id, version_id, chunk_id) REFERENCES knowledge_chunks (workspace_id, version_id, id),
    CHECK (rank BETWEEN 1 AND 6 AND label = 'S' || CAST(rank AS text)),
    CHECK (start_offset >= 0 AND end_offset > start_offset),
    FOREIGN KEY(workspace_id) REFERENCES workspaces (id)
)""",
    """CREATE TABLE assistant_feedback (
    request_id UUID NOT NULL,
    member_id UUID NOT NULL,
    helpful BOOLEAN NOT NULL,
    reason VARCHAR(1000),
    id UUID NOT NULL,
    workspace_id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    UNIQUE (workspace_id, request_id, member_id),
    FOREIGN KEY(workspace_id, request_id, member_id) REFERENCES assistant_requests (workspace_id, id, requested_by_member_id),
    CHECK (reason IS NULL OR length(reason) <= 1000),
    FOREIGN KEY(workspace_id) REFERENCES workspaces (id)
)""",
    """CREATE TABLE jobs (
    id UUID NOT NULL,
    workspace_id UUID NOT NULL,
    kind VARCHAR(32) NOT NULL,
    payload_json JSONB NOT NULL,
    result_refs_json JSONB,
    dedupe_key VARCHAR(100) NOT NULL,
    status VARCHAR(10) NOT NULL,
    available_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    attempts INTEGER NOT NULL,
    locked_by VARCHAR(100),
    attempt_token UUID,
    lease_until TIMESTAMP WITH TIME ZONE,
    heartbeat_at TIMESTAMP WITH TIME ZONE,
    last_error_code VARCHAR(50),
    finished_at TIMESTAMP WITH TIME ZONE,
    version INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    UNIQUE (workspace_id, id),
    UNIQUE (workspace_id, dedupe_key),
    CHECK (kind IN ('knowledge_index','assistant_request')),
    CHECK (status IN ('queued','running','succeeded','failed')),
    CHECK (attempts BETWEEN 0 AND 4 AND version > 0),
    CHECK ((status = 'running') = (attempt_token IS NOT NULL AND lease_until IS NOT NULL AND locked_by IS NOT NULL)),
    FOREIGN KEY(workspace_id) REFERENCES workspaces (id)
)""",
    """CREATE INDEX ix_jobs_claim ON jobs (status, available_at, lease_until)""",
    """CREATE INDEX ix_jobs_workspace_recent ON jobs (workspace_id, created_at, id)""",
]

TABLES = (
    "knowledge_documents",
    "knowledge_versions",
    "knowledge_chunks",
    "assistant_requests",
    "assistant_citations",
    "assistant_feedback",
    "jobs",
)


def upgrade() -> None:
    for statement in DDL:
        op.execute(statement)
    for name, field in (
        ("fk_knowledge_active", "active_version_id"),
        ("fk_knowledge_pending", "pending_version_id"),
    ):
        op.create_foreign_key(
            name,
            "knowledge_documents",
            "knowledge_versions",
            ["workspace_id", "id", field],
            ["workspace_id", "document_id", "id"],
        )
    op.execute("""
        CREATE FUNCTION atlas_immutable_knowledge_revision() RETURNS trigger LANGUAGE plpgsql
        AS $$
        BEGIN
            IF OLD.status <> 'draft' AND (
                ROW(NEW.workspace_id, NEW.document_id, NEW.revision_number, NEW.title,
                    NEW.source_kind, NEW.source_name, NEW.content_text, NEW.content_sha256,
                    NEW.published_by_member_id)
                IS DISTINCT FROM ROW(OLD.workspace_id, OLD.document_id, OLD.revision_number, OLD.title,
                    OLD.source_kind, OLD.source_name, OLD.content_text, OLD.content_sha256,
                    OLD.published_by_member_id)
                OR (OLD.status = 'ready' AND NEW IS DISTINCT FROM OLD)
            ) THEN
                RAISE EXCEPTION 'published knowledge revisions are immutable' USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER atlas_immutable_knowledge_revision BEFORE UPDATE ON knowledge_versions
        FOR EACH ROW EXECUTE FUNCTION atlas_immutable_knowledge_revision()
    """)

    scope = "workspace_id = NULLIF(current_setting('app.workspace_id', true), '')::uuid"
    staff = "current_setting('app.audience', true) = 'staff'"
    worker = "current_setting('app.audience', true) = 'worker'"
    operator = "current_user = 'atlas_migrator'"
    user = "NULLIF(current_setting('app.user_id', true), '')::uuid"
    active = f"EXISTS (SELECT 1 FROM memberships m WHERE m.user_id = {user} AND m.active"
    readers = f"({staff} AND {active}))"
    managers = f"({staff} AND {active} AND m.role IN ('admin','manager')))"
    questioners = f"({staff} AND {active} AND m.role IN ('admin','manager','agent')))"
    own_member = f"m.user_id = {user} AND m.active AND m.role IN ('admin','manager','agent')"
    owner = f"({questioners} AND EXISTS (SELECT 1 FROM memberships m WHERE m.id = requested_by_member_id AND {own_member}))"

    def approved(version_column: str) -> str:
        return f"""EXISTS (SELECT 1 FROM knowledge_documents d
            WHERE d.active_version_id = {version_column} AND d.archived_at IS NULL)"""

    def owns_request(table: str) -> str:
        return f"""({questioners} AND EXISTS (SELECT 1 FROM assistant_requests a
            WHERE a.id = {table}.request_id))"""

    writers = f"({worker} OR {managers})"
    documents = (
        f"{writers} OR ({readers} AND archived_at IS NULL AND active_version_id IS NOT NULL)"
    )
    revisions = (
        f"{writers} OR ({readers} AND status = 'ready' AND {approved('knowledge_versions.id')})"
    )

    def ready(version_column: str) -> str:
        return f"""({approved(version_column)} AND EXISTS (
            SELECT 1 FROM knowledge_versions v WHERE v.id = {version_column} AND v.status = 'ready'
        ))"""

    chunks = f"{worker} OR ({readers} AND {ready('knowledge_chunks.version_id')})"
    citations = f"{worker} OR ({owns_request('assistant_citations')} AND {ready('assistant_citations.version_id')})"
    feedback = f"{worker} OR {owns_request('assistant_feedback')}"
    job_read = f"{worker} OR {managers} OR ({questioners} AND kind = 'assistant_request' AND EXISTS (SELECT 1 FROM assistant_requests a WHERE CAST(a.id AS text) = payload_json->>'id'))"
    policies = {
        "knowledge_documents": (documents, managers, writers, None),
        "knowledge_versions": (revisions, managers, writers, None),
        "knowledge_chunks": (chunks, worker, None, worker),
        "assistant_requests": (f"{worker} OR {owner}", owner, worker, None),
        "assistant_citations": (citations, worker, worker, None),
        "assistant_feedback": (feedback, owns_request("assistant_feedback"), feedback, None),
        "jobs": (
            job_read,
            f"{managers} OR ({questioners} AND kind = 'assistant_request')",
            writers,
            None,
        ),
    }
    for table, (read, insert, update, delete) in policies.items():
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY m5_read ON {table} FOR SELECT USING ({scope} AND ({operator} OR {read}))"
        )
        op.execute(
            f"CREATE POLICY m5_insert ON {table} FOR INSERT WITH CHECK ({scope} AND ({operator} OR {insert}))"
        )
        grants = ["SELECT", "INSERT"]
        if update:
            predicate = f"{scope} AND ({operator} OR {update})"
            op.execute(
                f"CREATE POLICY m5_update ON {table} FOR UPDATE USING ({predicate}) WITH CHECK ({predicate})"
            )
            grants.append("UPDATE")
        if delete:
            op.execute(
                f"CREATE POLICY m5_delete ON {table} FOR DELETE USING ({scope} AND ({delete}))"
            )
            grants.append("DELETE")
        op.execute(
            f"CREATE POLICY m5_cleanup ON {table} FOR DELETE TO atlas_migrator USING ({scope})"
        )
        op.execute(f"GRANT {', '.join(grants)} ON {table} TO atlas_app")

    # The dispatcher sees jobs and identifier-only payloads. It has no domain-table grants.
    op.execute("CREATE POLICY dispatch_read ON jobs FOR SELECT TO atlas_queue USING (true)")
    op.execute(
        "CREATE POLICY dispatch_lease ON jobs FOR UPDATE TO atlas_queue USING (true) WITH CHECK (true)"
    )
    op.execute("GRANT SELECT ON jobs TO atlas_queue")
    op.execute("""
        GRANT UPDATE (status, attempts, locked_by, attempt_token, lease_until, heartbeat_at,
            version, updated_at) ON jobs TO atlas_queue
    """)
    # Reuse the rate-limit table with a separate namespace for authenticated staff questions.
    principal = f"(principal_key = 'workspace' OR EXISTS (SELECT 1 FROM memberships m WHERE m.user_id = {user} AND CAST(m.id AS text) = principal_key AND m.active))"
    budget = f"{scope} AND {questioners} AND {principal} AND operation IN ('assistant.minute','assistant.day')"
    op.execute(f"CREATE POLICY m5_budget_read ON rate_limit_buckets FOR SELECT USING ({budget})")
    op.execute(
        f"CREATE POLICY m5_budget_insert ON rate_limit_buckets FOR INSERT WITH CHECK ({budget})"
    )
    op.execute(
        f"CREATE POLICY m5_budget_update ON rate_limit_buckets FOR UPDATE USING ({budget}) WITH CHECK ({budget})"
    )
    op.execute(
        f"CREATE POLICY m5_budget_cleanup ON rate_limit_buckets FOR DELETE USING ({scope} AND {worker} AND operation IN ('assistant.minute','assistant.day'))"
    )
    op.execute(
        f"CREATE POLICY m5_budget_worker_read ON rate_limit_buckets FOR SELECT USING ({scope} AND {worker} AND operation IN ('assistant.minute','assistant.day'))"
    )
    op.execute(f"""CREATE POLICY m5_worker_audit ON audit_events FOR INSERT WITH CHECK (
        {scope} AND {worker} AND actor_kind = 'system' AND actor_user_id IS NULL
        AND action IN ('knowledge.indexed','knowledge.index_failed')
    )""")
    op.execute(f"""CREATE POLICY m5_worker_audit_read ON audit_events FOR SELECT USING (
        {scope} AND {worker} AND actor_kind = 'system'
        AND action IN ('knowledge.indexed','knowledge.index_failed')
    )""")


def downgrade() -> None:
    op.execute("DROP POLICY m5_worker_audit_read ON audit_events")
    op.execute("DROP POLICY m5_worker_audit ON audit_events")
    for policy in (
        "m5_budget_worker_read",
        "m5_budget_cleanup",
        "m5_budget_update",
        "m5_budget_insert",
        "m5_budget_read",
    ):
        op.execute(f"DROP POLICY {policy} ON rate_limit_buckets")
    op.drop_constraint("fk_knowledge_pending", "knowledge_documents", type_="foreignkey")
    op.drop_constraint("fk_knowledge_active", "knowledge_documents", type_="foreignkey")
    for table in reversed(TABLES):
        op.drop_table(table)
    op.execute("DROP FUNCTION atlas_immutable_knowledge_revision()")
