"""Present a projection: write it to disk, open it in a browser.

These are the side-effecting companions to :mod:`trans_lc_pilot.docproj.render`,
which only turns a :class:`DocProj` into a string. Keeping them here rather
than in the REPL lets them be reused as agent tools later.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import mammoth

from .model import DocProj

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


def write_html(proj: DocProj) -> Path:
    """Render ``proj`` to HTML and write it to a fresh temp file.

    Files land in ``<repo>/.tmp/`` rather than the system tempdir so
    that snap-packaged browsers (Firefox, Chromium) — whose
    confinement refuses access to ``/tmp`` — can read the file. The
    directory is created on demand and ``.tmp/`` is in ``.gitignore``.
    Files are intentionally not cleaned up: a browser may still be
    loading them after the process that wrote them has moved on.

    Args:
        proj: The projection to render.

    Returns:
        Path: Path of the written HTML file.
    """
    TMP_DIR.mkdir(exist_ok=True)
    fd, name = tempfile.mkstemp(prefix="docproj-", suffix=".html", dir=TMP_DIR)
    os.close(fd)
    path = Path(name)
    path.write_text(proj.render("html"), encoding="utf-8")
    return path


_EMPTY_P_MARGIN_CSS = """\
<style>
  /* Empty <p> elements (preserved from the source docx) collapse to
     zero height by default; force them to take a full line. */
  p:empty { margin: 1em 0; }
</style>
"""


def _wrap_as_document(fragment: str, title: str) -> str:
    """Wrap a mammoth HTML fragment in a minimal standalone document.

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


def write_source_html(proj: DocProj) -> Path:
    """Convert ``proj``'s source file to HTML via mammoth and write it.

    Differs from :func:`write_html`: the output is the raw HTML mammoth
    generates from the docx — the document as a reader sees it — rather
    than a tabular view of the parsed :class:`DocProj`. Re-runs mammoth
    each time (it is cheap, and caching the string into ``DocProj``
    metadata would inflate every projection with HTML that most callers
    never ask for).

    The output preserves empty paragraphs (``ignore_empty_paragraphs=False``)
    and wraps the fragment in a standalone HTML document so that
    preserved empty ``<p>`` elements actually render as blank lines.

    Args:
        proj: The projection whose source file is to be re-rendered.

    Returns:
        Path: Path of the written HTML file.

    Raises:
        FileNotFoundError: If ``proj.source_path`` is no longer there.
        OSError: On I/O failure while reading or writing.
    """
    TMP_DIR.mkdir(exist_ok=True)
    with proj.source_path.open("rb") as f:
        result = mammoth.convert_to_html(f, ignore_empty_paragraphs=False)
    html = _wrap_as_document(result.value, title=f"DocProj: {proj.source_path.name}")

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
