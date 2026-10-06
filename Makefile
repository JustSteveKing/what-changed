# Run `make` or `make help` to see the targets.
#
# Targets marked [paid] call the Tabstack Research API and spend credits.
# They need TABSTACK_API_KEY in the environment. GITHUB_TOKEN is optional.
# Research mode comes from TABSTACK_RESEARCH_MODE (fast or balanced, default fast).

.DEFAULT_GOAL := help
.PHONY: help install test typecheck check ask demo baseline baseline-balanced rerun score draft fixture clean

UV ?= uv

help: ## Show this help
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "} {printf "  %-18s %s\n", $$1, $$2}'

install: ## Install Python 3.13 and the locked dependencies
	$(UV) python install 3.13
	$(UV) sync --frozen

test: ## Run the test suite (no network, no credits)
	$(UV) run pytest -q

typecheck: ## Run mypy in strict mode
	$(UV) run mypy src tests eval

check: typecheck test ## Typecheck and test

ask: require-key ## [paid if routed to research] Ask one question: make ask Q="..."
	@test -n "$(Q)" || (echo 'Usage: make ask Q="your question"' && exit 64)
	@$(UV) run what-changed "$(Q)" || echo "(exit code $$?: each terminal state has its own code, see EXIT_CODES in src/what_changed/contract.py)"

demo: require-key ## [paid] Run the naive demo: make demo Q="..."
	@test -n "$(Q)" || (echo 'Usage: make demo Q="your question"' && exit 64)
	$(UV) run src/demo.py "$(Q)"

baseline: require-key ## [paid] 20 questions through the demo behaviour, fast mode
	TABSTACK_RESEARCH_MODE=fast $(UV) run python -m eval.run demo baseline-demo --first q06,q20

baseline-balanced: require-key ## [paid] 20 questions through the demo behaviour, balanced mode (about 45 min)
	TABSTACK_RESEARCH_MODE=balanced $(UV) run python -m eval.run demo baseline-demo-balanced --first q06,q20

rerun: require-key ## [paid] 20 questions through the router, balanced mode (about 25 min)
	TABSTACK_RESEARCH_MODE=balanced $(UV) run python -m eval.run routed rerun-routed-balanced --first q06,q20

score: ## Deterministic checks and blank scoring sheet: make score RUN=<run-id> (default: newest run)
	$(UV) run python -m eval.score $(or $(RUN),$(shell ls -d runs/20*/ | sort | tail -1 | xargs basename))

draft: ## Validate eval/scoring-draft-model.json and write scoring-draft-model.csv per run
	$(UV) run python -m eval.score_draft

fixture: require-key ## [paid] Record a live stream for replay tests: make fixture Q="..." OUT=tests/fixtures/x.json
	@test -n "$(Q)" -a -n "$(OUT)" || (echo 'Usage: make fixture Q="question" OUT=tests/fixtures/name.json' && exit 64)
	$(UV) run python -m eval.record_fixture "$(Q)" "$(OUT)"

clean: ## Remove local answers, request log and caches (keeps committed runs)
	rm -rf runs/answers runs/requests.jsonl .pytest_cache .mypy_cache
	find . -name __pycache__ -type d -not -path "./.venv/*" -prune -exec rm -rf {} +

.PHONY: require-key
require-key:
	@test -n "$$TABSTACK_API_KEY" || (echo "TABSTACK_API_KEY is not set" && exit 1)
