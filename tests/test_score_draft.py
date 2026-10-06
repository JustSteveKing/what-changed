from pathlib import Path

from eval.score_draft import DRAFT_FILE, DraftFile, DraftRow, expected_keys, load_answer, validate_draft

BASE = {"provenance": "test", "rater": "test", "drafted_on": "2026-10-06"}
ANSWERS = {"r1": "The latest stable version is v4.4.7."}


def load(run_id: str, question_id: str) -> str:
    return ANSWERS[run_id]


def row(rating: str, quote: str) -> DraftRow:
    return DraftRow.model_validate({"run_id": "r1", "question_id": "q01", "element_id": "version", "rating": rating, "quote": quote, "reason": "x"})


def test_rejects_a_quote_that_is_not_in_the_stored_answer() -> None:
    draft = DraftFile.model_validate({**BASE, "rows": [row("fully", "v4.4.8")]})
    assert validate_draft(draft, load, ["r1/q01/version"]) == ["r1/q01/version: quote is not in the stored answer"]


def test_empty_quote_only_for_missing_and_uncovered_elements_reported() -> None:
    draft = DraftFile.model_validate({**BASE, "rows": [row("partly", "")]})
    assert validate_draft(draft, load, ["r1/q01/version", "r1/q01/source"]) == [
        'r1/q01/version: only "missing" may have no quote',
        "no row for r1/q01/source",
    ]


def test_the_committed_draft_is_complete_and_every_quote_is_verbatim() -> None:
    draft = DraftFile.model_validate_json(Path(DRAFT_FILE).read_text())
    run_ids = sorted({r.run_id for r in draft.rows})
    assert len(run_ids) == 3
    assert validate_draft(draft, load_answer, expected_keys(run_ids)) == []
