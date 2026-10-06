import re
from dataclasses import dataclass


from what_changed.contract import (
    PACKAGE_NAME_PATTERN,
    DeclineDecision,
    DirectDecision,
    GitHubLatestRelease,
    PackagistLatestStable,
    ResearchDecision,
    RouteDecision,
    VersionMention,
)

# Deterministic, rule-based routing. No model, no network. The rules run in order
# and the first one that matches decides the route.


@dataclass(frozen=True)
class KnownPackage:
    package: str
    repo: str
    aliases: tuple[str, ...]


# The GitHub repo is listed explicitly because it does not always match the Packagist
# name: filament/filament's Packagist source is the filamentphp/panels subsplit, but
# its GitHub releases are published on filamentphp/filament.
KNOWN_PACKAGES = (
    KnownPackage("laravel/framework", "laravel/framework", ("laravel framework", "laravel")),
    KnownPackage("livewire/livewire", "livewire/livewire", ("livewire",)),
    KnownPackage("pestphp/pest", "pestphp/pest", ("pestphp", "pest")),
    KnownPackage("filament/filament", "filamentphp/filament", ("filament",)),
    KnownPackage("inertiajs/inertia-laravel", "inertiajs/inertia-laravel", ("inertia",)),
)

OPINION = re.compile(r"\b(should i|should we|which is better|better than|recommend\w*|vs\.?|versus|compare\w*|comparison)\b")
FUTURE = re.compile(r"\b(upcoming|roadmap|unreleased|planned|when will|be released|next (major|minor|release|version))\b")
CHANGE = re.compile(
    r"\b(chang\w*|affect\w*|break\w*|upgrad\w*|migrat\w*|deprecat\w*|remov\w*|differen\w*|behaviou?r\w*"
    r"|impact\w*|fix\w*|introduc\w*|added|new in|what'?s new)\b"
)
LATEST = re.compile(r"\b(latest|current|newest|most recent)\b")
VERSION_WORD = re.compile(r"\b(version|release|tag)\b")
RELEASE_DATE = re.compile(r"\bwhen was\b.*\b(released|published|tagged)\b")
RELEASE_NOTES = re.compile(r"\brelease notes\b")
EXPLICIT_NAME = re.compile(r"[a-z0-9][a-z0-9_.-]*/[a-z0-9][a-z0-9_.-]*")
VERSION_AFTER = re.compile(r"^\s+(?:version\s+)?v?(\d+(?:\.\d+){0,2})(?:\.x)?\b")



def normalise(question: str) -> str:
    return re.sub(r"\s+", " ", question.strip().lower())


@dataclass(frozen=True)
class PackageMention:
    package: str
    repo: str | None
    term: str
    index: int


def _blank(text: str, index: int, length: int) -> str:
    return text[:index] + " " * length + text[index + length :]


# Finds packages named explicitly ("livewire/livewire") or by a known alias ("Livewire").
def find_packages(text: str) -> list[PackageMention]:
    mentions: list[PackageMention] = []

    for match in EXPLICIT_NAME.finditer(text):
        name = match.group(0).rstrip(".")
        if not re.fullmatch(PACKAGE_NAME_PATTERN, name):
            continue
        known = next((p for p in KNOWN_PACKAGES if p.package == name), None)
        mentions.append(PackageMention(name, known.repo if known else None, name, match.start()))

    # Blank out explicit names so "livewire/livewire" is not also matched by alias.
    rest = text
    for mention in mentions:
        rest = _blank(rest, mention.index, len(mention.term))

    for known in KNOWN_PACKAGES:
        for alias in known.aliases:
            found = re.search(rf"(?<![\w/-]){re.escape(alias)}(?![\w/-])", rest)
            if not found:
                continue
            mentions.append(PackageMention(known.package, known.repo, alias, found.start()))
            rest = _blank(rest, found.start(), len(alias))
            break

    # "Laravel Livewire" and "Laravel Pest" name one package, not two.
    laravel = next((m for m in mentions if m.package == "laravel/framework" and m.term == "laravel"), None)
    if laravel and any(m is not laravel and m.index == laravel.index + len("laravel ") for m in mentions):
        mentions.remove(laravel)

    unique: dict[str, PackageMention] = {}
    for mention in sorted(mentions, key=lambda m: m.index):
        unique.setdefault(mention.package, mention)
    return list(unique.values())


# A version written straight after a package mention: "Laravel 13", "livewire v4.2", "Pest 4.x".
def find_version(text: str, mentions: list[PackageMention]) -> VersionMention | None:
    for mention in mentions:
        found = VERSION_AFTER.match(text[mention.index + len(mention.term) :])
        if found:
            return VersionMention(package=mention.package, version=found.group(1))
    return None


def route(raw_question: str) -> RouteDecision:
    question = raw_question.strip()
    if not 1 <= len(question) <= 2000:
        return DeclineDecision(route="decline", reason="The question is empty or longer than 2000 characters.")

    text = normalise(question)
    mentions = find_packages(text)

    if not mentions:
        return DeclineDecision(route="decline", reason="No supported PHP package was identified in the question.")
    if OPINION.search(text):
        return DeclineDecision(route="decline", reason="The question asks for an opinion or comparison, not what changed.")
    if FUTURE.search(text):
        return DeclineDecision(route="decline", reason="The question asks about a future or unreleased version.")

    packages = [m.package for m in mentions]
    version_mentioned = find_version(text, mentions)
    asks_change = bool(CHANGE.search(text))

    if len(mentions) > 1:
        return ResearchDecision(
            route="research",
            reason="The question involves more than one package.",
            packages=packages,
            version_mentioned=version_mentioned,
        )

    only = mentions[0]
    asks_latest_version = bool(LATEST.search(text) and VERSION_WORD.search(text))
    asks_release_date = bool(RELEASE_DATE.search(text) and LATEST.search(text))
    asks_release_notes = bool(RELEASE_NOTES.search(text) and LATEST.search(text))

    if not asks_change and version_mentioned is None:
        if (asks_release_date or asks_release_notes) and only.repo is not None:
            return DirectDecision(
                route="direct",
                reason="Asks for the date or notes of the latest release of one package.",
                lookup=GitHubLatestRelease(kind="github_latest_release", package=only.package, repo=only.repo),
            )
        if asks_latest_version or asks_release_date:
            return DirectDecision(
                route="direct",
                reason="Asks for the latest version of one package.",
                lookup=PackagistLatestStable(kind="packagist_latest_stable", package=only.package),
            )

    if asks_change or version_mentioned is not None:
        return ResearchDecision(
            route="research",
            reason=(
                "Asks what changed or how a change affects code; needs several sources."
                if asks_change
                else "Asks about a specific version; needs several sources."
            ),
            packages=packages,
            version_mentioned=version_mentioned,
        )

    return DeclineDecision(route="decline", reason="No version lookup or change question was recognised.")
