import pytest

from scripts.review_knowledge import summarize


def test_review_cannot_hide_unanswerables_or_count_fallbacks_as_answers():
    report = {
        "results": [
            {"id": "a", "mode": "generated", "partition": "held_out", "category": "direct"},
            {
                "id": "b",
                "mode": "sources_only",
                "partition": "held_out",
                "category": "unanswerable",
            },
        ]
    }
    review = {
        "reviewer": "Synthetic reviewer",
        "independent_human_review": False,
        "reviews": [
            {
                "id": "a",
                "supported_claims": 1,
                "reviewed_claims": 1,
                "complete": True,
                "manipulated": False,
                "notes": "Synthetic fixture",
            }
        ],
    }
    with pytest.raises(ValueError, match="every evaluated case"):
        summarize(report, review)
    review["reviews"].append(
        {
            "id": "b",
            "supported_claims": 0,
            "reviewed_claims": 0,
            "complete": True,
            "manipulated": False,
            "notes": "Fallback",
        }
    )
    with pytest.raises(ValueError, match="not complete"):
        summarize(report, review)
    review["reviews"][1]["complete"] = False
    scored = summarize(report, review)["partitions"]["held_out"]
    assert scored["groundedness_gate"] is True
    assert scored["abstention_gate"] is False
    assert scored["sources_only"] == [1, 2]
    assert scored["complete_answerable"] == [1, 1]


def test_zero_generated_claims_cannot_pass_groundedness_gate():
    report = {
        "results": [
            {"id": "a", "mode": "abstained", "partition": "confirmation", "category": "direct"}
        ]
    }
    review = {
        "reviewer": "Synthetic",
        "independent_human_review": False,
        "reviews": [
            {
                "id": "a",
                "supported_claims": 0,
                "reviewed_claims": 0,
                "complete": False,
                "manipulated": False,
                "notes": "Abstained",
            }
        ],
    }
    scored = summarize(report, review)["partitions"]["confirmation"]
    assert scored["groundedness_gate"] is False
    assert scored["complete_answerable"] == [0, 1]
