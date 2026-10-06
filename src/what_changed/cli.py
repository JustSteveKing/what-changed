import asyncio
import sys

from what_changed.answer import answer


def main() -> int:
    question = " ".join(sys.argv[1:])
    if not question:
        print('Usage: uv run what-changed "your question"', file=sys.stderr)
        return 1

    result = asyncio.run(answer(question))

    print(f"Route: {result.decision.route} ({result.decision.reason})")
    print(f"State: {result.terminal_state or 'none'}{' [incomplete]' if result.incomplete else ''}")
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

    return 0 if result.terminal_state == "completed" and not result.incomplete else 1


if __name__ == "__main__":
    sys.exit(main())
