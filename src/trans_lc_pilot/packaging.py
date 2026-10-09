"""Standalone CLI entry point for packaging the project as a plugin.

Usage::

    trans-lc-pilot-package [--out FILE]

Produces a distributable zip archive. The archive currently contains
only ``setup.cmd`` (a placeholder that prints ``hello world``); the
real plugin layout — ``.codebuddy-plugin/``, ``agents/``, ``skills/``,
``avatars/`` — lands here in a later milestone.

This entry point does **not** handle document-only operations
(``inspect``, ``preview``, ``split``, ``assemble``). Those live on
``trans-lc-pilot`` (see :mod:`trans_lc_pilot.cli`).
"""
from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

_SETUP_CMD_BODY = "@echo hello world\r\n"
"""Placeholder ``setup.cmd`` payload; ``\\r\\n`` keeps the file
Windows-native, which a ``.cmd`` should be."""


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Argument vector excluding the program name.

    Returns:
        argparse.Namespace: Parsed arguments. ``out`` names the zip
        archive to write.
    """
    parser = argparse.ArgumentParser(prog="trans-lc-pilot-package")
    parser.add_argument(
        "--out",
        metavar="FILE",
        default="plugin.zip",
        help="Path of the zip to write (default: ./plugin.zip).",
    )
    return parser.parse_args(argv)


def _write_plugin(out_path: Path) -> None:
    """Write the plugin archive at ``out_path``.

    The archive currently holds a single ``setup.cmd`` whose payload
    is :data:`_SETUP_CMD_BODY` — a stub that will be replaced when
    the real plugin layout is wired up.

    Args:
        out_path: Destination zip path.
    """
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("setup.cmd", _SETUP_CMD_BODY)


def main(argv: list[str] | None = None) -> int:
    """Entry point for the ``trans-lc-pilot-package`` console script.

    Args:
        argv: Optional argument vector excluding the program name;
            defaults to ``sys.argv[1:]`` when ``None``.

    Returns:
        int: Exit code; ``0`` for a clean run, ``1`` on failure.
    """
    args = parse_args(list(argv if argv is not None else sys.argv[1:]))
    out_path = Path(args.out)
    try:
        _write_plugin(out_path)
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"plugin: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
