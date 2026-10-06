# Verified against documentation or source

Every external API shape used in this repository is listed here with where it was checked and when. If a row says "not confirmed", the code does not rely on it.

API facts that do not depend on the SDK (Tabstack HTTP behaviour, pricing, Packagist, GitHub) were first checked on 2026-10-05 and re-checked on 2026-10-06 where noted.

## Tabstack Research (`tabstack` Python SDK 2.8.5)

SDK rows checked 2026-10-06 against `.venv/lib/python3.13/site-packages/tabstack/`.

| Question | Answer | Where checked |
| --- | --- | --- |
| SDK package | `tabstack` 2.8.5 on PyPI, "The official Python library for the tabstack API", repository `Mozilla-Ocho/tabstack-python`. Depends on `httpx`, `pydantic`, `anyio` | PyPI JSON API, 2026-10-06 |
| Methods | `Tabstack().agent.research(...)` returns `Stream[ResearchEvent]`; `AsyncTabstack().agent.research(...)` returns `AsyncStream[ResearchEvent]` | `resources/agent.py` lines 218-294 (sync), 484 onwards (async) |
| Request parameters | Keyword-only `query`, `fetch_timeout`, `mode` (`"fast"` or `"balanced"`), `nocache`, plus `timeout` per request | `resources/agent.py` `research` signature |
| API key source | `TABSTACK_API_KEY` env var, read by the client constructor; raises if missing. Base URL from `TABSTACK_BASE_URL` | `_client.py` lines 84-95, 279-290 |
| Event types | `ResearchEvent` is a pydantic union discriminated on `event`, with the same event names as the HTTP API (`start`, `planning:start/end`, ..., `complete`, `error`) | `types/research_event.py` line 843 |
| `complete` payload | `event.data.report`, `event.data.message`, `event.data.metadata`; `metadata.cited_pages` (alias `citedPages`) is optional | `types/research_event.py` lines 312-391 |
| Cited page fields | `id`, `claims` (list of str), `source_queries`, `url` required; `title`, `summary`, `relevance`, `reliability`, `depth`, `parent_url`, `full_text` optional | `types/research_event.py` lines 135-164 |
| `error` payload | `event.data.error.name`, `event.data.error.message`, optional `stack`; `event.data.message`, `timestamp`, optional `activity` | `types/research_event.py` lines 396-412 |
| Streamed `error` events | Yielded to the caller like any other event; the SDK does not raise on them | `_streaming.py` `AsyncStream.__stream__` lines 126-143 |
| Stream ending with no terminal event | The iterator simply finishes; the response is closed in a `finally` | `_streaming.py` lines 126-143 |
| Closing a stream | `AsyncStream` is an async context manager and has `close()`, both of which close the HTTP response | `_streaming.py` lines 145-162 |
| SDK default timeout | Client default `httpx.Timeout(timeout=60, connect=5.0)`. `research()` replaces it with `600` when neither the call nor the client set one | `_constants.py`; `resources/agent.py` lines 270-271 |
| What the SDK timeout covers | An `httpx.Timeout` of 600 applies to each connect, read, write and pool wait separately. For a stream, the read timeout is the longest allowed gap between chunks, so a fully silent stream fails after 600 s, but a stream that keeps sending events is not limited in total | `_constants.py`; httpx timeout semantics, https://www.python-httpx.org/advanced/timeouts/ |
| SDK automatic retries | `DEFAULT_MAX_RETRIES = 2`, initial delay 0.5 s, max 8 s; retries 408, 409, 429, 5xx and honours `x-should-retry` | `_constants.py`; `_base_client.py` `_should_retry` (around line 777) |
| Official Python example | Iterates `client.agent.research(...)`, raises on `event.event == "error"`, prints `event.data.report` and `event.data.metadata.cited_pages` on `complete` | https://docs.tabstack.ai/sdks/python/quickstart/, 2026-10-06 |

The following rows are about the HTTP API, not the SDK, and were checked on 2026-10-05:

