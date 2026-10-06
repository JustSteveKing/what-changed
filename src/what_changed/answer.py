import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Literal

from what_changed.cache import TtlCache
from what_changed.config import Config, load_config
from what_changed.contract import (
    AnswerError,
    ApplicationAnswer,
    DirectLookup,
    ResearchDecision,
    RouteDecision,
    RouteResult,
    TerminalState,
)
from what_changed.deadline import Cancelled, TimedOut
from what_changed.router import find_packages, normalise, route
from what_changed.routes.direct import PackagistVersion, fetch_packagist_versions, run_direct
from what_changed.routes.research import run_research
from what_changed.log import log_request
from what_changed.store import store_answer

# "routed" is the feature. "demo" reproduces the tagged demo (every question goes to one
# Research call) through this same entry point, so baseline outputs share one shape.
Strategy = Literal["routed", "demo"]

RunDirect = Callable[[DirectLookup, Config, asyncio.Event | None], Awaitable[RouteResult]]
RunResearch = Callable[[str, Config, asyncio.Event | None], Awaitable[RouteResult]]
FetchVersions = Callable[[str, Config, asyncio.Event | None], Awaitable[list[PackagistVersion]]]


# True when any tagged version (stable or pre-release) starts with the given version,
# so "13" matches 13.34.0 and "4.2" matches 4.2.4-beta.2.
def version_exists(version: str, normalized_versions: list[str]) -> bool:
    wanted = [int(part) for part in version.split(".")]
    for normalized in normalized_versions:
        parts = normalized.replace("-", ".").split(".")
        if all(i < len(parts) and parts[i].isdigit() and int(parts[i]) == want for i, want in enumerate(wanted)):
            return True
    return False


# Direct lookups are cached briefly, keyed on the normalised question. Research
# answers are not cached: the point of the feature is a current answer, and a
# cached research answer could miss a release tagged minutes ago. This is only about
# this application; Tabstack has its own server-side cache, which the `nocache`
# request parameter bypasses (see docs/VERIFIED.md).
_default_cache: tuple[float, TtlCache[RouteResult]] | None = None


def default_direct_cache(config: Config) -> TtlCache[RouteResult]:
    global _default_cache
    if _default_cache is None or _default_cache[0] != config.direct_cache_ttl_s:
        _default_cache = (config.direct_cache_ttl_s, TtlCache(config.direct_cache_ttl_s))
    return _default_cache[1]


def declined(reason: str) -> RouteResult:
    return RouteResult(
        terminal_state="declined",
        incomplete=False,
        incomplete_reasons=[],
        text=reason,
        sources=[],
        error=None,
        cost=None,
        cost_note="No outbound call was made.",
    )


def demo_decision(question: str) -> ResearchDecision:
    return ResearchDecision(
        route="research",
        reason="Demo behaviour: every question goes to one Research call.",
        packages=[m.package for m in find_packages(normalise(question))],
        version_mentioned=None,
    )


async def run_decision(
    question: str,
    decision: RouteDecision,
    config: Config,
    cancel: asyncio.Event | None,
    direct: RunDirect,
    research: RunResearch,
    fetch_versions: FetchVersions,
    cache: TtlCache[RouteResult],
) -> tuple[RouteResult, bool]:
    if decision.route == "decline":
        return declined(decision.reason), False
    if decision.route == "direct":
        key = normalise(question)
        hit = cache.get(key)
        if hit is not None:
            return hit, True
        result = await direct(decision.lookup, config, cancel)
        # Only successful lookups are cached; a failure should be retried next time.
        if result.terminal_state == "completed":
            cache.set(key, result)
        return result, False

    # A research call about a version that has never been tagged would answer
    # from speculation, so check Packagist first.
    if decision.version_mentioned is not None:
        package, version = decision.version_mentioned.package, decision.version_mentioned.version
        versions = await fetch_versions(package, config, cancel)
        if not version_exists(version, [v.version_normalized for v in versions]):
            return declined(f"Packagist lists no tagged release of {package} matching {version}."), False
    return await research(question, config, cancel), False


async def answer(
    question: str,
    *,
    strategy: Strategy = "routed",
    config: Config | None = None,
    # Setting this event cancels whatever call is in flight.
    cancel: asyncio.Event | None = None,
    # Overridable so tests can run without the network.
    direct: RunDirect = run_direct,
    research: RunResearch = run_research,
    fetch_versions: FetchVersions = fetch_packagist_versions,
    direct_cache: TtlCache[RouteResult] | None = None,
) -> ApplicationAnswer:
    started_at = datetime.now(UTC)
    config = config or load_config()
    decision = demo_decision(question) if strategy == "demo" else route(question)

    cache = direct_cache if direct_cache is not None else default_direct_cache(config)
    cached = False
    try:
        result, cached = await run_decision(question, decision, config, cancel, direct, research, fetch_versions, cache)
    except Exception as error:
        state: TerminalState = "timed_out" if isinstance(error, TimedOut) else "cancelled" if isinstance(error, Cancelled) else "failed"
        reasons = {"timed_out": "The call timed out.", "cancelled": "The call was cancelled.", "failed": "The call threw an error."}
        result = RouteResult(
            terminal_state=state,
            incomplete=True,
            incomplete_reasons=[reasons[state]],
            text="",
            sources=[],
            error=AnswerError(name=type(error).__name__, message=str(error)),
            cost=None,
            cost_note="No cost reported.",
        )

    final = ApplicationAnswer(
        question=question,
        decision=decision,
        **result.model_dump(),
        cached=cached,
        started_at=started_at,
        ended_at=datetime.now(UTC),
    )
    stored = store_answer(final, config.answer_store_dir) if config.answer_store_dir is not None else None
    if config.request_log_file is not None:
        log_request(final, stored.id if stored else None, config.request_log_file)
    return final
