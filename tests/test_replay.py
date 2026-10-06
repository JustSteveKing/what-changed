import asyncio
from dataclasses import replace
from pathlib import Path

from tabstack import AsyncTabstack

from what_changed.answer import answer
from what_changed.config import Config
from what_changed.contract import ApplicationAnswer, ReplayFixture, RouteResult
from what_changed.routes.research import run_research

from tests.helpers import TEST_CONFIG, run
from tests.sse_server import SseScript, SseServer

CONFIG = replace(TEST_CONFIG, research_timeout_s=5.0)
FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> ReplayFixture:
    return ReplayFixture.model_validate_json((FIXTURES / name).read_text())


# Replays a fixture over real SSE through the real SDK, then through answer().
def replay(name: str) -> ApplicationAnswer:
    fixture = load(name)
    with SseServer(SseScript(events=[e.model_dump() for e in fixture.events])) as server:
        client = AsyncTabstack(api_key="test-key", base_url=server.base_url, max_retries=0)

        async def research(question: str, config: Config, cancel: asyncio.Event | None) -> RouteResult:
            return await run_research(question, config, cancel, client)

        return run(answer("What changed in the latest Laravel release?", config=CONFIG, research=research))


def test_completed_stream_gives_completed_answer_with_ordered_source_record() -> None:
    result = replay("research-completed.json")
    assert result.terminal_state == "completed"
    assert result.error is None
    assert result.text
    assert result.sources
    assert [s.position for s in result.sources] == list(range(1, len(result.sources) + 1))


def test_streamed_error_gives_failed_answer_with_the_error_verbatim() -> None:
    error_event = next(e for e in load("research-error.json").events if e.event == "error")
    error = error_event.data["error"]
    assert isinstance(error, dict)
    result = replay("research-error.json")
    assert result.terminal_state == "failed"
    assert result.error is not None and (result.error.name, result.error.message) == (error["name"], error["message"])
    assert result.sources == []


def test_stream_that_closes_without_a_terminal_event_gives_stream_closed() -> None:
    result = replay("research-stream-closed.json")
    assert result.terminal_state == "stream_closed"
    assert result.incomplete_reasons == ["The stream ended without a terminal event."]
    assert result.text == ""


def test_the_three_fixtures_give_three_different_answers() -> None:
    results = [replay(n) for n in ("research-completed.json", "research-error.json", "research-stream-closed.json")]
    shapes = {r.model_dump_json(include={"terminal_state", "error", "text", "sources"}) for r in results}
    assert len(shapes) == 3
