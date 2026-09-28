"""Tools available to the LangChain agent."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from langchain_core.tools import tool

from trans_lc_pilot.docproj import (
    bundle,
    heading_counts,
    presentation,
    read,
)
from trans_lc_pilot.workspace import Workspace, ingest, write_index, write_preview


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
    doc = read(file_path)
    counts = heading_counts(doc.fragment)
    if not counts:
        return "no headings found"
    lines = [f"h{level}: {count}" for level, count in sorted(counts.items())]
    return "\n".join(lines)


@tool
def preview_docx(
    file_path: str, workspace: str = "", open_browser: bool = True
) -> str:
    """Convert a docx file to HTML via mammoth and open it for a look.

    Produces the document as a reader sees it, preserves empty paragraphs,
    and wraps the fragment in a standalone HTML document. The file lands
    in the workspace scratch (``<workspace>/.tmp/``) under a fresh random
    name each call, and is never cleaned up.

    A preview is a glance, so it does not ingest the document: nothing is
    copied into ``sources/``.

    Args:
        file_path: Path to the .docx file to convert.
        workspace: Root directory artifacts land under. Empty (the
            default) uses the current working directory.
        open_browser: Whether to open the HTML in the default browser
            after writing. Defaults to ``True``.

    Returns:
        str: Path of the written HTML file, optionally followed by a
        browser-open status line.
    """
    doc = read(file_path)
    path = write_preview(doc, Workspace.at(workspace or Path.cwd()))
    result = f"source: {doc.path}\nhtml: {path}"
    if open_browser:
        result += f"\n{presentation.open_in_browser(path)}"
    return result


@tool
def split_docx_by_headings(
    file_path: str,
    level: int = 1,
    workspace: str = "",
    as_name: str = "",
    open_browser: bool = True,
) -> str:
    """Split a docx file into a bundle of HTML pieces, one per heading.

    The bundle is a directory holding the pieces, a manifest recording
    their order, an index page linking them, and a copy of the source
    document that later supplies the styles when the pieces are
    assembled back into a docx. Content before the first matching
    heading becomes a preamble file named ``000-preamble.html``.

    The document is copied into ``<workspace>/sources/`` first, and the
    bundle records that copy. Splitting the same document again costs
    nothing; storing *different* content under a name already taken is
    refused, so a bundle is never silently rebuilt from another
    document.

    Args:
        file_path: Path to the .docx file to split.
        level: Heading level to split on, 1-6. Always run
            ``list_docx_heading_levels`` first to know what levels exist.
            The bundle lands at
            ``<workspace>/bundles/<source-name>-h<level>``, and never
            overwrites a directory that already holds files.
        workspace: Root directory artifacts land under. Empty (the
            default) uses the current working directory.
        as_name: Store the source under this name instead of its own
            file name. Needed when that name already holds a different
            document.
        open_browser: Whether to open the index page in the default
            browser after writing. Defaults to ``True``.

    Returns:
        str: Summary of what was written — source path, level used,
        article count, available heading levels, bundle directory, index
        path, and an optional note about preamble or "no heading at this
        level".
    """
    doc = read(file_path)
    ws = Workspace.at(workspace or Path.cwd())
    source = ingest(ws, doc.path, as_name=as_name or None)
    doc = replace(doc, path=source.path)
    root = ws.bundle_dir(doc.path.name, level)
    record = bundle.write_bundle(doc, level=level, out_dir=root)
    index_path = root / bundle.INDEX_NAME

    lines: list[str] = [f"source: {source.origin}"]
    if source.stored:
        lines.append(f"stored: {source.path}")
    lines += [
        f"level: {level}",
        f"articles: {len(record.articles)}",
    ]
    if record.preamble is not None:
        lines.append("preamble: yes (content before the first heading)")
    if len(record.articles) == 1 and not record.articles[0].title:
        lines.append(f"note: no heading at level {level}; document left whole")
    lines.append("heading levels in document:")
    counts = heading_counts(doc.fragment)
    if counts:
        for h_level, count in sorted(counts.items()):
            lines.append(f"  h{h_level}: {count}")
    else:
        lines.append("  no headings found")
    lines.append(f"bundle: {root}")
    lines.append(f"index: {index_path}")
    _refresh_index(ws, lines)
    if open_browser:
        # The bundle's index lists the pieces; the workspace index above
        # it lists bundles, so it is not what a split should open.
        lines.append(presentation.open_in_browser(index_path))
    return "\n".join(lines)


def _refresh_index(workspace: Workspace, notices: list[str]) -> None:
    """Rewrite the workspace index, noting a failure rather than raising.

    The split or assembly is the work; the index is derived from it, so
    a page that could not be refreshed should be reported, not thrown.

    Args:
        workspace: Whose index to refresh.
        notices: Lines to append the warning to.
    """
    try:
        write_index(workspace)
    except OSError as exc:
        notices.append(f"warning: workspace index not written: {exc}")


@tool
def assemble_docx_from_bundle(
    bundle_dir: str,
    output_path: str = "",
    template_path: str = "",
    workspace: str = "",
    force: bool = False,
    open_browser: bool = True,
) -> str:
    """Assemble a bundle's HTML pieces into a new docx.

    The document is rebuilt from the pieces in the order the bundle's
    manifest gives, with its styles taken from the bundle's copy of the
    original document, so page setup, headers, footers and theme
    survive. Whatever the HTML cannot express does not — report every
    ``warning:`` line verbatim, because those name what was lost.

    The source docx is never modified; the output is a new file.

    Args:
        bundle_dir: The bundle directory ``split_docx_by_headings``
            wrote; it holds the manifest that defines the order.
        output_path: Where to write the docx. Empty (the default) uses
            ``<workspace>/output/<bundle-name>.docx``.
        template_path: A docx to take styles from instead of the bundle's
            copy of the original. Empty (the default) uses that copy.
        workspace: Root directory artifacts land under. Empty (the
            default) uses the current working directory.
        force: Overwrite ``output_path`` when it already exists.
        open_browser: Whether to open the written docx in the default
            handler after writing. Defaults to ``True``.

    Returns:
        str: Bundle, piece count, output path, which pieces were edited
        since the split, and one ``warning:`` line per construct that
        could not be carried over.
    """
    root = Path(bundle_dir)
    ws = Workspace.at(workspace or Path.cwd())
    out_path = Path(output_path) if output_path else ws.output_path(root)
    result = bundle.assemble_docx(
        root, out_path, template=template_path or None, force=force
    )

    lines: list[str] = [
        f"bundle: {root}",
        f"pieces: {result.pieces}",
        f"output: {result.output}",
    ]
    if result.edited:
        lines.append(
            "edited: " + ", ".join(f"{number:03d}" for number in result.edited)
        )
    else:
        lines.append("edited: none (every piece still matches its split-time hash)")
    lines.extend(f"warning: {message}" for message in result.warnings)
    _refresh_index(ws, lines)
    if open_browser:
        lines.append(presentation.open_in_browser(result.output))
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
        preview_docx,
        split_docx_by_headings,
        assemble_docx_from_bundle,
    ]
