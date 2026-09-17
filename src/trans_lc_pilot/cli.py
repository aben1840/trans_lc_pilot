"""Command-line entry: one-shot prompt or the interactive REPL."""
from __future__ import annotations

import argparse
import sys
import traceback

from . import repl
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


def _run_oneshot(prompt: str) -> int:
    """Send one prompt to the agent, print the reply, and finish.

    Args:
        prompt: Natural-language prompt.

    Returns:
        int: ``0`` on success; failures propagate to :func:`main`.
    """
    print(run_once(build_agent(load_settings()), prompt))
    return 0


def _run_interactive() -> int:
    """Enter the interactive REPL.

    Returns:
        int: Exit code from the REPL loop.
    """
    return repl.run(load_settings())


def _dispatch(argv: list[str]) -> int:
    """Route an argument vector to the one-shot or interactive mode.

    A prompt argument selects the one-shot mode; otherwise the
    interactive REPL starts.

    Args:
        argv: Argument vector excluding the program name.

    Returns:
        int: ``0`` on success.
    """
    args = parse_args(argv)
    if args.prompt:
        exit_code = _run_oneshot(" ".join(args.prompt))
    else:
        exit_code = _run_interactive()
    return exit_code


def main(argv: list[str] | None = None) -> int:
    """Entry point for the ``trans-lc-pilot`` console script.

    Two ways in:

    * ``trans-lc-pilot`` — interactive REPL.
    * ``trans-lc-pilot "prompt"`` — one-shot agent call.

    Args:
        argv: Optional argument vector excluding the program name;
            defaults to ``sys.argv[1:]`` when ``None``.

    Returns:
        int: Exit code; ``0`` for a clean run or REPL exit
        (``Ctrl-D`` / ``Ctrl-C``), ``1`` when an exception is caught
        and reported to ``stderr``.
    """
    argv = list(argv if argv is not None else sys.argv[1:])
    try:
        exit_code = _dispatch(argv)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
