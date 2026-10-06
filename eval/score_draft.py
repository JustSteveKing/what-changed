import csv
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Literal

from what_changed.contract import EvalQuestionSet, Model, NonEmpty, RunRecord

# Validates the model-drafted ratings and writes one scoring-draft-model.csv per run.
# The human sheet (scoring.csv) is never touched. Usage: uv run python -m eval.score_draft

DRAFT_FILE = Path("eval/scoring-draft-model.json")


class DraftRow(Model):
    run_id: str
    question_id: str
    element_id: str
    rating: Literal["fully", "partly", "missing"]
    # Exact text from the stored answer the rating rests on. Empty only for "missing".
    quote: str
    reason: NonEmpty


class DraftFile(Model):
    provenance: NonEmpty
    rater: NonEmpty
    drafted_on: str
    rows: list[DraftRow]


def validate_draft(draft: DraftFile, load_answer: Callable[[str, str], str], expected: list[str]) -> list[str]:
    problems: list[str] = []
    seen: set[str] = set()
    for row in draft.rows:
        key = f"{row.run_id}/{row.question_id}/{row.element_id}"
        if key in seen:
            problems.append(f"duplicate row {key}")
        seen.add(key)
        if row.quote == "" and row.rating != "missing":
            problems.append(f'{key}: only "missing" may have no quote')
        if row.quote != "" and row.quote not in load_answer(row.run_id, row.question_id):
            problems.append(f"{key}: quote is not in the stored answer")
    problems.extend(f"no row for {key}" for key in expected if key not in seen)
    return problems


def load_answer(run_id: str, question_id: str) -> str:
    return RunRecord.model_validate_json((Path("runs") / run_id / f"{question_id}.json").read_text()).text


def expected_keys(run_ids: list[str]) -> list[str]:
    questions = EvalQuestionSet.validate_json(Path("eval/questions.json").read_text())
    return [f"{run_id}/{q.id}/{e.id}" for run_id in run_ids for q in questions for e in q.required_elements]


def main() -> int:
    draft = DraftFile.model_validate_json(DRAFT_FILE.read_text())
    questions = EvalQuestionSet.validate_json(Path("eval/questions.json").read_text())
    run_ids = sorted({r.run_id for r in draft.rows})

    problems = validate_draft(draft, load_answer, expected_keys(run_ids))
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 1

    for run_id in run_ids:
        rows = {(r.question_id, r.element_id): r for r in draft.rows if r.run_id == run_id}
        with (Path("runs") / run_id / "scoring-draft-model.csv").open("w", newline="") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow(["run_id", "question_id", "element_id", "check", "draft_rating", "quote_from_answer", "reason", "rater"])
            for q in questions:
                for e in q.required_elements:
                    row = rows[(q.id, e.id)]
                    writer.writerow([run_id, q.id, e.id, e.check, row.rating, row.quote, row.reason, draft.rater])
        counts = {k: sum(1 for r in rows.values() if r.rating == k) for k in ("fully", "partly", "missing")}
        print(f"{run_id}: fully {counts['fully']}, partly {counts['partly']}, missing {counts['missing']} of {len(rows)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
