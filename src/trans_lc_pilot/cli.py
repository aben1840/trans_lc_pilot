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
        strings (empty when omitted, which triggers REPL mode);
        ``model`` is an optional ``--model`` override.
    """
    parser = argparse.ArgumentParser(prog="trans-lc-pilot")
    parser.add_argument("prompt", nargs="*", help="Prompt text; omit for REPL.")
    parser.add_argument("--model", help="Override OPENAI_MODEL.")
    return parser.parse_args(argv)


def apply_overrides(args: argparse.Namespace):
    """Apply CLI-driven overrides and reload settings.

    Args:
        args: Parsed :class:`argparse.Namespace` from :func:`parse_args`.

    Returns:
        Settings: Freshly loaded
        :class:`~trans_lc_pilot.config.Settings`, after mutating the
        process environment with any ``--model`` override.

    Side Effects:
        When ``args.model`` is truthy, writes ``OPENAI_MODEL`` into
        :data:`os.environ` so the subsequent ``load_settings()`` call
        picks it up.
    """
    if args.model:
        import os
        os.environ["OPENAI_MODEL"] = args.model
    return load_settings()


def dispatch(agent, prompt: str | None) -> int:
    """Run the agent either for a single prompt or in an interactive REPL.

    Args:
        agent: Compiled agent produced by
            :func:`trans_lc_pilot.agent.build_agent`.
        prompt: Single-shot user prompt, or ``None`` to enter the REPL.

    Returns:
        int: Process-style exit code; ``0`` for both the single-shot
        path and a clean REPL exit (``Ctrl-D`` / ``Ctrl-C``).
    """
    if prompt is not None:
        print(run_once(agent, prompt))
        return 0
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

    Args:
        argv: Optional argument vector excluding the program name;
            defaults to ``sys.argv[1:]`` when ``None``.

    Returns:
        int: Exit code forwarded from :func:`dispatch`.
    """
    args = parse_args(argv if argv is not None else sys.argv[1:])
    settings = apply_overrides(args)
    agent = build_agent(settings)
    prompt = " ".join(args.prompt) if args.prompt else None
    return dispatch(agent, prompt)


if __name__ == "__main__":
    raise SystemExit(main())
