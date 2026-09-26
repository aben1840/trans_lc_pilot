"""Present a projection: write it to disk, open it in a browser.

These are the side-effecting companions to
:mod:`trans_lc_pilot.docproj.inspection`, which only turns a :class:`DocProj`
into a string. Keeping them here rather than in the REPL lets them be reused
as agent tools later.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from html import escape
from pathlib import Path

from .article import Article
from .document import DocProj
from .html_headings import split_by_headings

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


def write_inspection_html(proj: DocProj) -> Path:
    """Render ``proj``'s inspection view and write it to a fresh temp file.

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
    """Render ``proj``'s source view to HTML and write it.

    Differs from :func:`write_inspection_html`: the output is the raw HTML
    mammoth generates from the docx — the document as a reader sees it —
    rather than a tabular view of the parsed :class:`DocProj`.

    The fragment is wrapped in a standalone HTML document so that
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
    html = _wrap_as_document(
        proj.source_fragment(), title=f"DocProj: {proj.source_path.name}"
    )

    fd, name = tempfile.mkstemp(prefix="docproj-source-", suffix=".html", dir=TMP_DIR)
    os.close(fd)
    path = Path(name)
    path.write_text(html, encoding="utf-8")
    return path


def _slug(title: str, limit: int = 30) -> str:
    """Turn a heading into a filesystem-safe filename fragment.

    Args:
        title: Heading text.
        limit: Maximum length of the result.

    Returns:
        str: Slashes, colons and whitespace replaced by ``-``; falls
        back to ``"untitled"`` when nothing usable remains.
    """
    cleaned = re.sub(r'[<>:"/\\|?*\s]+', "-", title).strip("-")
    return cleaned[:limit] or "untitled"


def _article_filename(article: Article) -> str:
    """Name the output file for one article.

    Args:
        article: The article to name.

    Returns:
        str: ``000-preamble.html`` for the preamble, otherwise
        ``<number>-<slug>.html``.
    """
    if article.is_preamble:
        name = "000-preamble.html"
    else:
        name = f"{article.number:03d}-{_slug(article.title)}.html"
    return name


def _write_index(out_dir: Path, articles: list[Article], proj: DocProj) -> Path:
    """Write an index page linking every article.

    Args:
        out_dir: Directory holding the article files.
        articles: Articles that were written.
        proj: The projection the articles came from.

    Returns:
        Path: Path of the written index.
    """
    items: list[str] = []
    for article in articles:
        label = article.title or "preamble"
        items.append(
            f'<li><a href="{_article_filename(article)}">{escape(label)}</a></li>'
        )
    body = (
        f"<h1>{escape(proj.source_path.name)}</h1>\n"
        f"<p>{len(articles)} article(s) split at heading level.</p>\n"
        "<ul>\n" + "\n".join(items) + "\n</ul>"
    )
    index = out_dir / "index.html"
    index.write_text(
        _wrap_as_document(body, title=f"Articles: {proj.source_path.name}"),
        encoding="utf-8",
    )
    return index


def write_articles(proj: DocProj, level: int = 1) -> Path:
    """Split the source into one HTML file per article.

    Each article is written into a fresh subdirectory of ``.tmp/`` so a
    run's output stays together and does not mix with earlier renders.
    An ``index.html`` links them.

    Args:
        proj: The projection whose source file is to be split.
        level: Heading level to split on, 1-6.

    Returns:
        Path: Path of the index page.

    Raises:
        FileNotFoundError: If ``proj.source_path`` is no longer there.
        OSError: On I/O failure while reading or writing.
    """
    TMP_DIR.mkdir(exist_ok=True)
    articles = split_by_headings(proj.source_fragment(), level=level)
    out_dir = Path(tempfile.mkdtemp(prefix="articles-", dir=TMP_DIR))
    for article in articles:
        title = article.title or proj.source_path.name
        (out_dir / _article_filename(article)).write_text(
            _wrap_as_document(article.html, title=title), encoding="utf-8"
        )
    return _write_index(out_dir, articles, proj)


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
