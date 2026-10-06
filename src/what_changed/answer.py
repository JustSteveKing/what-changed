import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Literal

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
) -> RouteResult:
    if decision.route == "decline":
        return declined(decision.reason)
    if decision.route == "direct":
        return await direct(decision.lookup, config, cancel)

    # A research call about a version that has never been tagged would answer
    # from speculation, so check Packagist first.
    if decision.version_mentioned is not None:
        package, version = decision.version_mentioned.package, decision.version_mentioned.version
        versions = await fetch_versions(package, config, cancel)
        if not version_exists(version, [v.version_normalized for v in versions]):
            return declined(f"Packagist lists no tagged release of {package} matching {version}.")
    return await research(question, config, cancel)


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
) -> ApplicationAnswer:
    started_at = datetime.now(UTC)
    config = config or load_config()
    decision = demo_decision(question) if strategy == "demo" else route(question)

    try:
        result = await run_decision(question, decision, config, cancel, direct, research, fetch_versions)
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

    return ApplicationAnswer(
        question=question,
        decision=decision,
        **result.model_dump(),
        started_at=started_at,
        ended_at=datetime.now(UTC),
    )
