"""Present HTML: serialize it to a standalone document, open it in a browser.

The side-effecting companions to
:mod:`trans_lc_pilot.docproj.html_headings`, which turns a fragment into
:class:`Article` objects. Nothing here decides where a file belongs —
the caller does, and for both entry points that caller is
:mod:`trans_lc_pilot.workspace`.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from html import escape
from pathlib import Path

GENERATOR = "trans-lc-pilot"
GENERATOR_META = f'<meta name="generator" content="{GENERATOR}">'


def _browser_command() -> list[str] | None:
    """Return the platform's "open this file" command prefix.

    Returns:
        list[str] | None: Argv prefix for launching the default file
        handler, or ``None`` when no supported opener is on ``PATH``.
    """
    if sys.platform == "darwin":
        candidates = [["open"]]
    elif sys.platform.startswith("win"):
        candidates = [["cmd", "/c", "start", ""]]
    else:
        candidates = [["xdg-open"], ["wslview"]]
    for cmd in candidates:
        if shutil.which(cmd[0]) is not None:
            return cmd
    return None


_EMPTY_P_MARGIN_CSS = """\
<style>
  /* Empty <p> elements (preserved from the source docx) collapse to
     zero height by default; force them to take a full line. */
  p:empty { margin: 1em 0; }
</style>
"""


def wrap_as_document(fragment: str, title: str) -> str:
    """Wrap an HTML fragment in a minimal standalone document.

    Adds ``<!doctype>``, an ``<html>`` head carrying the title, the
    empty-paragraph CSS and a generator marker, then the fragment body.

    Args:
        fragment: HTML fragment from mammoth (no doctype).
        title: Title for the document. Escaped, since it comes from a
            file name or a heading and may hold ``&`` or ``<``.

    Returns:
        str: Complete HTML document.
    """
    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        f"{GENERATOR_META}\n"
        f"<title>{escape(title)}</title>\n"
        f"{_EMPTY_P_MARGIN_CSS}"
        "</head>\n"
        "<body>\n"
        f"{fragment}\n"
        "</body>\n"
        "</html>\n"
    )


def open_in_browser(path: Path) -> str:
    """Open ``path`` with the platform's default handler.

    Never raises: headless machines have no opener, so the failure is
    reported as a message the caller can print or return.

    Args:
        path: File to open.

    Returns:
        str: Human-readable status message.
    """
    cmd = _browser_command()
    if cmd is None:
        message = f"no browser opener found; open manually: {path}"
    else:
        try:
            subprocess.Popen(
                [*cmd, str(path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            message = f"opened: {path}"
        except OSError as exc:
            message = f"could not open browser ({exc}); open manually: {path}"
    return message
