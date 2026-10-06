import asyncio
import contextlib
from collections.abc import Awaitable
from typing import Any, TypeVar

T = TypeVar("T")


class TimedOut(Exception):
    pass


class Cancelled(Exception):
    pass


# Runs `awaitable` with a limit on the whole call, and stops it early if `cancel` is
# set (Ctrl+C in the CLI). Either way the work in progress is cancelled, which closes
# any open stream, and the exception says which of the two happened.
async def with_deadline(awaitable: Awaitable[T], seconds: float, what: str, cancel: asyncio.Event | None = None) -> T:
    work = asyncio.ensure_future(awaitable)
    stop = asyncio.ensure_future(cancel.wait()) if cancel is not None else None
    waiting: set[asyncio.Future[Any]] = {work, stop} if stop is not None else {work}
    try:
        done, _ = await asyncio.wait(waiting, timeout=seconds, return_when=asyncio.FIRST_COMPLETED)
    finally:
        if stop is not None:
            stop.cancel()

    if work in done:
        return work.result()

    work.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await work
    if cancel is not None and cancel.is_set():
        raise Cancelled(f"{what} was cancelled")
    raise TimedOut(f"{what} timed out after {round(seconds * 1000)} ms")
