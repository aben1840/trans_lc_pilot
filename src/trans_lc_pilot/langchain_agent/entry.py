"""Standalone CLI entry point for the LangChain agent.

Usage::

    trans-lc-pilot-agent "split this docx by headings"   # one-shot
    trans-lc-pilot-agent                                 # interactive REPL

This entry point does **not** handle document-only operations
(``--split``, ``--convert``, ``--list-levels``). Those live on
``trans-lc-pilot`` (see :mod:`trans_lc_pilot.cli`).
"""
from __future__ import annotations

import argparse
import sys

from . import repl
from .agent import build_agent, run_once
from .config import load_settings


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Argument vector excluding the program name.

    Returns:
        argparse.Namespace: Parsed arguments. ``prompt`` is a list of
        strings (empty when omitted, in which case ``main`` enters
        REPL mode).
    """
    parser = argparse.ArgumentParser(prog="trans-lc-pilot-agent")
    parser.add_argument(
        "prompt",
        nargs="*",
        help="Prompt text; omit for interactive REPL.",
    )
    return parser.parse_args(argv)


def _run_oneshot(prompt: str) -> int:
    """Send one prompt to the agent and print the reply.

    Args:
        prompt: Natural-language prompt.

    Returns:
        int: ``0`` on success.
    """
    print(run_once(build_agent(load_settings()), prompt))
    return 0


def main(argv: list[str] | None = None) -> int:
    """Entry point for the ``trans-lc-pilot-agent`` console script.

    Args:
        argv: Optional argument vector excluding the program name;
            defaults to ``sys.argv[1:]`` when ``None``.

    Returns:
        int: Exit code; ``0`` for a clean run or REPL exit.
    """
    args = parse_args(list(argv if argv is not None else sys.argv[1:]))
    if args.prompt:
        return _run_oneshot(" ".join(args.prompt))
    return repl.run(load_settings())


if __name__ == "__main__":
    raise SystemExit(main())