| Question | Answer | Where checked |
| --- | --- | --- |
| `balanced` mode availability | Docs say `balanced` requires a paid plan | https://docs.tabstack.ai/guides/research/ |
| Server-side cache | `nocache` (default `false`): "Force fresh results, bypass cache". Every run here leaves it at the default | https://docs.tabstack.ai/guides/research/; https://docs.tabstack.ai/trust/data-handling/#caching |
| Terminal events | `complete` (success) and `error` (failure, "can arrive at any point as alternative terminal event") | https://docs.tabstack.ai/guides/research/ |
| Server-side timeout | "No server-side timeout exists; budget client-side timeouts" | https://docs.tabstack.ai/guides/research/ |
| `claims` in fast mode | Docs: `claims` is an empty array in fast mode | https://docs.tabstack.ai/guides/research/ |
| HTTP errors | Raised before the stream opens, as typed SDK exceptions. Body shape `{ "error": "message" }` | https://docs.tabstack.ai/production/error-reference/ |
| Cost reporting | **Not reported in any API response.** "Plans, current spend, and credit balance live in the console, not in any API response." Research fast 250 credits, balanced 350 credits (list price) | https://docs.tabstack.ai/pricing/ |
| Latency guidance | Fast "typically under 60 seconds", balanced "up to ~4 minutes". Provider guidance only | https://docs.tabstack.ai/guides/research/ |

## httpx (direct lookups)

Checked 2026-10-06.

| Question | Answer | Where checked |
| --- | --- | --- |
| Why httpx | Already installed as a dependency of the Tabstack SDK, so no extra package; async, so a whole-call deadline and cancellation can wrap it with `asyncio` | `tabstack` 2.8.5 `requires_dist` |
| Version | 0.28.1, pinned | `pyproject.toml`, `uv.lock` |
| Default timeout | `httpx.AsyncClient()` with no `timeout` argument uses `Timeout(timeout=5.0)`: 5 s for each connect, read, write and pool wait. The naive direct route relies on this default; it is a library default, not a deliberate limit | `httpx._config.DEFAULT_TIMEOUT_CONFIG` printed from the installed package; https://www.python-httpx.org/advanced/timeouts/ |

## Packagist

Checked 2026-10-05; endpoint and top-level keys re-checked 2026-10-06 (`laravel/framework` still listed v13.34.0 first).

| Question | Answer | Where checked |
| --- | --- | --- |
| Metadata endpoint | `GET https://repo.packagist.org/p2/{vendor}/{package}.json` (tagged releases), `...~dev.json` (dev branches) | https://packagist.org/apidoc |
| Response shape | Top-level keys `minified`, `packages`, `security-advisories`. `packages["vendor/name"]` is an array of versions. Minified format: the first entry is complete, later entries only carry fields that changed. `version` and `version_normalized` are present on each entry | https://packagist.org/apidoc; live response for `livewire/livewire` on 2026-10-05 |
| Version ordering | Live response listed newest first, but the docs do not promise an order. The code sorts by `version_normalized` itself rather than relying on array order | live response; not confirmed in docs |
| Pre-releases in the stable file | Not stated in the docs. Confirmed live: the non-`~dev` file includes pre-release tags (on 2026-10-05: `filament/filament` 233, `livewire/livewire` 21, `laravel/framework` 11, `inertiajs/inertia-laravel` 5, `pestphp/pest` 0). Normalised pre-release versions carry a suffix such as `4.0.0.0-beta6`, so the code treats only purely numeric `version_normalized` values as stable | live responses, 2026-10-05 |
| Minified expansion | Each entry carries only fields that changed from the previous entry; the value `"__unset"` removes a field. Confirmed live: `inertiajs/inertia-laravel` `v3.0.0-beta5` has no `time` key of its own. The code mirrors Composer's `MetadataMinifier::expand` | https://github.com/composer/metadata-minifier/blob/main/src/MetadataMinifier.php |
| Source repo vs release repo | `filament/filament` lists `source.url` `https://github.com/filamentphp/panels.git` (a subsplit), but its GitHub releases are on `filamentphp/filament`. The router therefore keeps an explicit package to repo map | live responses, 2026-10-05 |
| Package name format | `^[a-z0-9]([_.-]?[a-z0-9]+)*/[a-z0-9](([_.]\|-{1,2})?[a-z0-9]+)*$`; stabilities in order `dev`, `alpha`, `beta`, `RC`, `stable` | https://getcomposer.org/doc/04-schema.md#name |
| Etiquette | Send a `User-Agent` including a contact (`mailto=`); max 10 concurrent requests (20 for static files); `If-Modified-Since` supported | https://packagist.org/apidoc |

