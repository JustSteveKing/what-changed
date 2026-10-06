import asyncio
import os
import signal
import sys

from what_changed.answer import answer
from what_changed.contract import EXIT_CODES, USAGE_EXIT_CODE, ApplicationAnswer


async def ask(question: str) -> ApplicationAnswer:
    # First Ctrl+C cancels the in-flight call and lets it report a cancelled state.
    # A second Ctrl+C exits immediately.
    cancel = asyncio.Event()

    def on_interrupt() -> None:
        if cancel.is_set():
            os._exit(EXIT_CODES["cancelled"])
        print("Cancelling. Press Ctrl+C again to exit immediately.", file=sys.stderr)
        cancel.set()

    asyncio.get_running_loop().add_signal_handler(signal.SIGINT, on_interrupt)
    return await answer(question, cancel=cancel)


def main() -> int:
    question = " ".join(sys.argv[1:])
    if not question:
        print('Usage: uv run what-changed "your question"', file=sys.stderr)
        return USAGE_EXIT_CODE

    result = asyncio.run(ask(question))

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
