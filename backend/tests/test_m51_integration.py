"""New provider vetoes must preserve real PostgreSQL/requester-only fallbacks."""

from dataclasses import replace

import pytest
from test_m1_integration import clients as clients
from test_m1_integration import core as core
from test_m5_integration import article, ok, publish, question, run
from test_m5_integration import engines as engines
from test_m5_integration import models as models

from app.modules.knowledge.providers import ModelFailure

pytestmark = pytest.mark.integration
BASE = "/api/v1"


@pytest.mark.parametrize("reason", ["unsupported_claim", "unsafe_evidence", "invalid_citations"])
def test_rejected_generation_keeps_authorized_excerpts_without_draft_or_retry(
    clients, engines, models, caplog, reason
):
    manager, peer = clients("manager1"), clients("manager2")
    doc = article(manager, "Synthetic equipment policy", "Loan equipment requires inspection.")
    queued = publish(manager, doc)
    run(engines, models, expected=queued["job_id"])

    class RejectedDraft:
        def generate(self, question, sources):
            assert sources
            raise ModelFailure(reason)

    request = question(manager, "What is required for loan equipment?")
    job = run(engines, replace(models, generation=RejectedDraft()))
    path = BASE + "/assistant/requests/" + request["id"]
    result = ok(manager.get(path))
    assert result["mode"] == "sources_only"
    assert result["answer_text"] is None and result["error_code"] == reason
    assert any("inspection" in item["excerpt"] for item in result["sources"])
    assert peer.get(path).status_code == 404
    assert ok(manager.get(BASE + "/jobs/" + str(job.id)))["attempts"] == 1
    assert "Loan equipment" not in caplog.text
    document = ok(manager.get(BASE + "/knowledge/documents/" + doc["document_id"]))
    from test_m1_integration import mutate

    ok(
        mutate(
            manager,
            "/knowledge/documents/" + doc["document_id"] + "/archive",
            {"reason": "Synthetic fixture complete"},
            version=document["version"],
        )
    )
    after = ok(manager.get(path))
    assert after["error_code"] == "sources_changed" and after["answer_text"] is None
    assert all(item["version_id"] != doc["id"] for item in after["sources"])
