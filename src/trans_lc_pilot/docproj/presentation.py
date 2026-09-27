"""Present HTML: serialize it to a standalone document, open it in a browser.

These are the side-effecting companions to
:mod:`trans_lc_pilot.docproj.html_headings`, which turns a fragment into
:class:`Article` objects, and to :mod:`trans_lc_pilot.docproj.bundle`,
which owns the layout of a split on disk. Keeping the HTML rendering
here rather than in the CLI lets both entries reuse it.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from .source import SourceDoc

TMP_DIR = Path(__file__).resolve().parents[3] / ".tmp"


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

    Adds ``<!doctype>``, ``<html>``, ``<head>`` with a title and the
    empty-paragraph CSS, and the fragment body. Returns the full
    document as a string.

    Args:
        fragment: HTML fragment from mammoth (no doctype).
        title: Title for the document.

    Returns:
        str: Complete HTML document.
    """
    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        f"<title>{title}</title>\n"
        f"{_EMPTY_P_MARGIN_CSS}"
        "</head>\n"
        "<body>\n"
        f"{fragment}\n"
        "</body>\n"
        "</html>\n"
    )


def write_source_html(doc: SourceDoc) -> Path:
    """Write ``doc``'s HTML fragment to a fresh temp file.

    The output is the raw HTML mammoth generates from the docx — the
    document as a reader sees it — wrapped in a standalone HTML
    document so that preserved empty ``<p>`` elements actually render
    as blank lines. Used by ``--convert``; a split writes into a bundle
    instead (see :func:`trans_lc_pilot.docproj.bundle.write_bundle`).

    Args:
        doc: The source document to write.

    Returns:
        Path: Path of the written HTML file.

    Raises:
        OSError: On I/O failure while creating or writing the file.
    """
    TMP_DIR.mkdir(exist_ok=True)
    html = wrap_as_document(doc.fragment, title=f"Source: {doc.path.name}")

    fd, name = tempfile.mkstemp(prefix="docproj-source-", suffix=".html", dir=TMP_DIR)
    os.close(fd)
    path = Path(name)
    path.write_text(html, encoding="utf-8")
    return path


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
