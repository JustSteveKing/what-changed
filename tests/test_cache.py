import asyncio
from dataclasses import replace

from what_changed.answer import answer
from what_changed.cache import TtlCache
from what_changed.config import Config
from what_changed.contract import DirectLookup, RouteResult, SourceRecord

from tests.helpers import TEST_CONFIG, run

CONFIG = replace(TEST_CONFIG, direct_cache_ttl_s=60.0)
OK = RouteResult(
    terminal_state="completed",
    incomplete=False,
    incomplete_reasons=[],
    text="v4.4.7",
    sources=[SourceRecord(position=1, url="https://repo.packagist.org/p2/livewire/livewire.json", title=None, kind="packagist_metadata", claims=["x"])],
    error=None,
    cost=None,
    cost_note="stub",
)
QUESTION = "What is the latest version of livewire/livewire?"


class Counter:
    def __init__(self, result: RouteResult) -> None:
        self.calls = 0
        self.result = result

    async def direct(self, lookup: DirectLookup, config: Config, cancel: asyncio.Event | None) -> RouteResult:
        self.calls += 1
        return self.result

    async def research(self, question: str, config: Config, cancel: asyncio.Event | None) -> RouteResult:
        self.calls += 1
        return self.result


def test_repeat_question_is_served_from_the_cache_even_with_different_case_and_spacing() -> None:
    clock = [0.0]
    cache: TtlCache[RouteResult] = TtlCache(60.0, now=lambda: clock[0])
    counter = Counter(OK)
    first = run(answer(QUESTION, config=CONFIG, direct=counter.direct, direct_cache=cache))
    second = run(answer("  what is the latest version of LIVEWIRE/livewire? ", config=CONFIG, direct=counter.direct, direct_cache=cache))
    assert counter.calls == 1
    assert (first.cached, second.cached) == (False, True)

    clock[0] = 60.0
    third = run(answer(QUESTION, config=CONFIG, direct=counter.direct, direct_cache=cache))
    assert counter.calls == 2
    assert third.cached is False


def test_failed_lookup_is_not_cached() -> None:
    cache: TtlCache[RouteResult] = TtlCache(60.0)
    counter = Counter(OK.model_copy(update={"terminal_state": "failed"}))
    run(answer(QUESTION, config=CONFIG, direct=counter.direct, direct_cache=cache))
    run(answer(QUESTION, config=CONFIG, direct=counter.direct, direct_cache=cache))
    assert counter.calls == 2


def test_research_answers_are_not_cached() -> None:
    cache: TtlCache[RouteResult] = TtlCache(60.0)
    counter = Counter(OK)
    run(answer("What changed in the latest Laravel release?", config=CONFIG, research=counter.research, direct_cache=cache))
    run(answer("What changed in the latest Laravel release?", config=CONFIG, research=counter.research, direct_cache=cache))
    assert counter.calls == 2


def test_ttl_of_zero_turns_the_cache_off() -> None:
    cache: TtlCache[str] = TtlCache(0.0)
    cache.set("k", "v")
    assert cache.get("k") is None
