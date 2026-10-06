import asyncio
from dataclasses import replace
from pathlib import Path

from what_changed.answer import answer
from what_changed.config import Config
from what_changed.contract import RouteResult, SourceRecord
from what_changed.store import StoredAnswer

from tests.helpers import TEST_CONFIG, run

RESULT = RouteResult(
    terminal_state="completed",
    incomplete=False,
    incomplete_reasons=[],
    text="stub",
    sources=[
        SourceRecord(position=1, url="https://laravel.com/docs/13.x/upgrade", title="Upgrade Guide", kind="research_citation", claims=[]),
        SourceRecord(position=2, url="https://github.com/laravel/framework/releases", title=None, kind="research_citation", claims=[]),
    ],
    error=None,
    cost=None,
    cost_note="stub",
)


async def stub_research(question: str, config: Config, cancel: asyncio.Event | None) -> RouteResult:
    return RESULT


def test_writes_every_answer_with_its_sources_in_order(tmp_path: Path) -> None:
    config = replace(TEST_CONFIG, answer_store_dir=tmp_path)
    run(answer("What changed in the latest Laravel release?", config=config, research=stub_research))
    run(answer("Is Livewire better than Inertia?", config=config))

    stored = [StoredAnswer.model_validate_json(p.read_text()) for p in sorted(tmp_path.iterdir())]
    assert len(stored) == 2
    research = next(s for s in stored if s.answer.decision.route == "research")
    assert [(s.position, s.url) for s in research.answer.sources] == [
        (1, "https://laravel.com/docs/13.x/upgrade"),
        (2, "https://github.com/laravel/framework/releases"),
    ]
    assert next(s for s in stored if s.answer.decision.route == "decline").answer.terminal_state == "declined"
