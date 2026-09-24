"""Standalone LangChain agent runtime.

This subpackage is fully self-contained: it owns its own config,
tools, prompt, agent factory, and REPL. It does not depend on the
top-level CLI's argparse-driven document actions, and the top-level
CLI does not depend on this package's agent machinery.

Public API:

* :func:`build_agent` — construct the compiled LangChain agent.
* :func:`run_once` — dispatch a single prompt to an agent and return text.
* :func:`run_repl` — run the interactive REPL until EOF or quit.
* :func:`load_settings` — build :class:`Settings` from the environment.
"""
from __future__ import annotations

from .agent import build_agent, run_once
from .config import Settings, load_settings
from .repl import run as run_repl

__all__ = [
    "Settings",
    "build_agent",
    "load_settings",
    "run_once",
    "run_repl",
]
