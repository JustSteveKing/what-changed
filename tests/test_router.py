from pydantic import TypeAdapter

from what_changed.contract import (
    DeclineDecision,
    DirectDecision,
    GitHubLatestRelease,
    PackagistLatestStable,
    ResearchDecision,
    RouteDecision,
    VersionMention,
)
from what_changed.router import find_packages, find_version, normalise, route


def direct_lookup(question: str) -> PackagistLatestStable | GitHubLatestRelease:
    decision = route(question)
    assert isinstance(decision, DirectDecision), decision
    return decision.lookup


def research(question: str) -> ResearchDecision:
    decision = route(question)
    assert isinstance(decision, ResearchDecision), decision
    return decision


# Direct route


def test_latest_stable_version_goes_to_packagist() -> None:
    assert route("What is the latest stable version of livewire/livewire?") == DirectDecision(
        route="direct",
        reason="Asks for the latest version of one package.",
        lookup=PackagistLatestStable(kind="packagist_latest_stable", package="livewire/livewire"),
    )


def test_package_recognised_by_alias() -> None:
    assert direct_lookup("What's the current version of Pest?") == PackagistLatestStable(kind="packagist_latest_stable", package="pestphp/pest")


def test_latest_release_date_goes_to_github() -> None:
    assert direct_lookup("When was the latest Filament release published?") == GitHubLatestRelease(
        kind="github_latest_release", package="filament/filament", repo="filamentphp/filament"
    )


def test_latest_release_notes_go_to_github() -> None:
    assert direct_lookup("Show me the release notes for the latest Inertia release").kind == "github_latest_release"


def test_unknown_package_uses_packagist_because_no_repo_is_known() -> None:
    assert direct_lookup("When was the latest spatie/laravel-data release published?") == PackagistLatestStable(
        kind="packagist_latest_stable", package="spatie/laravel-data"
    )


def test_laravel_livewire_is_one_package() -> None:
    assert direct_lookup("What is the newest Laravel Livewire version?") == PackagistLatestStable(
        kind="packagist_latest_stable", package="livewire/livewire"
    )


# Research route


def test_change_question_goes_to_research() -> None:
    assert route("What changed in the latest Laravel release that affects queue workers?") == ResearchDecision(
        route="research",
        reason="Asks what changed or how a change affects code; needs several sources.",
        packages=["laravel/framework"],
        version_mentioned=None,
    )


def test_version_lookup_mixed_with_change_question_prefers_research() -> None:
    research("What is the latest Livewire version and what does it break?")


def test_records_version_after_package_name() -> None:
    assert research("What are the breaking changes when upgrading to Pest 4?").version_mentioned == VersionMention(package="pestphp/pest", version="4")


def test_records_version_with_v_prefix_and_x_suffix() -> None:
    assert research("How does validation behave in Laravel v12.x?").version_mentioned == VersionMention(package="laravel/framework", version="12")


def test_version_specific_question_without_change_words_goes_to_research() -> None:
    assert research("Tell me about Filament 4.2").version_mentioned == VersionMention(package="filament/filament", version="4.2")


def test_two_packages_go_to_research() -> None:
    assert research("Does Filament 5 work with Livewire 4?").packages == ["filament/filament", "livewire/livewire"]


def test_british_and_american_spelling_of_behaviour() -> None:
    research("Did Inertia change form behaviour?")
    research("Did Inertia change form behavior?")


def test_php_version_is_not_a_package_version() -> None:
    assert research("Which Laravel changes affect PHP 8.5 support?").version_mentioned is None


def test_will_alone_is_not_a_future_question() -> None:
    research("Will my queue workers break when upgrading Laravel?")


# Decline route


def test_declines_empty_question() -> None:
    assert route("   ").route == "decline"


def test_declines_question_with_no_supported_package() -> None:
    assert route("What changed in the latest Django release?") == DeclineDecision(
        route="decline", reason="No supported PHP package was identified in the question."
    )


def test_declines_comparison() -> None:
    assert route("Is Livewire better than Inertia?").route == "decline"
    assert route("Livewire vs Inertia for a new app").route == "decline"


def test_declines_unreleased_version_questions() -> None:
    assert route("What will change in the next major Laravel release?").route == "decline"
    assert route("When will Pest 6 be released?").route == "decline"


def test_declines_package_with_no_recognisable_intent() -> None:
    assert route("Tell me about Livewire").route == "decline"


def test_declines_should_i_even_when_it_mentions_upgrading() -> None:
    assert route("Should I upgrade to Laravel 13?").route == "decline"


# Helpers


def test_normalises_case_and_whitespace() -> None:
    assert normalise("  What   IS\nLivewire  ") == "what is livewire"


def test_alias_does_not_match_inside_longer_word_or_package_name() -> None:
    assert [m.package for m in find_packages(normalise("inertiajs/inertia-laravel latest version"))] == ["inertiajs/inertia-laravel"]
    assert find_packages("pesticide") == []


def test_no_version_when_none_follows_package() -> None:
    text = normalise("latest laravel release")
    assert find_version(text, find_packages(text)) is None


def test_always_returns_a_decision_that_passes_the_schema() -> None:
    adapter: TypeAdapter[RouteDecision] = TypeAdapter(RouteDecision)
    for question in ["", "livewire", "What changed in Pest 4?", "latest version of filament/filament", "x" * 3000]:
        adapter.validate_python(route(question).model_dump())
