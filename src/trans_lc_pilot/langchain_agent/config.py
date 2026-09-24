"""Runtime configuration loaded from environment variables."""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    """Runtime configuration for the LangChain agent.

    Attributes:
        openai_api_key: OpenAI API key. ``None`` when ``OPENAI_API_KEY``
            is unset in the environment; required at runtime by
            :func:`trans_lc_pilot.langchain_agent.agent.build_llm`,
            which raises :class:`ValueError` if it is missing.
        openai_model: Chat model name. Falls back to ``"gpt-4o-mini"``
            when ``OPENAI_MODEL`` is unset in the environment.
        openai_base_url: Optional base URL for a compatible OpenAI-style
            endpoint. ``None`` when ``OPENAI_BASE_URL`` is unset, i.e.
            the public OpenAI API.
    """

    openai_api_key: str | None
    openai_model: str
    openai_base_url: str | None


def load_settings() -> Settings:
    """Build :class:`Settings` from the process environment.

    Reads the following environment variables (typically populated from
    ``.env`` via :func:`dotenv.load_dotenv`, called at module import):

    * ``OPENAI_API_KEY`` — required at runtime, may be ``None`` here.
    * ``OPENAI_MODEL`` — defaults to ``"gpt-4o-mini"``.
    * ``OPENAI_BASE_URL`` — optional; ``None`` for the public OpenAI
      endpoint.

    Returns:
        Settings: A populated, frozen :class:`Settings` instance.
    """
    return Settings(
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        openai_base_url=os.getenv("OPENAI_BASE_URL"),
    )
