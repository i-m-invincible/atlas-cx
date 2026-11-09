"""Evaluate the versioned synthetic corpus in a disposable PostgreSQL database."""

import argparse
import json
import os
import platform
import secrets
from collections import Counter
from pathlib import Path
from time import perf_counter
from uuid import UUID, uuid4

from pydantic import BaseModel
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.modules.identity.operator import bootstrap_workspace
from app.modules.knowledge import retrieval
from app.modules.knowledge.content import checksum, normalize
from app.modules.knowledge.model_manifest import EMBEDDING_REVISION, PROMPT_VERSION, QWEN_TOKENIZER
from app.modules.knowledge.models import Document, Revision
from app.modules.knowledge.providers import FastTokenizer, MiniLM, ModelFailure, Ollama
from app.modules.knowledge.worker import Runtime, process
from app.platform.database import build_engine, workspace_session
from app.platform.dispatch import claim
from app.platform.jobs import Job

CORPUS_PATH = Path(__file__).resolve().parents[1] / "evaluation" / "knowledge-corpus-v1.json"


class Version(BaseModel):
    number: int
    text: str
    active: bool


class Article(BaseModel):
    key: str
    title: str
    revisions: list[Version]


class Question(BaseModel):
    id: str
    category: str
    partition: str
    question: str
    expected: str
    support: list[str]


class Isolation(BaseModel):
    title: str
    text: str
    query: str
    foreign_marker: str


class Corpus(BaseModel):
    version: str
    documents: list[Article]
    questions: list[Question]
    isolation: Isolation


def seed(
    app: Engine,
    migration: Engine,
    queue: Engine,
    runtime: Runtime,
    articles: list[Article],
) -> tuple[UUID, UUID, dict[UUID, str]]:
    suffix = uuid4().hex[:12]
    with Session(migration) as db, db.begin():
        workspace, member = bootstrap_workspace(
            db,
            "eval-" + suffix,
            "Synthetic evaluation",
            f"eval-{suffix}@example.com",
            "Synthetic evaluation operator",
            secrets.token_urlsafe(32),
        )
        workspace_id, member_id, user_id = workspace.id, member.id, member.user_id
    revisions: dict[UUID, str] = {}
    for ordinal, article in enumerate(articles, 1):
        # Stable document order for RRF ties. The high bits remain workspace-specific.
        document_id = UUID(int=(workspace_id.int & ~65535) | ordinal)
        for version in article.revisions:
            content = normalize(version.text)
            identifier = uuid4()
            with workspace_session(app, workspace_id, user_id=user_id) as db:
                document = db.get(Document, document_id)
                if document is None:
                    document = Document(
                        id=document_id,
                        workspace_id=workspace_id,
                        title=article.title,
                        created_by_member_id=member_id,
                    )
                    db.add(document)
                    db.flush()
                row = Revision(
                    id=identifier,
                    workspace_id=workspace_id,
                    document_id=document_id,
                    revision_number=version.number,
                    title=article.title,
                    source_kind="markdown",
                    content_text=content,
                    content_sha256=checksum(content),
                    status="queued",
                    published_by_member_id=member_id,
                )
                db.add(row)
                db.flush()
                document.pending_version_id = identifier
                db.add(
                    Job(
                        workspace_id=workspace_id,
                        kind="knowledge_index",
                        payload_json={"id": str(identifier)},
                        dedupe_key="knowledge:" + str(identifier),
                    )
                )
            attempt = claim(queue, "synthetic-evaluation")
            if not attempt or attempt.target_id != identifier:
                raise RuntimeError("Evaluation requires an idle disposable queue")
            process(app, queue, attempt, runtime)
            with workspace_session(app, workspace_id, user_id=user_id) as db:
                row = db.get(Revision, identifier)
                if not row or row.status != "ready":
                    raise RuntimeError(
                        "Synthetic revision did not index: " + str(row.error_code if row else None)
                    )
            revisions[identifier] = f"{article.key}:r{version.number}"
    return workspace_id, user_id, revisions


