import asyncio
from datetime import UTC, datetime

from what_changed.answer import answer, version_exists
from what_changed.config import Config
from what_changed.contract import AnswerError, ApplicationAnswer, DirectLookup, RouteResult, SourceRecord
from what_changed.routes.direct import PackagistVersion, expand_minified, is_stable, latest_stable, version_key
from what_changed.routes.research import collect_research

from tests.helpers import TEST_CONFIG, run, stream_of

OK = RouteResult(
    terminal_state="completed",
    incomplete=False,
    incomplete_reasons=[],
    text="stub",
    sources=[SourceRecord(position=1, url="https://example.com/a", title=None, kind="research_citation", claims=["x"])],
    error=None,
    cost=None,
    cost_note="stub",
)


async def ok_direct(lookup: DirectLookup, config: Config, cancel: asyncio.Event | None) -> RouteResult:
    return OK


async def ok_research(question: str, config: Config, cancel: asyncio.Event | None) -> RouteResult:
    return OK


async def versions_13(package: str, config: Config, cancel: asyncio.Event | None) -> list[PackagistVersion]:
    return [PackagistVersion(version="v13.34.0", version_normalized="13.34.0.0")]


def ask(question: str, **overrides: object) -> ApplicationAnswer:
    options: dict[str, object] = {"config": TEST_CONFIG, "direct": ok_direct, "research": ok_research, "fetch_versions": versions_13}
    options.update(overrides)
    return run(answer(question, **options))  # type: ignore[arg-type]


# answer() returns one shape for every route


def test_direct() -> None:
    result = ask("What is the latest version of livewire/livewire?")
    ApplicationAnswer.model_validate(result.model_dump())
    assert result.decision.route == "direct"


def test_research() -> None:
    result = ask("What changed in Laravel 13 queues?")
    assert result.decision.route == "research"
    assert result.terminal_state == "completed"


def test_decline() -> None:
    result = ask("Is Livewire better than Inertia?")
    assert result.terminal_state == "declined"


def test_declines_research_about_a_version_packagist_has_never_tagged() -> None:
    called = []

    async def research(question: str, config: Config, cancel: asyncio.Event | None) -> RouteResult:
        called.append(question)
        return OK

    result = ask("What changed in Laravel 14?", research=research)
    assert result.terminal_state == "declined"
    assert result.text == "Packagist lists no tagged release of laravel/framework matching 14."
    assert called == []


def test_thrown_error_becomes_failed_answer() -> None:
    async def broken(lookup: DirectLookup, config: Config, cancel: asyncio.Event | None) -> RouteResult:
        raise RuntimeError("Packagist (livewire/livewire) returned HTTP 500")

    result = ask("What is the latest version of livewire/livewire?", direct=broken)
    assert result.terminal_state == "failed"
    assert result.error == AnswerError(name="RuntimeError", message="Packagist (livewire/livewire) returned HTTP 500")


def test_demo_strategy_sends_every_question_to_research() -> None:
    assert ask("Is Livewire better than Inertia?", strategy="demo").decision.route == "research"


def test_timestamps_are_timezone_aware() -> None:
    result = ask("Is Livewire better than Inertia?")
    assert result.started_at <= result.ended_at <= datetime.now(UTC)


# collect_research


def test_complete_event_maps_to_ordered_source_record() -> None:
    result = run(
        collect_research(
            stream_of(
                [
                    {"event": "start", "data": {"message": "start", "timestamp": 1}},
                    {
                        "event": "complete",
                        "data": {
                            "message": "done",
                            "report": "Report",
                            "timestamp": 2,
                            "metadata": {
                                "executedQueries": [],
                                "mode": "fast",
                                "prompt": "p",
                                "queryComplexity": "simple",
                                "researchObjective": "o",
                                "researchPlan": "p",
                                "researchQuestions": [],
                                "totalPagesAnalyzed": 2,
                                "citedPages": [
                                    {"id": "1", "url": "https://laravel.com/docs/13.x/releases", "claims": [], "sourceQueries": [], "title": "Release Notes"},
                                    {"id": "2", "url": "https://github.com/laravel/framework/releases", "claims": ["c"], "sourceQueries": []},
                                ],
                            },
                        },
                    },
                ]
            )
        )
    )
    assert result.terminal_state == "completed"
    assert [(s.position, s.url, s.title) for s in result.sources] == [
        (1, "https://laravel.com/docs/13.x/releases", "Release Notes"),
        (2, "https://github.com/laravel/framework/releases", None),
    ]


def test_complete_event_with_no_citations_is_incomplete() -> None:
    metadata = {
        "executedQueries": [], "mode": "fast", "prompt": "p", "queryComplexity": "simple",
        "researchObjective": "o", "researchPlan": "p", "researchQuestions": [], "totalPagesAnalyzed": 0,
    }  # fmt: skip
    result = run(collect_research(stream_of([{"event": "complete", "data": {"message": "", "report": "Report", "timestamp": 1, "metadata": metadata}}])))
    assert result.incomplete is True
    assert result.incomplete_reasons == ["No sources were cited."]


def test_error_event_maps_to_failed() -> None:
    result = run(
        collect_research(stream_of([{"event": "error", "data": {"message": "x", "timestamp": 1, "error": {"name": "ResearchError", "message": "boom"}}}]))
    )
    assert result.terminal_state == "failed"
    assert result.error == AnswerError(name="ResearchError", message="boom")


def test_stream_closed_when_stream_just_ends() -> None:
    result = run(collect_research(stream_of([])))
    assert result.terminal_state == "stream_closed"
    assert result.incomplete_reasons == ["The stream ended without a terminal event."]


# Packagist helpers


def test_expands_minified_versions_like_composer() -> None:
    assert expand_minified(
        [
            {"name": "a/b", "version": "v2.0.0", "time": "t2", "license": ["MIT"]},
            {"version": "v1.0.0"},
            {"version": "v0.1.0", "license": "__unset"},
        ]
    ) == [
        {"name": "a/b", "version": "v2.0.0", "time": "t2", "license": ["MIT"]},
        {"name": "a/b", "version": "v1.0.0", "time": "t2", "license": ["MIT"]},
        {"name": "a/b", "version": "v0.1.0", "time": "t2"},
    ]


def test_filters_pre_releases_and_sorts_numerically() -> None:
    assert is_stable("4.4.7.0")
    assert not is_stable("4.0.0.0-beta6")
    assert version_key("13.10.0.0") > version_key("13.9.0.0")
    latest = latest_stable(
        [
            PackagistVersion(version="v5.7.0-beta4", version_normalized="5.7.0.0-beta4"),
            PackagistVersion(version="v5.10.0", version_normalized="5.10.0.0"),
            PackagistVersion(version="v5.9.0", version_normalized="5.9.0.0"),
        ]
    )
    assert latest is not None and latest.version == "v5.10.0"


def test_matches_version_prefix_against_tagged_versions() -> None:
    assert version_exists("13", ["13.34.0.0"])
    assert version_exists("4.2", ["4.2.4.0-beta2"])
    assert not version_exists("14", ["13.34.0.0"])
    assert not version_exists("1", ["13.34.0.0"])
