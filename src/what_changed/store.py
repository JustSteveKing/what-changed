import uuid
from datetime import UTC, datetime
from pathlib import Path

from pydantic import AwareDatetime

from what_changed.contract import ApplicationAnswer, Model


class StoredAnswer(Model):
    id: uuid.UUID
    stored_at: AwareDatetime
    answer: ApplicationAnswer


# Writes one JSON file per answer, including its ordered source record, so any
# answer can be inspected later exactly as it was returned.
def store_answer(answer: ApplicationAnswer, directory: Path) -> StoredAnswer:
    stored = StoredAnswer(id=uuid.uuid4(), stored_at=datetime.now(UTC), answer=answer)
    directory.mkdir(parents=True, exist_ok=True)
    name = f"{answer.started_at.strftime('%Y-%m-%dT%H-%M-%S-%f')}-{stored.id}.json"
    (directory / name).write_text(stored.model_dump_json(indent=2) + "\n")
    return stored
