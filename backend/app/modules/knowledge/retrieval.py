"""Exact PostgreSQL retrieval from each document's active, ready revision."""

import json
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from sqlalchemy import RowMapping, text
from sqlalchemy.orm import Session

from app.modules.knowledge.schemas import AssistantSource, Source
from app.platform.protocol import Fault

RETRIEVAL_VERSION = "rrf-english-1"
EVIDENCE_TOKENS = 1400
SIMILARITY_THRESHOLD = 0.45
Strategy = Literal["lexical", "vector", "hybrid"]

ACTIVE = """
    SELECT c.id AS chunk_id, c.version_id, v.document_id, v.title, v.revision_number, c.ordinal,
        c.heading_path, c.start_offset, c.end_offset, c.content AS excerpt,
        c.embedding, c.embedding_model_revision, c.search_tsvector
    FROM knowledge_chunks c
    JOIN knowledge_versions v ON (v.workspace_id, v.id) = (c.workspace_id, c.version_id)
    JOIN knowledge_documents d ON (d.workspace_id, d.id, d.active_version_id)
        = (v.workspace_id, v.document_id, v.id)
    WHERE c.workspace_id = :workspace AND d.archived_at IS NULL AND v.status = 'ready'
"""

# Convert natural-language questions to a disjunction of normalized English
# lexemes. PostgreSQL owns stopword removal, normalization, ranking and escaping.
LEXEMES = """
    SELECT CAST(string_agg(quote_literal(word), ' | ') AS tsquery) AS words
    FROM unnest(tsvector_to_array(to_tsvector('english', :question))) AS word
"""
LEXICAL = text(f"""
    WITH active AS NOT MATERIALIZED ({ACTIVE}), query AS ({LEXEMES})
    SELECT a.* FROM active a CROSS JOIN query q WHERE a.search_tsvector @@ q.words
    ORDER BY ts_rank_cd(a.search_tsvector, q.words) DESC, a.document_id, a.ordinal LIMIT :limit
""")
VECTOR = text(f"""
    WITH active AS NOT MATERIALIZED ({ACTIVE}), query AS ({LEXEMES})
    SELECT a.*, 1 - (a.embedding <=> CAST(:vector AS vector(384))) AS similarity,
        coalesce(a.search_tsvector @@ q.words, false) AS lexical_match
    FROM active a CROSS JOIN query q WHERE a.embedding_model_revision = :revision
    ORDER BY a.embedding <=> CAST(:vector AS vector(384)), a.document_id, a.ordinal LIMIT 20
""")


def source(row: RowMapping) -> Source:
    data = {key: row[key] for key in Source.model_fields if key != "source_url"}
    return Source.model_validate({**data, "source_url": f"/app/knowledge/sources/{row.chunk_id}"})


def lexical(session: Session, workspace_id: UUID, query: str, limit: int = 20) -> list[Source]:
    return [
        source(row)
        for row in session.execute(
            LEXICAL,
            {
                "workspace": workspace_id,
                "question": query,
                "limit": limit,
            },
        ).mappings()
    ]


def sources_by_id(
    session: Session, workspace_id: UUID, identifiers: list[UUID]
) -> dict[UUID, Source]:
    if not identifiers:
        return {}
    rows = session.execute(
        text(ACTIVE + " AND c.id = ANY(CAST(:ids AS uuid[]))"),
        {
            "workspace": workspace_id,
            "ids": identifiers,
        },
    ).mappings()
    return {row.chunk_id: source(row) for row in rows}


def inspect(session: Session, workspace_id: UUID, identifier: UUID) -> Source:
    result = sources_by_id(session, workspace_id, [identifier]).get(identifier)
    if result is None:
        raise Fault(404, "source_unavailable", "This source is no longer available.")
    return result


@dataclass(frozen=True)
class VectorCandidate:
    source: Source
    similarity: float
    lexical_match: bool


