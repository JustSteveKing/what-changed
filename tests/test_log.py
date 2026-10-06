import asyncio
from dataclasses import replace
from pathlib import Path

from what_changed.answer import answer
from what_changed.config import Config
from what_changed.contract import DirectLookup, RouteResult
from what_changed.log import RequestLogEntry

from tests.helpers import TEST_CONFIG, run


async def broken(lookup: DirectLookup, config: Config, cancel: asyncio.Event | None) -> RouteResult:
    raise RuntimeError("Packagist (livewire/livewire) returned HTTP 503")


def test_one_json_line_per_request_with_route_latency_state_and_reported_cost(tmp_path: Path) -> None:
    file = tmp_path / "requests.jsonl"
    config = replace(TEST_CONFIG, answer_store_dir=tmp_path / "answers", request_log_file=file)

    run(answer("Is Livewire better than Inertia?", config=config))
    run(answer("What is the latest version of livewire/livewire?", config=config, direct=broken))

    entries = [RequestLogEntry.model_validate_json(line) for line in file.read_text().splitlines()]
    assert [(e.route, e.terminal_state, e.error_name, e.reported_cost) for e in entries] == [
        ("decline", "declined", None, None),
        ("direct", "failed", "RuntimeError", None),
    ]
    assert all(e.answer_id is not None and e.latency_ms >= 0 for e in entries)
    assert "Livewire better" not in file.read_text()
