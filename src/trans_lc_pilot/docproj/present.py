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
