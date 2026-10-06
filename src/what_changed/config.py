import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field


# Everything configurable comes from the environment. TABSTACK_API_KEY is read by the
# Tabstack SDK itself and is deliberately not copied into this object.
class _Env(BaseModel):
    TABSTACK_RESEARCH_MODE: Literal["fast", "balanced"] = "fast"
    GITHUB_TOKEN: str | None = Field(default=None, min_length=1)
    PACKAGIST_MAILTO: str | None = None
    DIRECT_TIMEOUT_MS: int = Field(default=10_000, gt=0)
    # The docs give no server-side limit for research and say balanced mode can take
    # up to about four minutes, so the default leaves headroom above that.
    RESEARCH_TIMEOUT_MS: int = Field(default=300_000, gt=0)


@dataclass(frozen=True)
class Config:
    research_mode: Literal["fast", "balanced"]
    github_token: str | None
    user_agent: str
    direct_timeout_s: float
    research_timeout_s: float


def load_config(env: Mapping[str, str] = os.environ) -> Config:
    # Empty strings count as unset.
    parsed = _Env.model_validate({k: v for k, v in env.items() if k in _Env.model_fields and v != ""})

    # Packagist asks for a User-Agent with a contact address: https://packagist.org/apidoc
    user_agent = f"what-changed (mailto={parsed.PACKAGIST_MAILTO})" if parsed.PACKAGIST_MAILTO else "what-changed"

    return Config(
        research_mode=parsed.TABSTACK_RESEARCH_MODE,
        github_token=parsed.GITHUB_TOKEN,
        user_agent=user_agent,
        direct_timeout_s=parsed.DIRECT_TIMEOUT_MS / 1000,
        research_timeout_s=parsed.RESEARCH_TIMEOUT_MS / 1000,
    )
