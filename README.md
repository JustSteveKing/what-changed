# what-changed

A "what changed?" answerer for PHP and Laravel packages, taken from a naive demo to something closer to production, with the evidence of what happened along the way.

Ask something like "What changed in the latest Laravel release that affects queue workers?" and get back an answer with an ordered source record you can inspect. Questions are routed by fixed rules:

- **direct**: one structured lookup answers it (Packagist or the GitHub releases API). No model involved.
- **research**: several sources need reading and reconciling. One [Tabstack](https://tabstack.ai) Research call.
- **decline**: opinion questions, questions about unreleased versions, and questions about packages it does not cover.

This repository is the companion to an article. The code is written to be read and quoted, so it favours explicit types and plain control flow.

## Scope

Everything measured here comes from three evaluation runs of 20 questions on one day in October 2026. That is a small, dated sample. Nothing in this repository is a claim about typical latency, reliability or answer quality beyond those runs, and it makes no comparison with any other provider or approach.

## Quick start

Requires [uv](https://docs.astral.sh/uv/). uv installs the right Python (3.13) for you.

```sh
make install     # Python 3.13 and the locked dependencies
make check       # mypy --strict and the test suite; no network, no credits
```

Ask a question:

```sh
export TABSTACK_API_KEY=...        # needed for research questions
make ask Q="What is the latest stable version of livewire/livewire?"
```

Run `make` on its own to list every target.

## Costs

Targets marked `[paid]` in `make help` call the Tabstack Research API and spend credits: `demo`, `baseline`, `baseline-balanced`, `rerun` and `fixture`. `ask` spends credits only when a question is routed to research. Tabstack does not report cost in its API responses; spend is shown in the Tabstack console. See [pricing](https://docs.tabstack.ai/pricing/).

The tests never call the network. Provider behaviour is replayed from recorded fixtures through a local server.

## Configuration

Everything comes from the environment.

| Variable | Default | Purpose |
| --- | --- | --- |
| `TABSTACK_API_KEY` | none | Tabstack API key. Read by the SDK; never written to disk |
| `TABSTACK_RESEARCH_MODE` | `fast` | `fast` or `balanced` |
| `GITHUB_TOKEN` | none | Optional; raises the GitHub API rate limit from 60 to 5000 requests an hour |
| `PACKAGIST_MAILTO` | none | Contact address sent in the User-Agent, as Packagist asks |
| `DIRECT_TIMEOUT_MS` | `10000` | Deadline per Packagist or GitHub attempt |
| `DIRECT_MAX_ATTEMPTS` | `3` | Attempts for direct lookups (research is never retried) |
| `DIRECT_RETRY_BASE_MS` | `250` | Base delay for exponential backoff |
| `DIRECT_CACHE_TTL_MS` | `60000` | In-process cache for direct lookups; `0` turns it off |
| `RESEARCH_TIMEOUT_MS` | `300000` | Deadline for a whole research call |
| `ANSWER_STORE_DIR` | `runs/answers` | Where every answer is stored; `off` to disable |
| `REQUEST_LOG_FILE` | `runs/requests.jsonl` | JSON-lines request log; `off` to disable |

The CLI exits with a distinct code per terminal state: `completed` 0, `failed` 1, `declined` 2, `stream_closed` 3, `timed_out` 4, `cancelled` 130. Ctrl+C cancels an in-flight call.

## Layout

```
src/demo.py               the naive demo (tag: demo)
src/what_changed/         the feature: router, routes, answer contract, CLI
eval/questions.json       the 20-question evaluation set, with sources and freshness notes
eval/                     runner, deterministic scorer, fixture recorder, draft-scoring validator
runs/                     one directory per evaluation run
tests/                    pytest suite and replay fixtures
docs/VERIFIED.md          every external API shape, where it was checked and when
docs/EVIDENCE.md          environment, runs and their summaries
docs/CHECKLIST.md         production checklist for this feature
```

## Reading the history

The `demo` tag is the naive version. Each production change after it is one commit: deadlines, terminal states, cancellation, stored source records, request logging, retries for direct lookups only, and caching. `git log --reverse demo..` walks through them in order.

## Licence

MIT. See [LICENSE](LICENSE).
