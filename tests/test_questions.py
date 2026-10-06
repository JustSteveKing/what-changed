from pathlib import Path

from what_changed.contract import EvalQuestionSet

RAW = Path("eval/questions.json").read_text()


def test_matches_the_schema() -> None:
    EvalQuestionSet.validate_json(RAW)


def test_has_the_agreed_mix_of_5_direct_11_research_and_4_declined_or_incomplete() -> None:
    questions = EvalQuestionSet.validate_json(RAW)
    answered = [q for q in questions if q.expected_outcome == "answered"]
    assert len([q for q in answered if q.expected_route == "direct"]) == 5
    assert len([q for q in answered if q.expected_route == "research"]) == 11
    assert len([q for q in questions if q.expected_outcome != "answered"]) == 4
