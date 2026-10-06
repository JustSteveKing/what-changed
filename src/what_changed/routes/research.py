import asyncio
from collections.abc import AsyncIterable

from tabstack import AsyncTabstack
from tabstack.types.research_event import ResearchEvent

from what_changed.config import Config
from what_changed.contract import AnswerError, RouteResult, SourceRecord
from what_changed.deadline import with_deadline

COST_NOTE = "Tabstack does not report cost in API responses; spend is shown in the Tabstack console. See docs/VERIFIED.md."


# Turns a stream of provider events into a RouteResult. Kept separate from the network
# call so replay fixtures can drive it. Provider event objects stop here.
async def collect_research(events: AsyncIterable[ResearchEvent]) -> RouteResult:
    async for event in events:
        if event.event == "complete":
            pages = event.data.metadata.cited_pages or []
            sources = [
                SourceRecord(position=i + 1, url=page.url, title=page.title, kind="research_citation", claims=list(page.claims))
                for i, page in enumerate(pages)
            ]
            text = event.data.report
            reasons = []
            if text.strip() == "":
                reasons.append("The report is empty.")
            if not sources:
                reasons.append("No sources were cited.")
            return RouteResult(
                terminal_state="completed",
                incomplete=bool(reasons),
                incomplete_reasons=reasons,
                text=text,
                sources=sources,
                error=None,
                cost=None,
                cost_note=COST_NOTE,
            )
        if event.event == "error":
            return RouteResult(
                terminal_state="failed",
                incomplete=True,
                incomplete_reasons=["Research reported an error."],
                text="",
                sources=[],
                error=AnswerError(name=event.data.error.name, message=event.data.error.message),
                cost=None,
                cost_note=COST_NOTE,
            )

    # The stream ended without a complete or error event.
    return RouteResult(
        terminal_state="stream_closed",
        incomplete=True,
        incomplete_reasons=["The stream ended without a terminal event."],
        text="",
        sources=[],
        error=None,
        cost=None,
        cost_note=COST_NOTE,
    )


async def run_research(
    question: str,
    config: Config,
    cancel: asyncio.Event | None = None,
    client: AsyncTabstack | None = None,
) -> RouteResult:
    client = client or AsyncTabstack()

    async def call() -> RouteResult:
        stream = await client.agent.research(query=question, mode=config.research_mode)
        async with stream:
            return await collect_research(stream)

    # The SDK's timeout is per read, so a stream that keeps sending events is never
    # cut off by it. This deadline covers the whole call.
    # Setting `cancel` (Ctrl+C in the CLI) stops it early and closes the stream.
    return await with_deadline(call(), config.research_timeout_s, "Research", cancel)