def latency(samples: list[float]) -> dict[str, float | int | None]:
    ordered = sorted(samples)
    return {
        "n": len(ordered),
        "p50_ms": round(ordered[(len(ordered) - 1) // 2], 2) if ordered else None,
        "p95_ms": round(ordered[max(0, (95 * len(ordered) + 99) // 100 - 1)], 2)
        if ordered
        else None,
    }


def proportion(numerator: int, denominator: int) -> dict[str, int]:
    return {"numerator": numerator, "denominator": denominator}


def evaluate(args: argparse.Namespace) -> dict[str, object]:
    corpus = Corpus.model_validate_json(CORPUS_PATH.read_text(encoding="utf-8"))
    assert Counter(row.category for row in corpus.questions) == {
        "direct": 30,
        "multi": 10,
        "unanswerable": 10,
        "conflict": 5,
        "injection": 5,
    }
    assert sum(row.partition == "held_out" for row in corpus.questions) == 20
    app = build_engine(os.environ["TEST_DATABASE_URL"])
    migration = build_engine(os.environ["MIGRATION_DATABASE_URL"])
    queue = build_engine(os.environ["QUEUE_DATABASE_URL"])
    directory = Path(args.models)
    embedder = MiniLM(directory)
    tokenizer = FastTokenizer(directory, QWEN_TOKENIZER)
    generator = Ollama(args.ollama_url, tokenizer) if args.generate else None
    if generator:
        generator.verify()
    runtime = Runtime(embedder, tokenizer.count, None)
    try:
        workspace, user, refs = seed(app, migration, queue, runtime, corpus.documents)
        other = corpus.isolation
        foreign, foreign_user, _ = seed(
            app,
            migration,
            queue,
            runtime,
            [
                Article(
                    key="foreign",
                    title=other.title,
                    revisions=[Version(number=1, text=other.text, active=True)],
                ),
            ],
        )
        active = {
            f"{article.key}:r{row.number}"
            for article in corpus.documents
            for row in article.revisions
            if row.active
        }
        hit: Counter[tuple[str, str]] = Counter()
        eligible: Counter[str] = Counter()
        complete: Counter[tuple[str, str]] = Counter()
        retrieval_times: list[float] = []
        generation_times: list[float] = []
        total_times: list[float] = []
        results: list[dict[str, object]] = []
        abstained_unanswerable = 0
        citations_valid = citations_count = fallbacks = 0
        for question in corpus.questions:
            start = perf_counter()
            query = question.question
            vector = embedder.embed([query])[0]
            with workspace_session(app, workspace, user_id=user) as db:
                lexical = retrieval.lexical(db, workspace, query)
                vectors = retrieval.vector(db, workspace, query, vector, EMBEDDING_REVISION)
                sets = {
                    method: retrieval.evidence(
                        retrieval.rank(lexical, vectors, method), tokenizer.count
                    )
                    for method in ("lexical", "vector", "hybrid")
                }
                selected = sets["hybrid"]
                current = retrieval.sources_by_id(db, workspace, [row.chunk_id for row in selected])
            retrieval_times.append((perf_counter() - start) * 1000)
            found = {
                method: [f"{refs[item.version_id]}:c{item.ordinal}" for item in sources]
                for method, sources in sets.items()
            }
            assert all(
                ref.split(":c")[0] in active for matches in found.values() for ref in matches
            )
            if question.category in {"direct", "multi"}:
                eligible[question.partition] += 1
                for method, matches in found.items():
                    hit[method, question.partition] += bool(set(question.support) & set(matches))
                    complete[method, question.partition] += set(question.support) <= set(matches)
            citations_count += len(selected)
            citations_valid += sum(
                retrieval.valid_excerpt(item, current[item.chunk_id]) for item in selected
            )
            mode = "sources_only" if selected else "abstained"
            answer = error = None
            if selected and generator:
                before = perf_counter()
                try:
                    output = generator.generate(query, selected)
                    answer, error = output.answer, output.reason
                    mode = "generated" if answer else "abstained"
                except ModelFailure as exc:
                    error = exc.code
                generation_times.append((perf_counter() - before) * 1000)
            fallbacks += mode == "sources_only"
            abstained_unanswerable += mode == "abstained" and question.category == "unanswerable"
            total_times.append((perf_counter() - start) * 1000)
            result = {
                "id": question.id,
                "partition": question.partition,
                "matches": found,
                "mode": mode,
                "error": error,
                "answer": answer,
            }
            results.append(result)
            if args.log_claims and answer:
                print(
                    "Synthetic claim record "
                    + json.dumps(
                        {
                            "id": question.id,
                            "answer": answer,
                            "sources": found["hybrid"],
                        },
                        ensure_ascii=True,
                    ),
                    flush=True,
                )
        with workspace_session(app, foreign, user_id=foreign_user) as db:
            foreign_source = retrieval.lexical(db, foreign, other.query)[0]
            assert other.foreign_marker in foreign_source.excerpt
        with workspace_session(app, workspace, user_id=user) as db:
            lexical = retrieval.lexical(db, workspace, other.query)
            vector = retrieval.vector(
                db, workspace, other.query, embedder.embed([other.query])[0], EMBEDDING_REVISION
            )
            by_id = retrieval.sources_by_id(db, workspace, [foreign_source.chunk_id])
        leaks = sum(other.foreign_marker in item.excerpt for item in lexical)
        leaks += sum(other.foreign_marker in item.source.excerpt for item in vector)
        leaks += len(by_id)
        leaks += sum(other.foreign_marker in str(row["answer"]) for row in results)
        return {
            "corpus": corpus.version,
            "embedding_revision": EMBEDDING_REVISION,
            "retrieval_version": retrieval.RETRIEVAL_VERSION,
            "prompt_version": PROMPT_VERSION,
            "machine": platform.platform(),
            "cpu_threads": os.cpu_count(),
            "generation_requested": args.generate,
            "hit_at_6": {
                method: {
                    partition: proportion(hit[method, partition], eligible[partition])
                    for partition in ("development", "held_out")
                }
                for method in ("lexical", "vector", "hybrid")
            },
            "all_support_at_6": {
                method: {
                    partition: proportion(complete[method, partition], eligible[partition])
                    for partition in ("development", "held_out")
                }
                for method in ("lexical", "vector", "hybrid")
            },
            "citation_validity": proportion(citations_valid, citations_count),
            "unanswerable_abstention": proportion(abstained_unanswerable, 10),
            "fallback": proportion(fallbacks, len(results)),
            "isolation_disclosures": leaks,
            "latency": {
                "retrieval_with_query_embedding": latency(retrieval_times),
                "generation": latency(generation_times),
                "end_to_end_direct": latency(total_times),
            },
            "groundedness": "manual review required" if args.generate else "generation disabled",
            "results": results,
        }
    finally:
        app.dispose()
        migration.dispose()
        queue.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--generate", action="store_true")
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    parser.add_argument(
        "--log-claims",
        action="store_true",
        help="Print generated claims from this synthetic corpus for manual review",
    )
    args = parser.parse_args()
    result = evaluate(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        "Synthetic evaluation "
        + json.dumps({key: value for key, value in result.items() if key != "results"})
    )


if __name__ == "__main__":
    main()