## GitHub releases API

Checked 2026-10-05; `X-GitHub-Api-Version: 2026-03-10` re-confirmed on 2026-10-06.

| Question | Answer | Where checked |
| --- | --- | --- |
| Latest release | `GET /repos/{owner}/{repo}/releases/latest`: "the most recent non-prerelease, non-draft release" | https://docs.github.com/en/rest/releases/releases |
| List releases | `GET /repos/{owner}/{repo}/releases?per_page=&page=` (max 100 per page) | same |
| Fields used | `tag_name`, `name`, `body`, `html_url`, `published_at`, `draft`, `prerelease` | same; live response for `laravel/framework` on 2026-10-05 |
| Headers | `Accept: application/vnd.github+json`, `X-GitHub-Api-Version: 2026-03-10`. Live response echoed `x-github-api-version-selected: 2026-03-10` | same; live response |
| Auth | Public releases readable unauthenticated. Optional `GITHUB_TOKEN` env var is sent as `Authorization: Bearer` to raise the rate limit | same |
| Latest release per repo | On 2026-10-05 `releases/latest` returned a release for `laravel/framework`, `livewire/livewire`, `pestphp/pest`, `filamentphp/filament` and `inertiajs/inertia-laravel` | live responses |
| Rate limit | Unauthenticated: 60 requests per hour (live response: `x-ratelimit-limit: 60`). Exceeded: `403` or `429` with `x-ratelimit-remaining: 0`; do not retry before `x-ratelimit-reset`. Secondary limits: honour `retry-after`, otherwise wait at least a minute, back off exponentially and give up after a fixed number of retries | https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api |

## Ground truth for eval/questions.json

Checked 2026-10-05. Every required element in `eval/questions.json` was written from these files, read as raw text, not from memory. The human-facing URLs in the question set were checked to return HTTP 200 on the same day (`laravel.com/docs/13.x/*` redirects to `laravel.com/framework/docs/13.x/*`).

| Package | Raw file read | Human-facing URL |
| --- | --- | --- |
| laravel/framework | `laravel/docs` branch `13.x`: `upgrade.md`, `releases.md`; `laravel/framework` branch `13.x`: `composer.json`; GitHub release `v13.34.0` body | https://laravel.com/docs/13.x/upgrade, https://laravel.com/docs/13.x/releases |
| livewire/livewire | `livewire/livewire` branch `main`: `docs/upgrading.md`; GitHub release `v4.4.7` body; compare `v4.4.6...v4.4.7` (2 commits) | https://livewire.laravel.com/docs/4.x/upgrading |
| pestphp/pest | `pestphp/docs` branch `5.x`: `upgrade-guide.md` (branch `master` only covers up to 3.x) | https://pestphp.com/docs/upgrade-guide |
| filament/filament | `filamentphp/filament` branch `5.x`: `docs/14-upgrade-guide.md`, `packages/support/composer.json`; tag `v5.0.0`: `packages/support/composer.json` | https://filamentphp.com/docs/5.x/upgrade-guide |
| inertiajs/inertia-laravel | `inertiajs/docs` branch `main`: `v3/getting-started/upgrade-guide.mdx`; GitHub releases `v3.0.0` and `v3.5.1` bodies | https://inertiajs.com/docs/v3/getting-started/upgrade-guide |

Observed while reading: the GitHub release `livewire/livewire` `v4.4.7` has a body containing only a "Full Changelog" compare link, so there are no itemised official release notes. q20 relies on this deliberately to test an incomplete answer; its ground truth is the compare view, which lists two commits: "Resolve contextual attribute parameters from the container" and "Build assets for v4.4.7".
