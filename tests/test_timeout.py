import asyncio
import time
from dataclasses import replace
from typing import Any

import httpx
import pytest
from tabstack import AsyncTabstack

from what_changed.answer import answer
from what_changed.config import load_config
from what_changed.deadline import TimedOut
from what_changed.routes.research import run_research

from tests.helpers import TEST_CONFIG, run
from tests.sse_server import SseScript, SseServer

START = {"event": "start", "data": {"message": "start", "timestamp": 1}}


def test_aborts_a_research_stream_that_stays_open_past_the_limit() -> None:
    config = replace(TEST_CONFIG, research_timeout_s=0.2)
    with SseServer(SseScript(events=[START], hang=True)) as server:
        client = AsyncTabstack(api_key="test-key", base_url=server.base_url, max_retries=0)
        started = time.monotonic()
        with pytest.raises(TimedOut, match="Research timed out after 200 ms"):
            run(run_research("q", config, client=client))
        assert time.monotonic() - started < 2


def test_aborts_a_direct_lookup_that_does_not_respond(monkeypatch: pytest.MonkeyPatch) -> None:
    async def never(self: httpx.AsyncClient, url: str, **kwargs: Any) -> httpx.Response:
        await asyncio.sleep(60)
        raise AssertionError("unreachable")

    monkeypatch.setattr(httpx.AsyncClient, "get", never)
    config = replace(TEST_CONFIG, direct_timeout_s=0.05)
    result = run(answer("What is the latest version of livewire/livewire?", config=config))
    assert result.terminal_state == "timed_out"
    assert result.error is not None
    assert (result.error.name, result.error.message) == ("TimedOut", "Packagist (livewire/livewire) timed out after 50 ms")


def test_reads_the_limits_from_the_environment() -> None:
    loaded = load_config({"DIRECT_TIMEOUT_MS": "1234", "RESEARCH_TIMEOUT_MS": "5678"})
    assert (loaded.direct_timeout_s, loaded.research_timeout_s) == (1.234, 5.678)
    with pytest.raises(ValueError):
        load_config({"DIRECT_TIMEOUT_MS": "soon"})
