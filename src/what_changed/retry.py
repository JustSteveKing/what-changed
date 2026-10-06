import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypeVar

from what_changed.deadline import Cancelled

T = TypeVar("T")


class HttpError(Exception):
    def __init__(self, message: str, status: int, retry_after_s: float | None, rate_limit_exhausted: bool) -> None:
        super().__init__(message)
        self.status = status
        # From a Retry-After header, if the server sent one.
        self.retry_after_s = retry_after_s
        # GitHub's primary rate limit: x-ratelimit-remaining is 0. GitHub's docs say not
        # to retry before x-ratelimit-reset, which can be up to an hour away.
        self.rate_limit_exhausted = rate_limit_exhausted


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int
    base_delay_s: float
    # Longest wait this code will accept between attempts, including Retry-After.
    max_delay_s: float


# Network errors, per-attempt timeouts, 429 and 5xx are worth another try.
# Other 4xx responses will not change on retry.
def is_retryable(error: Exception) -> bool:
    if isinstance(error, Cancelled):
        return False
    if isinstance(error, HttpError):
        if error.rate_limit_exhausted:
            return False
        return error.status == 429 or error.status >= 500
    return True


def delay_for(error: Exception, attempt: int, policy: RetryPolicy) -> float | None:
    if isinstance(error, HttpError) and error.retry_after_s is not None:
        return error.retry_after_s if error.retry_after_s <= policy.max_delay_s else None
    return min(policy.base_delay_s * 2.0 ** (attempt - 1), policy.max_delay_s)


async def _sleep(seconds: float, cancel: asyncio.Event | None) -> None:
    if cancel is None:
        await asyncio.sleep(seconds)
        return
    try:
        await asyncio.wait_for(cancel.wait(), timeout=seconds)
    except TimeoutError:
        return
    raise Cancelled("Cancelled while waiting to retry")


# Runs `attempt` up to max_attempts times with exponential backoff. The last
# error is re-raised unchanged so the caller still sees what actually happened.
async def with_retries(attempt: Callable[[], Awaitable[T]], policy: RetryPolicy, cancel: asyncio.Event | None = None) -> T:
    n = 1
    while True:
        try:
            return await attempt()
        except Exception as error:
            if n >= policy.max_attempts or not is_retryable(error):
                raise
            delay = delay_for(error, n, policy)
            if delay is None:
                raise
            await _sleep(delay, cancel)
            n += 1
