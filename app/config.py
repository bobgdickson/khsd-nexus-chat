from __future__ import annotations

import json
from functools import cached_property
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_INSTRUCTIONS = (
    "You are the Kern High School District Project SPARK assistant. Provide concise, actionable answers that clearly cite any relevant"
    " details. If you are unsure, say so and share the next best action."
)

DEFAULT_PROMPTS = [
    {"label": "What can you do?", "prompt": "What can you do?"},
    {"label": "Summarize key data", "prompt": "Summarize the latest Nexus data drop."},
    {"label": "Enrollment trends", "prompt": "How has enrollment changed over time?"},
]


def _parse_prompts(raw: str | None) -> list[dict[str, str]]:
    if not raw:
        return DEFAULT_PROMPTS
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return DEFAULT_PROMPTS

    prompts: list[dict[str, str]] = []
    if isinstance(payload, list):
        for item in payload:
            if not isinstance(item, dict):
                continue
            label = str(item.get("label") or item.get("prompt") or "").strip()
            prompt = str(item.get("prompt") or item.get("label") or "").strip()
            if not prompt:
                continue
            prompts.append({"label": label or prompt, "prompt": prompt})
    return prompts or DEFAULT_PROMPTS


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    openai_api_key: str | None = None
    model: str = "gpt-5.1"
    assistant_instructions: str = DEFAULT_INSTRUCTIONS
    history_limit: int = Field(default=20, ge=1, le=200)
    app_name: str = "KHSD Nexus Chat Backend"
    public_base_url: str = "http://localhost:8004"
    database_url: str | None = None
    domain_key: str = "domain_pk_localhost_dev"
    start_screen_greeting: str = "Ask me anything about your schools."
    composer_placeholder: str = "How can we help?"
    start_screen_prompts_json: str | None = None
    fin_connection_string: str | None = Field(default=None, alias="FIN_STR")
    cors_allow_origins: list[str] = Field(default_factory=lambda: ["*"])

    model_config = SettingsConfigDict(env_prefix="", env_file=".env", extra="ignore")

    @cached_property
    def start_screen_prompts(self) -> list[dict[str, str]]:
        return _parse_prompts(self.start_screen_prompts_json)

    def get_public_config(self) -> dict[str, Any]:
        return {
            "enabled": True,
            "ready": bool(self.openai_api_key),
            "apiUrl": f"{self.public_base_url.rstrip('/')}/chatkit",
            "domainKey": self.domain_key,
            "greeting": self.start_screen_greeting,
            "placeholder": self.composer_placeholder,
            "startScreenPrompts": self.start_screen_prompts,
        }


settings = Settings()
