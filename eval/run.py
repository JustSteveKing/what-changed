import asyncio
import platform
import subprocess
import sys
from dataclasses import replace
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

from what_changed.answer import Strategy, answer
from what_changed.config import load_config
from what_changed.contract import EvalQuestionSet, RunManifest, RunRecord

# Usage: uv run python -m eval.run <demo|routed> [label] [--first q06,q20]


def git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout.strip()


async def main(argv: list[str]) -> int:
    if not argv or argv[0] not in ("demo", "routed"):
        print("Usage: uv run python -m eval.run <demo|routed> [label] [--first q06,q20]", file=sys.stderr)
        return 1
    strategy: Strategy = "demo" if argv[0] == "demo" else "routed"
    label = argv[1] if len(argv) > 1 and not argv[1].startswith("--") else strategy
    first = argv[argv.index("--first") + 1].split(",") if "--first" in argv else []

    questions = EvalQuestionSet.validate_json(Path("eval/questions.json").read_text())
    rank = {qid: i for i, qid in enumerate(first)}
    ordered = sorted(questions, key=lambda q: (rank.get(q.id, len(first)), q.id))

    # The runner writes its own run records, so answers are not stored a second time.
    config = replace(load_config(), answer_store_dir=None)
    started_at = datetime.now(UTC)
    run_id = f"{started_at.strftime('%Y-%m-%dT%H-%M-%S')}Z-python-{label}"
    run_dir = Path("runs") / run_id
    run_dir.mkdir(parents=True)

    manifest = RunManifest(
        run_id=run_id,
        strategy=strategy,
        research_mode=config.research_mode,
        started_at=started_at,
        ended_at=None,
        git_commit=git("rev-parse", "HEAD"),
        git_dirty=git("status", "--porcelain") != "",
        python=platform.python_version(),
        os=f"{platform.system()} {platform.release()} {platform.machine()}",
        packages={name: version(name) for name in ("tabstack", "pydantic", "httpx", "pytest", "mypy")},
        github_token_set=config.github_token is not None,
        question_order=[q.id for q in ordered],
    )
    manifest_path = run_dir / "manifest.json"
    manifest_path.write_text(manifest.model_dump_json(indent=2) + "\n")

    # One question at a time, so each record's timing is not affected by the others.
    for question in ordered:
        print(f"{question.id} {question.question}", flush=True)
        result = await answer(question.question, strategy=strategy, config=config)
        record = RunRecord(
            **result.model_dump(),
            run_id=run_id,
            question_id=question.id,
            strategy=strategy,
            expected_route=question.expected_route,
            duration_ms=int((result.ended_at - result.started_at).total_seconds() * 1000),
        )
        (run_dir / f"{question.id}.json").write_text(record.model_dump_json(indent=2) + "\n")
        print(f"  {record.decision.route} {record.terminal_state or 'none'} {record.duration_ms}ms sources={len(record.sources)}", flush=True)

    manifest.ended_at = datetime.now(UTC)
    manifest_path.write_text(manifest.model_dump_json(indent=2) + "\n")
    print(f"Wrote {run_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
