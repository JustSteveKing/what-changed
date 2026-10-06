import csv
from collections.abc import Callable
import json
import statistics
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import get_args

from what_changed.contract import EvalQuestionSet, RunManifest, RunRecord, TerminalState

from eval.urls import is_well_formed, normalise_url

# Deterministic checks only. Answer quality is scored by a person in scoring.csv;
# nothing here judges whether an answer is right.


@dataclass(frozen=True)
class Checks:
    question_id: str
    route_matched: bool
    source_present: bool
    malformed_urls: list[str]
    duplicate_url_variants: list[list[str]]
    empty_sources: bool
    sources_with_empty_claims: int
    terminal_state_present: bool


def check(record: RunRecord) -> Checks:
    groups: dict[str, list[str]] = {}
    for source in record.sources:
        if is_well_formed(source.url):
            groups.setdefault(normalise_url(source.url), []).append(source.url)
    return Checks(
        question_id=record.question_id,
        route_matched=record.decision.route == record.expected_route,
        source_present=bool(record.sources),
        malformed_urls=[s.url for s in record.sources if not is_well_formed(s.url)],
        duplicate_url_variants=[urls for urls in groups.values() if len(urls) > 1],
        empty_sources=not record.sources,
        sources_with_empty_claims=sum(1 for s in record.sources if not s.claims),
        terminal_state_present=record.terminal_state is not None,
    )


def main(argv: list[str]) -> int:
    if not argv:
        print("Usage: uv run python -m eval.score <run-id>", file=sys.stderr)
        return 1
    run_id = argv[0]
    run_dir = Path("runs") / run_id

    manifest = RunManifest.model_validate_json((run_dir / "manifest.json").read_text())
    questions = EvalQuestionSet.validate_json(Path("eval/questions.json").read_text())
    records = [RunRecord.model_validate_json(p.read_text()) for p in sorted(run_dir.glob("q[0-9][0-9].json"))]

    checks = [check(r) for r in records]
    (run_dir / "checks.json").write_text(json.dumps([asdict(c) for c in checks], indent=2) + "\n")

    # Scoring sheet: one row per required element, rating left blank for a person.
    by_id = {q.id: q for q in questions}
    with (run_dir / "scoring.csv").open("w", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["run_id", "question_id", "question", "element_id", "check", "source", "answer_file", "rating (fully|partly|missing)", "reviewer_notes"])
        for record in records:
            question = by_id[record.question_id]
            for element in question.required_elements:
                writer.writerow([run_id, question.id, question.question, element.id, element.check, element.source, f"{run_dir}/{question.id}.json", "", ""])

    total = len(records)

    def count(predicate: Callable[[RunRecord], object]) -> int:
        return sum(1 for r in records if predicate(r))

    def passed(predicate: Callable[[Checks], object]) -> str:
        return f"{sum(1 for c in checks if predicate(c))} / {total}"

    def failed_ids(predicate: Callable[[Checks], object]) -> str:
        return ", ".join(c.question_id for c in checks if predicate(c)) or "none"

    research = [r.duration_ms for r in records if r.decision.route == "research" and r.terminal_state != "declined"]
    timing = (
        f"min {min(research)} ms, median {round(statistics.median(research))} ms, max {max(research)} ms"
        if research
        else "no research calls"
    )

    lines = [
        f"### Run {run_id}",
        "",
        f"- Strategy: {manifest.strategy}; research mode: {manifest.research_mode}",
        f"- Started {manifest.started_at.isoformat()}, ended {manifest.ended_at.isoformat() if manifest.ended_at else 'not recorded (run did not finish)'}",
        f"- Commit {manifest.git_commit}{' (working tree dirty)' if manifest.git_dirty else ''}; Python {manifest.python}; {manifest.os}",
        f"- Records: {total} of {len(questions)}",
        "",
        "| Outcome | Count |",
        "| --- | --- |",
        *[f"| terminal state {state} | {sum(1 for r in records if r.terminal_state == state)} / {total} |" for state in get_args(TerminalState)],
        f"| no terminal state recorded | {count(lambda r: r.terminal_state is None)} / {total} |",
        f"| error name contains \"Timeout\" | {count(lambda r: r.error is not None and 'Timeout' in r.error.name)} / {total} |",
        f"| returned no answer text | {count(lambda r: r.text.strip() == '')} / {total} |",
        f"| marked incomplete by the application | {count(lambda r: r.incomplete)} / {total} |",
        "",
        "| Deterministic check | Passed | Failed question IDs |",
        "| --- | --- | --- |",
        f"| route matched expectation | {passed(lambda c: c.route_matched)} | {failed_ids(lambda c: not c.route_matched)} |",
        f"| source record present | {passed(lambda c: c.source_present)} | {failed_ids(lambda c: not c.source_present)} |",
        f"| all cited URLs well formed | {passed(lambda c: not c.malformed_urls)} | {failed_ids(lambda c: c.malformed_urls)} |",
        f"| no duplicate URL variants | {passed(lambda c: not c.duplicate_url_variants)} | {failed_ids(lambda c: c.duplicate_url_variants)} |",
        f"| no empty source array | {passed(lambda c: not c.empty_sources)} | {failed_ids(lambda c: c.empty_sources)} |",
        f"| every source has at least one claim | {passed(lambda c: c.sources_with_empty_claims == 0 and not c.empty_sources)} | {failed_ids(lambda c: c.sources_with_empty_claims > 0 or c.empty_sources)} |",
        f"| terminal state present | {passed(lambda c: c.terminal_state_present)} | {failed_ids(lambda c: not c.terminal_state_present)} |",
        "",
        f"Research call wall-clock time ({len(research)} calls): {timing}.",
        "",
    ]
    (run_dir / "summary.md").write_text("\n".join(lines))
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
