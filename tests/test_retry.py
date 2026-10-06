from collections.abc import Callable
from dataclasses import replace
from typing import Any

import httpx
import pytest
from tabstack import AsyncTabstack

from what_changed.answer import answer
from what_changed.routes.research import run_research

from tests.helpers import TEST_CONFIG, run
from tests.sse_server import SseScript, SseServer

CONFIG = replace(TEST_CONFIG, direct_max_attempts=3, direct_retry_base_s=0.001)
PACKAGIST_BODY = {"packages": {"livewire/livewire": [{"version": "v4.4.7", "version_normalized": "4.4.7.0"}]}}
QUESTION = "What is the latest version of livewire/livewire?"


def stub_get(monkeypatch: pytest.MonkeyPatch, responses: list[Callable[[], httpx.Response]]) -> list[int]:
    calls: list[int] = []

    async def fake_get(self: httpx.AsyncClient, url: str, **kwargs: Any) -> httpx.Response:
        calls.append(1)
        return responses[min(len(calls) - 1, len(responses) - 1)]()

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    return calls


def test_retries_a_503_and_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = stub_get(monkeypatch, [lambda: httpx.Response(503), lambda: httpx.Response(200, json=PACKAGIST_BODY)])
    assert run(answer(QUESTION, config=CONFIG)).terminal_state == "completed"
    assert len(calls) == 2


def test_gives_up_after_the_configured_number_of_attempts(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail() -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    calls = stub_get(monkeypatch, [fail])
    result = run(answer(QUESTION, config=CONFIG))
    assert result.terminal_state == "failed"
    assert result.error is not None and (result.error.name, result.error.message) == ("ConnectError", "connection refused")
    assert len(calls) == 3


def test_does_not_retry_a_404(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = stub_get(monkeypatch, [lambda: httpx.Response(404)])
    run(answer(QUESTION, config=CONFIG))
    assert len(calls) == 1


def test_does_not_retry_when_the_github_rate_limit_is_exhausted(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = stub_get(monkeypatch, [lambda: httpx.Response(403, headers={"x-ratelimit-remaining": "0"})])
    result = run(answer("When was the latest Filament release published?", config=CONFIG))
    assert result.error is not None and result.error.message == "GitHub (filamentphp/filament latest release) returned HTTP 403"
    assert len(calls) == 1


def test_does_not_wait_for_a_retry_after_longer_than_the_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = stub_get(monkeypatch, [lambda: httpx.Response(429, headers={"retry-after": "3600"})])
    run(answer(QUESTION, config=CONFIG))
    assert len(calls) == 1


def test_research_makes_exactly_one_request_when_the_api_returns_500() -> None:
    with SseServer(SseScript(status=500)) as server:
        client = AsyncTabstack(api_key="test-key", base_url=server.base_url, max_retries=0)
        with pytest.raises(Exception):
            run(run_research("q", CONFIG, client=client))
        assert server.requests == 1


def test_the_default_research_client_has_retries_switched_off(monkeypatch: pytest.MonkeyPatch) -> None:
    with SseServer(SseScript(status=500)) as server:
        monkeypatch.setenv("TABSTACK_BASE_URL", server.base_url)
        monkeypatch.setenv("TABSTACK_API_KEY", "test-key")
        with pytest.raises(Exception):
            run(run_research("q", replace(CONFIG, research_timeout_s=10.0)))
        assert server.requests == 1
