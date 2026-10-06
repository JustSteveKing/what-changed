import asyncio
from collections.abc import Awaitable
from typing import TypeVar

T = TypeVar("T")


class TimedOut(Exception):
    pass


# Runs `awaitable` with a limit on the whole call. When the limit passes, asyncio
# cancels the work in progress (closing any open stream) and TimedOut is raised.
async def with_deadline(awaitable: Awaitable[T], seconds: float, what: str) -> T:
    try:
        async with asyncio.timeout(seconds):
            return await awaitable
    except TimeoutError:
        raise TimedOut(f"{what} timed out after {round(seconds * 1000)} ms") from None
