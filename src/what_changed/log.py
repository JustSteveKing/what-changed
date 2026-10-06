import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import AwareDatetime

from what_changed.contract import ApplicationAnswer, Model, TerminalState


# One JSON line per request. The question text is left out on purpose: the
# stored answer (linked by answer_id) holds it, and logs tend to travel further.
class RequestLogEntry(Model):
    ts: AwareDatetime
    answer_id: uuid.UUID | None
    route: Literal["direct", "research", "decline"]
    terminal_state: TerminalState
    latency_ms: int
    incomplete: bool
    source_count: int
    error_name: str | None
    # Only ever a cost the API reported. Tabstack reports none, so this is None.
    reported_cost: None


def log_request(answer: ApplicationAnswer, answer_id: uuid.UUID | None, file: Path) -> RequestLogEntry:
    entry = RequestLogEntry(
        ts=datetime.now(UTC),
        answer_id=answer_id,
        route=answer.decision.route,
        terminal_state=answer.terminal_state,
        latency_ms=int((answer.ended_at - answer.started_at).total_seconds() * 1000),
        incomplete=answer.incomplete,
        source_count=len(answer.sources),
        error_name=answer.error.name if answer.error else None,
        reported_cost=answer.cost,
    )
    file.parent.mkdir(parents=True, exist_ok=True)
    with file.open("a") as handle:
        handle.write(entry.model_dump_json() + "\n")
    return entry