def vector(
    session: Session,
    workspace_id: UUID,
    question: str,
    embedding: list[float],
    model_revision: str,
) -> list[VectorCandidate]:
    rows = session.execute(
        VECTOR,
        {
            "workspace": workspace_id,
            "question": question,
            "vector": str(embedding),
            "revision": model_revision,
        },
    ).mappings()
    return [VectorCandidate(source(row), row.similarity, row.lexical_match) for row in rows]


def rank(
    lexical_hits: list[Source],
    vector_hits: list[VectorCandidate],
    strategy: Strategy,
    *,
    threshold: float = SIMILARITY_THRESHOLD,
) -> list[Source]:
    scores: dict[UUID, float] = {}
    candidates: dict[UUID, Source] = {}
    admitted: set[UUID] = set()
    lists: list[list[tuple[Source, bool]]] = []
    if strategy != "vector":
        lists.append([(item, True) for item in lexical_hits])
    if strategy != "lexical":
        lists.append(
            [
                (
                    hit.source,
                    hit.similarity >= threshold or (strategy == "hybrid" and hit.lexical_match),
                )
                for hit in vector_hits
            ]
        )
    for matches in lists:
        for position, (item, eligible) in enumerate(matches, 1):
            candidates[item.chunk_id] = item
            scores[item.chunk_id] = scores.get(item.chunk_id, 0) + 1 / (60 + position)
            if eligible:
                admitted.add(item.chunk_id)
    return sorted(
        (candidates[identifier] for identifier in admitted),
        key=lambda item: (-scores[item.chunk_id], item.document_id, item.ordinal),
    )


def prompt_json(value: object) -> str:
    # Never let untrusted excerpt or question text become ChatML delimiters.
    return (
        json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
    )


def evidence_json(items: list[AssistantSource]) -> str:
    return prompt_json(
        [{"label": item.label, "title": item.title, "excerpt": item.excerpt} for item in items]
    )


def trim_overlap(item: Source, selected: list[AssistantSource]) -> Source | None:
    spans = [(item.start_offset, item.end_offset)]
    for prior in selected:
        if prior.version_id != item.version_id:
            continue
        remaining = []
        for left, right in spans:
            if right <= prior.start_offset or left >= prior.end_offset:
                remaining.append((left, right))
            else:
                if left < prior.start_offset:
                    remaining.append((left, prior.start_offset))
                if right > prior.end_offset:
                    remaining.append((prior.end_offset, right))
        spans = remaining
    if not spans:
        return None
    start, end = max(spans, key=lambda span: span[1] - span[0])
    excerpt = item.excerpt[start - item.start_offset : end - item.start_offset]
    if not excerpt.strip():
        return None
    return item.model_copy(update={"start_offset": start, "end_offset": end, "excerpt": excerpt})


def evidence(ranked: list[Source], count: Callable[[str], int]) -> list[AssistantSource]:
    selected: list[AssistantSource] = []
    used: Counter[UUID] = Counter()
    texts: set[str] = set()
    for item in ranked:
        if used[item.document_id] == 3:
            continue
        trimmed = trim_overlap(item, selected)
        if not trimmed:
            continue
        canonical = " ".join(trimmed.excerpt.casefold().split())
        if canonical in texts:
            continue
        number = len(selected) + 1
        candidate = AssistantSource(**trimmed.model_dump(), label=f"S{number}", rank=number)
        if count(evidence_json([*selected, candidate])) > EVIDENCE_TOKENS:
            continue
        selected.append(candidate)
        used[item.document_id] += 1
        texts.add(canonical)
        if len(selected) == 6:
            break
    return selected


def valid_excerpt(candidate: AssistantSource, current: Source) -> bool:
    start = candidate.start_offset - current.start_offset
    end = candidate.end_offset - current.start_offset
    return (
        candidate.document_id == current.document_id
        and candidate.version_id == current.version_id
        and 0 <= start < end <= len(current.excerpt)
        and candidate.excerpt == current.excerpt[start:end]
    )
