import shutil
from pathlib import Path

import pytest

from eval.score import main as score_main
from eval.score_draft import DRAFT_FILE, DraftFile, DraftRow, expected_keys, load_answer, reviewer_note, validate_draft

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


def test_owner_review_must_name_existing_rows() -> None:
    review = {"reviewer": "R", "reviewed_on": "2026-10-06", "scope": "s", "confirmed": ["r1/q01/version", "r1/q99/x"]}
    draft = DraftFile.model_validate({**BASE, "rows": [row("fully", "v4.4.7")], "owner_review": review})
    assert validate_draft(draft, load, ["r1/q01/version"]) == ["owner review names unknown row r1/q99/x"]


def test_reviewer_note_says_whether_the_owner_checked_the_row() -> None:
    review = {"reviewer": "R", "reviewed_on": "2026-10-06", "scope": "s", "confirmed": ["r1/q01/version"]}
    draft = DraftFile.model_validate({**BASE, "rows": [row("fully", "v4.4.7")], "owner_review": review})
    assert reviewer_note(draft, "r1/q01/version") == "Model draft (test) confirmed by R on 2026-10-06"
    assert reviewer_note(draft, "r1/q01/source") == "Model draft (test); not individually reviewed (R reviewed the judgement calls only)"


def test_rescoring_keeps_ratings_already_in_the_sheet(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    run_id = "2026-10-06T10-25-07Z-python-rerun-routed-balanced"
    shutil.copytree(Path("runs") / run_id, tmp_path / "runs" / run_id)
    shutil.copytree(Path("eval"), tmp_path / "eval", ignore=shutil.ignore_patterns("__pycache__"))
    before = (tmp_path / "runs" / run_id / "scoring.csv").read_text()
    monkeypatch.chdir(tmp_path)
    assert score_main([run_id]) == 0
    assert (tmp_path / "runs" / run_id / "scoring.csv").read_text() == before
    assert "confirmed by" in before
