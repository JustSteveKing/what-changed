from typing import Annotated, Literal, Union
from urllib.parse import urlparse

from pydantic import AfterValidator, AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, TypeAdapter
from pydantic.alias_generators import to_camel

# Composer's own package name rule, from https://getcomposer.org/doc/04-schema.md#name
PACKAGE_NAME_PATTERN = r"^[a-z0-9]([_.-]?[a-z0-9]+)*/[a-z0-9](([_.]|-{1,2})?[a-z0-9]+)*$"

PackageName = Annotated[str, StringConstraints(pattern=PACKAGE_NAME_PATTERN)]
GitHubRepo = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")]
NonEmpty = Annotated[str, StringConstraints(min_length=1)]


def _http_url(value: str) -> str:
    # Checked but kept exactly as given: pydantic's URL types would rewrite it.
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError(f"not an http(s) URL: {value}")
    return value


HttpUrlString = Annotated[str, AfterValidator(_http_url)]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


# What a direct route will look up. One structured call, no model.
class PackagistLatestStable(Model):
    kind: Literal["packagist_latest_stable"]
    package: PackageName


class GitHubLatestRelease(Model):
    kind: Literal["github_latest_release"]
    package: PackageName
    repo: GitHubRepo


DirectLookup = Annotated[Union[PackagistLatestStable, GitHubLatestRelease], Field(discriminator="kind")]


class VersionMention(Model):
    package: PackageName
    version: NonEmpty


class DirectDecision(Model):
    route: Literal["direct"]
    reason: NonEmpty
    lookup: DirectLookup


class ResearchDecision(Model):
    route: Literal["research"]
    reason: NonEmpty
    packages: list[PackageName]
    # A version the question names, e.g. "14" or "4.2". Checked against Packagist before research runs.
    version_mentioned: VersionMention | None


class DeclineDecision(Model):
    route: Literal["decline"]
    reason: NonEmpty


RouteDecision = Annotated[Union[DirectDecision, ResearchDecision, DeclineDecision], Field(discriminator="route")]


# One entry in the ordered source record attached to every answer.
class SourceRecord(Model):
    position: Annotated[int, Field(ge=1)]
    url: HttpUrlString
    title: str | None
    kind: Literal["packagist_metadata", "github_release", "research_citation"]
    claims: list[str]


TerminalState = Literal["completed", "failed", "stream_closed", "timed_out", "cancelled", "declined"]

# Each terminal state has its own CLI exit code so scripts can tell them apart.
# 130 follows the shell convention for a process stopped by Ctrl+C (SIGINT).
EXIT_CODES: dict[TerminalState, int] = {
    "completed": 0,
    "failed": 1,
    "declined": 2,
    "stream_closed": 3,
    "timed_out": 4,
    "cancelled": 130,
}
USAGE_EXIT_CODE = 64


class AnswerError(Model):
    name: str
    message: str


# What a route hands back to answer.py. answer.py adds question, decision and timestamps.
class RouteResult(Model):
    terminal_state: TerminalState
    # True when the call completed but the answer cannot be relied on as a full answer.
    incomplete: bool
    incomplete_reasons: list[str]
    text: str
    sources: list[SourceRecord]
    error: AnswerError | None
    # Only ever a value the API itself reported. Never estimated.
    cost: None
    cost_note: str


class ApplicationAnswer(RouteResult):
    question: str
    decision: RouteDecision
    # True when a direct lookup was served from the cache. Defaults to False so
    # records written before caching existed still parse.
    cached: bool = False
    started_at: AwareDatetime
    ended_at: AwareDatetime


# eval/questions.json is camelCase JSON; these models read it as written.
class EvalModel(Model):
    model_config = ConfigDict(extra="forbid", frozen=True, alias_generator=to_camel, populate_by_name=True)


# One entry in eval/questions.json. Everything here is written before any run.
class RequiredElement(EvalModel):
    id: Annotated[str, StringConstraints(pattern=r"^[a-z0-9-]+$")]
    # What a reviewer checks for in the answer.
    check: NonEmpty
    # The official page where the ground truth for this element lives.
    source: HttpUrlString


class EvalQuestion(EvalModel):
    id: Annotated[str, StringConstraints(pattern=r"^q\d{2}$")]
    question: NonEmpty
    expected_route: Literal["direct", "research", "decline"]
    # "declined" covers both the decline route and research questions refused before any call.
    expected_outcome: Literal["answered", "declined", "incomplete"]
    required_elements: list[RequiredElement]
    official_sources: Annotated[list[HttpUrlString], Field(min_length=1)]
    freshness: NonEmpty
    ground_truth_checked_on: Annotated[str, StringConstraints(pattern=r"^\d{4}-\d{2}-\d{2}$")]
    # Anything the author could not ground in an official source, for a human to resolve.
    flags: list[str]
    # Decisions about the question, recorded once a flag is resolved.
    notes: list[str]


def _unique_ids(questions: list[EvalQuestion]) -> list[EvalQuestion]:
    if len({q.id for q in questions}) != len(questions):
        raise ValueError("Question IDs must be unique")
    return questions


EvalQuestionSet: TypeAdapter[list[EvalQuestion]] = TypeAdapter(
    Annotated[list[EvalQuestion], Field(min_length=20, max_length=20), AfterValidator(_unique_ids)]
)


# One file per question per evaluation run, under runs/<run-id>/.
class RunRecord(ApplicationAnswer):
    # Optional so run records written before distinct terminal states existed still
    # parse. In those records None means no terminal event was seen.
    terminal_state: TerminalState | None  # type: ignore[assignment]
    run_id: NonEmpty
    question_id: Annotated[str, StringConstraints(pattern=r"^q\d{2}$")]
    strategy: Literal["routed", "demo"]
    expected_route: Literal["direct", "research", "decline"]
    duration_ms: Annotated[int, Field(ge=0)]


class RunManifest(Model):
    model_config = ConfigDict(extra="forbid", frozen=False)
    run_id: NonEmpty
    strategy: Literal["routed", "demo"]
    research_mode: Literal["fast", "balanced"]
    started_at: AwareDatetime
    ended_at: AwareDatetime | None
    git_commit: str
    git_dirty: bool
    python: str
    os: str
    packages: dict[str, str]
    github_token_set: bool
    question_order: list[str]


# A recorded or constructed SSE stream used to replay provider behaviour in tests.
class ReplayEvent(Model):
    event: str
    data: dict[str, object]


class ReplayFixture(Model):
    # Where the events came from: recorded from a live call, or derived/constructed and how.
    provenance: NonEmpty
    recorded_at: AwareDatetime
    events: list[ReplayEvent]
