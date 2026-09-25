"""Tools available to the LangChain agent."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from langchain_core.tools import tool

from trans_lc_pilot.docproj import heading_counts, presentation, read
from trans_lc_pilot.docproj.headings import split_by_headings


@tool
def get_current_time(timezone_name: str = "UTC") -> str:
    """Return the current time as an ISO-8601 string.

    Args:
        timezone_name: IANA timezone name (e.g. ``"UTC"``,
            ``"America/New_York"``). Defaults to ``"UTC"``. Empty strings
            are coerced to ``"UTC"``.

    Returns:
        str: ISO-8601 formatted timestamp in the requested timezone.

    Raises:
        ValueError: If ``timezone_name`` is not a valid IANA timezone name.
    """
    tz_name = timezone_name or "UTC"
    try:
        tz = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Unknown timezone: {timezone_name!r}") from exc
    return datetime.now(tz).isoformat()


@tool
def list_docx_heading_levels(file_path: str) -> str:
    """Report heading counts per level in a docx file.

    Does not write any files — it only inspects the document structure.
    Always run this before splitting, so you know what levels exist.

    Args:
        file_path: Path to the .docx file to inspect.

    Returns:
        str: One line per heading level present (e.g. ``"h2: 5"``), or
        ``"no headings found"`` when the document has no heading styles.
    """
    proj = read(file_path)
    counts = heading_counts(presentation.source_fragment(proj))
    if not counts:
        return "no headings found"
    lines = [f"h{level}: {count}" for level, count in sorted(counts.items())]
    return "\n".join(lines)


@tool
def convert_docx_to_html(file_path: str, open_browser: bool = True) -> str:
    """Convert a docx file to HTML via mammoth.

    Produces the document as a reader sees it, preserves empty paragraphs,
    and wraps the fragment in a standalone HTML document. The file is
    written to ``.tmp/`` under the repo root.

    Args:
        file_path: Path to the .docx file to convert.
        open_browser: Whether to open the HTML in the default browser
            after writing. Defaults to ``True``.

    Returns:
        str: Path of the written HTML file, optionally followed by a
        browser-open status line.
    """
    proj = read(file_path)
    path = presentation.write_source_html(proj)
    result = f"source: {proj.source_path}\nhtml: {path}"
    if open_browser:
        result += f"\n{presentation.open_in_browser(path)}"
    return result


@tool
def split_docx_by_headings(
    file_path: str, level: int = 1, open_browser: bool = True
) -> str:
    """Split a docx file into one HTML file per heading at the given level.

    Each article gets its own HTML file plus an ``index.html`` that links
    them all. The directory and files land in ``.tmp/`` under the repo
    root. Content before the first matching heading becomes a preamble
    file named ``000-preamble.html``.

    Args:
        file_path: Path to the .docx file to split.
        level: Heading level to split on, 1-6. Always run
            ``list_docx_heading_levels`` first to know what levels exist.
        open_browser: Whether to open the index page in the default
            browser after writing. Defaults to ``True``.

    Returns:
        str: Summary of what was written — source path, level used,
        article count, available heading levels, index path, and an
        optional note about preamble or "no heading at this level".
    """
    proj = read(file_path)
    fragment = presentation.source_fragment(proj)
    articles = split_by_headings(fragment, level=level)
    index_path = presentation.write_articles(proj, level=level)

    lines: list[str] = [
        f"source: {proj.source_path}",
        f"level: {level}",
        f"articles: {len(articles)}",
    ]
    if any(article.is_preamble for article in articles):
        lines.append("preamble: yes (content before the first heading)")
    if len(articles) == 1 and not articles[0].title:
        lines.append(f"note: no heading at level {level}; document left whole")
    lines.append("heading levels in document:")
    counts = heading_counts(fragment)
    if counts:
        for h_level, count in sorted(counts.items()):
            lines.append(f"  h{h_level}: {count}")
    else:
        lines.append("  no headings found")
    lines.append(f"index: {index_path}")
    if open_browser:
        lines.append(presentation.open_in_browser(index_path))
    return "\n".join(lines)


def default_tools() -> list:
    """Return the default tool set exposed to the agent.

    Returns:
        list: Tools the agent may call. Includes time retrieval and
        the full docx processing pipeline.
    """
    return [
        get_current_time,
        list_docx_heading_levels,
        convert_docx_to_html,
        split_docx_by_headings,
    ]
