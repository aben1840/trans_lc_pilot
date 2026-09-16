"""Agent factory: builds a LangChain tool-calling agent."""
from __future__ import annotations

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from .config import Settings
from .tools import default_tools

SYSTEM_PROMPT = (
    "You are a concise assistant. Answer directly. "
    "Use tools only when they clearly help."
)


def build_llm(settings: Settings) -> BaseChatModel:
    """Construct the chat model used by the agent.

    Args:
        settings: Resolved :class:`~trans_lc_pilot.config.Settings`
            providing the API key, model name, and optional base URL.

    Returns:
        BaseChatModel: A configured :class:`langchain_openai.ChatOpenAI`
        instance with ``temperature=0.2``.

    Raises:
        ValueError: If ``settings.openai_api_key`` is ``None`` (i.e.
            ``OPENAI_API_KEY`` was not provided in the environment).
    """
    if settings.openai_api_key is None:
        raise ValueError("OPENAI_API_KEY is not set")
    return ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        temperature=0.2,
    )


def build_agent(settings: Settings):
    """Build a LangChain tool-calling agent from settings.

    Args:
        settings: Resolved :class:`~trans_lc_pilot.config.Settings`
            driving model selection, credentials, and the default tool
            set.

    Returns:
        The compiled agent returned by
        :func:`langchain.agents.create_agent`, suitable for
        ``agent.invoke({"messages": [...]})``.
    """
    llm = build_llm(settings)
    return create_agent(
        model=llm,
        tools=default_tools(),
        system_prompt=SYSTEM_PROMPT,
    )


def run_once(agent, message: str) -> str:
    """Send a single user message and return the final assistant text.

    Args:
        agent: Compiled agent produced by :func:`build_agent`.
        message: User prompt to dispatch to the agent.

    Returns:
        str: Concatenated text content from the agent's last message.
        Returns an empty string when the agent yields no messages, and
        flattens list-shaped content blocks into a single string.
    """
    result = agent.invoke({"messages": [{"role": "user", "content": message}]})
    messages = result.get("messages", [])
    if not messages:
        return ""
    last = messages[-1]
    content = getattr(last, "content", "")
    if isinstance(content, list):
        return "".join(
            block.get("text", "") for block in content if isinstance(block, dict)
        )
    return str(content)
