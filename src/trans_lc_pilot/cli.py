"""Command-line entry: single-shot prompt or interactive REPL."""
from __future__ import annotations

import argparse
import sys

from .agent import build_agent, run_once
from .config import load_settings


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Argument vector excluding the program name; typically
            ``sys.argv[1:]``.

    Returns:
        argparse.Namespace: Parsed arguments. ``prompt`` is a list of
        strings (empty when omitted, in which case ``main`` enters
        REPL mode).
    """
    parser = argparse.ArgumentParser(prog="trans-lc-pilot")
    parser.add_argument("prompt", nargs="*", help="Prompt text; omit for REPL.")
    return parser.parse_args(argv)


def run_repl(agent) -> int:
    """Run the agent in an interactive REPL.

    Reads lines from stdin until end-of-file (``Ctrl-D``) or
    ``KeyboardInterrupt`` (``Ctrl-C``) and invokes the agent on
    each non-empty line. Empty lines are skipped without an LLM
    call.

    Args:
        agent: Compiled agent produced by
            :func:`trans_lc_pilot.agent.build_agent`.

    Returns:
        int: Process-style exit code; ``0`` on clean exit.
    """
    print("trans-lc-pilot REPL. Ctrl-D to exit.")
    while True:
        try:
            line = input("> ").strip()
        except EOFError:
            print()
            return 0
        except KeyboardInterrupt:
            print()
            return 0
        if not line:
            continue
        print(run_once(agent, line))


def main(argv: list[str] | None = None) -> int:
    """Entry point for the ``trans-lc-pilot`` console script.

    Dispatches to the one-shot path when a prompt is supplied on
    the command line, otherwise drops into the interactive REPL.

    Args:
        argv: Optional argument vector excluding the program name;
            defaults to ``sys.argv[1:]`` when ``None``.

    Returns:
        int: Exit code; ``0`` for a clean one-shot run or a clean
        REPL exit (``Ctrl-D`` / ``Ctrl-C``).
    """
    args = parse_args(argv if argv is not None else sys.argv[1:])
    settings = load_settings()
    agent = build_agent(settings)
    prompt = " ".join(args.prompt) if args.prompt else None
    if prompt is not None:
        print(run_once(agent, prompt))
        return 0
    else:
        return run_repl(agent)


if __name__ == "__main__":
    raise SystemExit(main())
