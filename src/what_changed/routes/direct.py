import re
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict

from what_changed.config import Config
from what_changed.contract import DirectLookup, RouteResult, SourceRecord

NO_COST_NOTE = "Public Packagist and GitHub endpoints; no cost is reported."


# Only the fields this route reads. Packagist and GitHub send many more.
class PackagistVersion(BaseModel):
    model_config = ConfigDict(extra="ignore")
    version: str
    version_normalized: str
    time: str | None = None


class GitHubRelease(BaseModel):
    model_config = ConfigDict(extra="ignore")
    tag_name: str
    name: str | None
    body: str | None
    html_url: str
    published_at: str | None


# The p2 format is minified: each entry only carries the fields that changed from the
# previous one, and "__unset" removes a field. This mirrors Composer's own
# MetadataMinifier::expand (github.com/composer/metadata-minifier).
def expand_minified(versions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    expanded: list[dict[str, Any]] = []
    previous: dict[str, Any] = {}
    for entry in versions:
        current = dict(previous)
        for key, value in entry.items():
            if value == "__unset":
                current.pop(key, None)
            else:
                current[key] = value
        expanded.append(current)
        previous = current
    return expanded


# Normalised stable versions look like "4.4.7.0". Anything with a suffix
# ("4.0.0.0-beta6") or a dev prefix is not stable.
def is_stable(version_normalized: str) -> bool:
    return re.fullmatch(r"\d+(\.\d+)*", version_normalized) is not None


def version_key(version_normalized: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version_normalized.split("."))


def packagist_url(package: str) -> str:
    return f"https://repo.packagist.org/p2/{package}.json"


async def fetch_packagist_versions(package: str, config: Config) -> list[PackagistVersion]:
    async with httpx.AsyncClient() as client:
        response = await client.get(packagist_url(package), headers={"User-Agent": config.user_agent})
    if response.status_code != 200:
        raise RuntimeError(f"Packagist ({package}) returned HTTP {response.status_code}")
    versions = response.json()["packages"].get(package)
    if versions is None:
        raise RuntimeError(f"Packagist response did not include {package}")
    return [PackagistVersion.model_validate(v) for v in expand_minified(versions)]


def latest_stable(versions: list[PackagistVersion]) -> PackagistVersion | None:
    stable = [v for v in versions if is_stable(v.version_normalized)]
    return max(stable, key=lambda v: version_key(v.version_normalized), default=None)


async def packagist_latest_stable(package: str, config: Config) -> RouteResult:
    latest = latest_stable(await fetch_packagist_versions(package, config))
    source_title = f"Packagist metadata for {package}"
    if latest is None:
        return RouteResult(
            terminal_state="completed",
            incomplete=True,
            incomplete_reasons=["Packagist lists no stable version for this package."],
            text=f"Packagist lists no stable version of {package}.",
            sources=[SourceRecord(position=1, url=packagist_url(package), title=source_title, kind="packagist_metadata", claims=[])],
            error=None,
            cost=None,
            cost_note=NO_COST_NOTE,
        )

    released = f", released {latest.time}" if latest.time else ""
    claim = f"Latest stable version of {package} is {latest.version}{released}."
    return RouteResult(
        terminal_state="completed",
        incomplete=False,
        incomplete_reasons=[],
        text=f"The latest stable version of {package} on Packagist is {latest.version}{released}.",
        sources=[SourceRecord(position=1, url=packagist_url(package), title=source_title, kind="packagist_metadata", claims=[claim])],
        error=None,
        cost=None,
        cost_note=NO_COST_NOTE,
    )


async def github_latest_release(repo: str, config: Config) -> RouteResult:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2026-03-10",
        "User-Agent": config.user_agent,
    }
    if config.github_token:
        headers["Authorization"] = f"Bearer {config.github_token}"

    async with httpx.AsyncClient() as client:
        response = await client.get(f"https://api.github.com/repos/{repo}/releases/latest", headers=headers)
    if response.status_code != 200:
        raise RuntimeError(f"GitHub ({repo} latest release) returned HTTP {response.status_code}")
    release = GitHubRelease.model_validate(response.json())

    published = f", published {release.published_at}" if release.published_at else ""
    notes = f"\n\nRelease notes:\n\n{release.body}" if release.body else ""
    return RouteResult(
        terminal_state="completed",
        incomplete=False,
        incomplete_reasons=[],
        text=f"The latest GitHub release of {repo} is {release.tag_name}{published}.{notes}",
        sources=[
            SourceRecord(
                position=1,
                url=release.html_url,
                title=release.name or release.tag_name,
                kind="github_release",
                claims=[f"Latest release of {repo} is {release.tag_name}{published}."],
            )
        ],
        error=None,
        cost=None,
        cost_note=NO_COST_NOTE,
    )


async def run_direct(lookup: DirectLookup, config: Config) -> RouteResult:
    if lookup.kind == "packagist_latest_stable":
        return await packagist_latest_stable(lookup.package, config)
    return await github_latest_release(lookup.repo, config)
