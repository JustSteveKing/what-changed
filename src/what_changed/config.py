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


@dataclass(frozen=True)
class Config:
    research_mode: Literal["fast", "balanced"]
    github_token: str | None
    user_agent: str


def load_config(env: Mapping[str, str] = os.environ) -> Config:
    # Empty strings count as unset.
    parsed = _Env.model_validate({k: v for k, v in env.items() if k in _Env.model_fields and v != ""})

    # Packagist asks for a User-Agent with a contact address: https://packagist.org/apidoc
    user_agent = f"what-changed (mailto={parsed.PACKAGIST_MAILTO})" if parsed.PACKAGIST_MAILTO else "what-changed"

    return Config(
        research_mode=parsed.TABSTACK_RESEARCH_MODE,
        github_token=parsed.GITHUB_TOKEN,
        user_agent=user_agent,
    )
