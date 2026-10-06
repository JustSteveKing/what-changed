# The demo: one Research call, print the answer, done.
# Deliberately naive. See the git history for what changes after this.
import sys

from tabstack import Tabstack

question = " ".join(sys.argv[1:])
if not question:
    print('Usage: uv run src/demo.py "your question"', file=sys.stderr)
    sys.exit(1)

client = Tabstack()
stream = client.agent.research(query=question, mode="fast")

for event in stream:
    if event.event == "complete":
        print(event.data.report)
        print("\nSources:")
        for page in event.data.metadata.cited_pages or []:
            print(f"- {page.title or '(untitled)'}: {page.url}")
    if event.event == "error":
        raise RuntimeError(event.data.error.message)
