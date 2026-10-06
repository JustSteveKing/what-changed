import asyncio
import os
import signal
import subprocess
import sys
from dataclasses import replace

import pytest
from tabstack import AsyncTabstack

from what_changed.answer import answer
from what_changed.contract import EXIT_CODES
from what_changed.deadline import Cancelled
from what_changed.routes.research import run_research

from tests.helpers import TEST_CONFIG, run
from tests.sse_server import SseScript, SseServer

HANGING = SseScript(events=[{"event": "start", "data": {"message": "start", "timestamp": 1}}], hang=True)
CONFIG = replace(TEST_CONFIG, research_timeout_s=10.0)


def test_cancels_an_in_flight_research_stream_when_the_event_is_set() -> None:
    async def scenario() -> None:
        cancel = asyncio.Event()
        asyncio.get_running_loop().call_later(0.1, cancel.set)
        client = AsyncTabstack(api_key="test-key", base_url=server.base_url, max_retries=0)
        with pytest.raises(Cancelled, match="Research was cancelled"):
            await run_research("q", CONFIG, cancel, client)

    with SseServer(HANGING) as server:
        run(scenario())


def test_returns_cancelled_without_calling_out_when_already_cancelled() -> None:
    async def scenario() -> str:
        cancel = asyncio.Event()
        cancel.set()
        result = await answer("What is the latest version of livewire/livewire?", config=CONFIG, cancel=cancel)
        return result.terminal_state

    assert run(scenario()) == "cancelled"


def test_ctrl_c_in_the_cli_cancels_the_call_and_exits_with_the_cancelled_code() -> None:
    with SseServer(HANGING) as server:
        # A placeholder key: the real one must never reach a child process in tests.
        env = {**os.environ, "TABSTACK_API_KEY": "test-key", "TABSTACK_BASE_URL": server.base_url}
        child = subprocess.Popen(
            [sys.executable, "-m", "what_changed.cli", "What changed in the latest Laravel release?"],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        # Send SIGINT once the research request has reached the server.
        assert server.requested.wait(timeout=15)
        child.send_signal(signal.SIGINT)
        stdout, _ = child.communicate(timeout=15)
    assert "State: cancelled" in stdout
    assert child.returncode == EXIT_CODES["cancelled"]
