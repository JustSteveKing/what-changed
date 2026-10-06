# Production checklist: "what changed?" answerer

Filled in on 2026-10-06 at the state measured in `docs/EVIDENCE.md`. Each item is marked `pass`, `fail` or `cannot verify from outside`. "From outside" means it depends on something only Tabstack (or the account owner's console) can show.

Scope: the evidence is three evaluation runs of 20 questions each on one morning, plus the test suite. That is a small, dated sample. A `pass` below means the item held in that evidence, not that it always holds.

## Quality

| Item | Status | Evidence |
| --- | --- | --- |
| Routing is deterministic, rule-based and unit tested | pass | `src/what_changed/router.py`; `tests/test_router.py` (25 tests) |
| Every question took its expected route | pass | Re-run: route matched 20 / 20 (baseline 13 / 20) |
| Questions about unreleased versions, the future, or opinions are declined without a research call | pass | Re-run q17, q18, q19 declined; q17 checked against Packagist first |
| Every non-declined answer carries an ordered source record | pass | Re-run: 17 / 17 non-declined answers have sources; positions are 1..n (`tests/test_store.py`, `tests/test_replay.py`) |
| Every cited source carries at least one claim | fail | Re-run: 15 / 17 non-declined answers (q08, q12 each have one source with no claims). Fast mode returns no claims at all (`docs/VERIFIED.md`) |
| Research answers cite official sources | fail | Not controlled by this application. Non-official domains were cited in every run, e.g. re-run q06 cites `releasebot.io`, `phpeveryday.com` and `ortamarco.me` |
| The application detects an answer that is thin or incomplete | fail | q20 ("latest Livewire release") was not marked incomplete in any run; `incomplete` only fires on an empty report or no sources |
| Answer quality is scored against official sources | pass | All 132 required elements in the three runs are rated in `scoring.csv`. Ratings were drafted by a model with a verbatim quote from the answer for each, checked by `eval/score_draft.py`; see `docs/EVIDENCE.md` |
| Every rating was checked by a person | fail | The owner reviewed the 21 judgement calls (all confirmed); the other 111 ratings were accepted as drafted. `reviewer_notes` in each `scoring.csv` marks which is which |
| The evaluation set records its sources and when each answer can change | pass | `eval/questions.json` (schema-validated, `freshness` and `groundTruthCheckedOn` on every question) |
| Direct answers match the source of truth at run time | pass | Re-run q01 to q05 report v4.4.7, v5.3.0, v5.9.0, v3.5.1 and v13.34.0, the values Packagist and GitHub returned that day |

## Latency

| Item | Status | Evidence |
| --- | --- | --- |
| Every outbound call has a whole-call deadline | pass | `src/what_changed/deadline.py`; `tests/test_timeout.py` (a research stream left open by a local server is cut off at the limit) |
| Deadlines are configurable | pass | `DIRECT_TIMEOUT_MS` (default 10000), `RESEARCH_TIMEOUT_MS` (default 300000) |
| Research calls finished inside the configured deadline | pass | 32 balanced-mode research calls across two runs: max 253883 ms against a 300000 ms limit. The margin is about 46 s, so this limit may need raising if balanced calls run longer |
| Direct lookups are fast | pass | Re-run: 5 direct lookups, max 350 ms |
| A stalled stream is detected before the overall deadline | fail | Only a total deadline exists. The SDK's 600 s read timeout is longer than that deadline, so it never applies. The Research guide recommends watching for stream silence; no idle timer is implemented |
| Provider latency commitment | cannot verify from outside | The Research guide gives "typically" figures only ([guide](https://docs.tabstack.ai/guides/research/)); no commitment was found on the pages read |

## Cost

| Item | Status | Evidence |
| --- | --- | --- |
| Cost of each request is recorded | cannot verify from outside | The API reports no cost: "Plans, current spend, and credit balance live in the console, not in any API response" ([pricing](https://docs.tabstack.ai/pricing/)). Records and logs carry `cost: null` |
| Billed research calls are never retried automatically | pass | `AsyncTabstack(max_retries=0)`; `tests/test_retry.py` counts one request on a 500, and fails (3 requests) if the SDK default is restored |
| Questions a single lookup can answer do not use research | pass | Re-run: 12 research calls for 20 questions (baseline 20) |
| A spend limit or budget guard exists in the application | fail | None implemented |
| Credits charged match the published price | cannot verify from outside | Published per-call prices are on the [pricing page](https://docs.tabstack.ai/pricing/); actual charges are only in the console |

## Failure handling

| Item | Status | Evidence |
| --- | --- | --- |
| Distinct terminal states, each with its own exit code | pass | `completed` 0, `failed` 1, `declined` 2, `stream_closed` 3, `timed_out` 4, `cancelled` 130; `tests/test_terminal_states.py` |
| A stream that ends without a terminal event is detected | pass | `tests/test_replay.py` with `research-stream-closed.json` (derived from a recorded stream) |
| A streamed error is surfaced verbatim | pass | `tests/test_replay.py` with `research-error.json`. The error event is constructed from the SDK type; a real streamed error was never observed |
| Timeouts produce `timed_out`, not a hang or a generic failure | pass | `tests/test_timeout.py` |
| Ctrl+C cancels an in-flight call cleanly | pass | `tests/test_cancel.py` sends SIGINT to the real CLI process; exit code 130, state `cancelled` |
| Direct lookups retry transient failures, boundedly | pass | `tests/test_retry.py`: 503 retried, 404 not retried, gives up after 3 attempts |
| GitHub rate-limit guidance is honoured | pass | Exhausted primary limit and `Retry-After` beyond 5 s are not retried (`tests/test_retry.py`), per [GitHub's rate-limit docs](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api) |
| Tabstack's per-minute budget is read proactively | fail | `X-RateLimit-Remaining` is not read; a research 429 becomes `failed`. See [rate limits](https://docs.tabstack.ai/production/rate-limits/#read-the-headers-never-hit-the-wall) |
| Failure paths seen against the live API | cannot verify from outside | No live run produced a failure, timeout or closed stream; these paths are exercised only by local tests and fixtures |

## Privacy

Statements about Tabstack's handling are quoted from its documentation, not paraphrased. Pages read on 2026-10-05.

| Item | Status | Evidence |
| --- | --- | --- |
| Use of research queries for model training is documented | pass | "Your requests and the content Tabstack processes for you are not used to train models." ([data handling](https://docs.tabstack.ai/trust/data-handling/#never-trained-on-private-by-default-built-by-mozilla)) |
| Retention of research queries and answers is documented | pass | The privacy policy is treated as the source of truth; the data handling page itself says "The canonical privacy policy is at https://tabstack.ai/legal/privacy". It says: "We store history (including your content and/or Outputs) for 90 days or unless you delete it." ([privacy policy](https://tabstack.ai/legal/privacy), last updated 2026-09-16) |
| The two official documents agree on retention | fail | They do not. The [data handling page](https://docs.tabstack.ai/trust/data-handling/#what-is-stored) says: "The payloads (the target URL, request parameters, response data, and extracted output) are not stored by default. They are retained for 90 days only when an organization opts into detailed data collection." This repository follows the privacy policy (row above) because the data handling page names it as canonical; a reader relying on the data handling page alone would get a different answer |
| Request metadata retention is documented | pass | "This is always recorded, on every plan." ([the path a request takes](https://docs.tabstack.ai/trust/data-handling/#the-path-a-request-takes)) |
| Processing by third-party model providers is documented | pass | "For endpoints that apply a model (/extract/json, /generate/json, /research, /automate), the content being processed and the instructions you supplied are sent to a contracted model provider" ([the path a request takes](https://docs.tabstack.ai/trust/data-handling/#the-path-a-request-takes)); provider list in the [privacy policy](https://tabstack.ai/legal/privacy#information-we-share) |
| Which model provider processes a given research call | cannot verify from outside | Not stated per request in any response or on the pages read |
| Cross-account caching is documented | pass | "Cached page content can be served across accounts. Pass nocache: true when you need a fetch that bypasses this shared cache." ([caching](https://docs.tabstack.ai/trust/data-handling/#caching)). All runs here used the default `nocache: false` |
| This account's "detailed data collection" setting | cannot verify from outside | An organisation setting visible only in the Tabstack console |
| Retention and access controls work as documented | cannot verify from outside | See [security](https://docs.tabstack.ai/trust/security/#access-controls) |
| Third-party security certifications | fail | "SOC 2 and ISO 27001 are not currently held." ([what this does not cover](https://docs.tabstack.ai/trust/data-handling/#what-this-does-not-cover)) |
| Data location | cannot verify from outside | See [international transfers](https://tabstack.ai/legal/privacy#international-transfers); no per-request region is reported |
| This application keeps question text out of logs | pass | `src/what_changed/log.py`; `tests/test_log.py` asserts the question is absent |
| This application has a retention limit for stored answers | fail | `runs/answers/` keeps every answer, including the question, with no expiry (it is git-ignored, but never pruned) |
| API keys are never written to disk | pass | Read from the environment only; `tests/test_key_scan.py` scans `runs/` and `tests/fixtures/` for `TABSTACK_API_KEY` and `GITHUB_TOKEN` |

## Ownership

| Item | Status | Evidence |
| --- | --- | --- |
| Dependencies pinned to exact versions with a lockfile | pass | `pyproject.toml` (exact `==` pins), `uv.lock` |
| External API shapes recorded with source and date | pass | `docs/VERIFIED.md` |
| A named owner for the feature | fail | No owner recorded in the repository |
| Someone re-checks the evaluation set when answers go stale | fail | Freshness notes exist (q06 and q20 expire with the next Laravel or Livewire release) but no one and no schedule is assigned |
| Provider changes are monitored | fail | Nothing watches the [Tabstack changelog](https://docs.tabstack.ai/changelog/) or SDK releases |
| Secret rotation has a procedure | fail | Not documented here. Tabstack: "API keys can be set to expire; rotation is manual today." ([security](https://docs.tabstack.ai/trust/security/#access-controls)) |
| Vulnerability reporting route for the provider is known | pass | [Reporting a vulnerability](https://docs.tabstack.ai/trust/security/#reporting-a-vulnerability) |

## Sources checked for this checklist

Read on 2026-10-05:

- https://docs.tabstack.ai/trust/data-handling/
- https://docs.tabstack.ai/trust/security/
- https://docs.tabstack.ai/production/rate-limits/
- https://docs.tabstack.ai/pricing/
- https://docs.tabstack.ai/guides/research/
- https://tabstack.ai/legal/privacy (last updated 2026-09-16)
