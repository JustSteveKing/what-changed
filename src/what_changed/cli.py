import asyncio
import sys

from what_changed.answer import answer
from what_changed.contract import EXIT_CODES, USAGE_EXIT_CODE


def main() -> int:
    question = " ".join(sys.argv[1:])
    if not question:
        print('Usage: uv run what-changed "your question"', file=sys.stderr)
        return USAGE_EXIT_CODE

    result = asyncio.run(answer(question))

    print(f"Route: {result.decision.route} ({result.decision.reason})")
    print(f"State: {result.terminal_state}{' [incomplete]' if result.incomplete else ''}")
    for reason in result.incomplete_reasons:
        print(f"  - {reason}")
    if result.error:
        print(f"Error: {result.error.name}: {result.error.message}")
    print()
    print(result.text)
    if result.sources:
        print("\nSources:")
        for source in result.sources:
            print(f"{source.position}. {source.title or '(untitled)'}: {source.url}")

    return EXIT_CODES[result.terminal_state]


if __name__ == "__main__":
    sys.exit(main())
