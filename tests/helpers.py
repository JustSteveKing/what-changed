import asyncio
from collections.abc import AsyncIterator, Awaitable
from typing import Any, TypeVar

from pydantic import TypeAdapter
from tabstack.types.research_event import ResearchEvent

from what_changed.config import Config

T = TypeVar("T")

TEST_CONFIG = Config(research_mode="fast", github_token=None, user_agent="test", direct_timeout_s=1.0, research_timeout_s=1.0)

_events: TypeAdapter[ResearchEvent] = TypeAdapter(ResearchEvent)


def run(awaitable: Awaitable[T]) -> T:
    async def wrapper() -> T:
        return await awaitable

    return asyncio.run(wrapper())


def to_event(raw: dict[str, Any]) -> ResearchEvent:
    return _events.validate_python(raw)


async def stream_of(raw_events: list[dict[str, Any]]) -> AsyncIterator[ResearchEvent]:
    for raw in raw_events:
        yield to_event(raw)
