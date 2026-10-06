import os
from pathlib import Path

import pytest


def files_under(*dirs: str) -> list[Path]:
    return [p for d in dirs if Path(d).exists() for p in Path(d).rglob("*") if p.is_file()]


# Secrets come from the environment only and must never be written to disk.
@pytest.mark.parametrize("name", ["TABSTACK_API_KEY", "GITHUB_TOKEN"])
def test_secret_never_lands_on_disk(name: str) -> None:
    secret = os.environ.get(name)
    if not secret:
        pytest.skip(f"{name} is not set")
    leaks = [str(p) for p in files_under("runs", "tests/fixtures") if secret in p.read_text(errors="ignore")]
    assert leaks == []
