import asyncio
import os
import sys
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import Literal

from tabstack import AsyncTabstack

from what_changed.contract import ReplayEvent, ReplayFixture

# Records one live research stream, event by event, for replay in tests.
# Usage: uv run python -m eval.record_fixture "question" tests/fixtures/research-completed.json


async def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print('Usage: uv run python -m eval.record_fixture "question" <output.json>', file=sys.stderr)
        return 64
    question, out = argv
    mode: Literal["fast", "balanced"] = "balanced" if os.environ.get("TABSTACK_RESEARCH_MODE") == "balanced" else "fast"
    client = AsyncTabstack(max_retries=0)
    recorded_at = datetime.now(UTC)
    events: list[ReplayEvent] = []
    stream = await client.agent.research(query=question, mode=mode)
    async with stream:
        async for event in stream:
            # exclude_unset keeps exactly the fields that came over the wire.
            events.append(ReplayEvent(event=event.event, data=event.data.model_dump(by_alias=True, exclude_unset=True, mode="json")))

    fixture = ReplayFixture(
        provenance=(
            f"Recorded from a live Tabstack Research call (mode: {mode}, tabstack {version('tabstack')}) "
            f"with eval/record_fixture.py. Query: {question!r}"
        ),
        recorded_at=recorded_at,
        events=events,
    )
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(fixture.model_dump_json(indent=2) + "\n")
    print(f"Wrote {len(events)} events to {out}: {', '.join(e.event for e in events)}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
