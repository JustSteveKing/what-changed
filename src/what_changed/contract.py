from typing import Annotated, Literal, Union
from urllib.parse import urlparse

from pydantic import AfterValidator, AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints

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


# None means the call ended without any terminal state being observed.
TerminalState = Literal["completed", "failed", "declined"]


class AnswerError(Model):
    name: str
    message: str


# What a route hands back to answer.py. answer.py adds question, decision and timestamps.
class RouteResult(Model):
    terminal_state: TerminalState | None
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
    started_at: AwareDatetime
    ended_at: AwareDatetime
