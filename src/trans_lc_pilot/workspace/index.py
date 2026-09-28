"""The aggregate view: every bundle in a workspace, on one page.

Derived, never authoritative. The manifests are the truth and this page
is a projection of them, rebuilt from disk on each write — so the worst
a stale copy can do is be replaced, and a bundle dropped in by hand is
picked up without being registered anywhere.
"""
from __future__ import annotations

from dataclasses import dataclass
from html import escape
from pathlib import Path
from urllib.parse import quote

from ..docproj.bundle import INDEX_NAME as BUNDLE_INDEX
from ..docproj.bundle import BundleError, read_bundle
from ..docproj.presentation import GENERATOR, GENERATOR_META, wrap_as_document
from .ingest import list_sources, read_origins
from .layout import BUNDLES_DIR, OUTPUT_DIR, Workspace

#: Read when testing whether a file is ours; a document's ``<head>`` is
#: at the top, so there is no reason to pull in a large stranger.
_MARKER_WINDOW = 4096


@dataclass(frozen=True)
class Entry:
    """One bundle as the index shows it.

    Attributes:
        name: The bundle directory's name.
        level: Heading level the split used, or ``None`` when the
            bundle could not be read.
        pieces: How many pieces its manifest lists, or ``None``.
        source: The stored source document it was built from, or
            ``None``.
        origin: Where that source came from, when the workspace
            recorded it.
        output: The assembled docx beside it, or ``None`` when there
            is none.
        problem: Why the bundle could not be read, or ``None``.
    """

    name: str
    level: int | None
    pieces: int | None
    source: str | None
    origin: str | None
    output: str | None
    problem: str | None


def render_index(workspace: Workspace) -> str:
    """Render the aggregate page for a workspace.

    Args:
        workspace: Whose bundles and sources to render.

    Returns:
        str: A standalone HTML document linking every bundle.
    """
    entries = _entries(workspace)
    sources = list_sources(workspace)
    heading = f"Workspace: {workspace.root.name or workspace.root}"
    body = "\n".join(
        [
            f"<h1>{escape(heading)}</h1>",
            f"<p>{_count(len(entries), 'bundle')} from"
            f" {_count(len(sources), 'source')}.</p>",
            _sources_section(workspace, sources),
            _bundles_section(entries),
        ]
    )
    return wrap_as_document(body, title=heading)


def write_index(workspace: Workspace, *, force: bool = False) -> Path:
    """Write the aggregate index.

    Refuses to overwrite a file this tool did not write, so a workspace
    that happens to hold a real ``index.html`` keeps it. An index this
    tool wrote carries the generator marker that
    :func:`trans_lc_pilot.docproj.presentation.wrap_as_document` adds, so
    the ordinary refresh is never interrupted.

    Args:
        workspace: Whose index to write.
        force: Overwrite a file that is not ours.

    Returns:
        Path: The page that was written.

    Raises:
        FileExistsError: If the path holds a file without the generator
            marker and ``force`` is false.
        OSError: On I/O failure.
    """
    path = workspace.index
    if path.is_file() and not force and not _is_ours(path):
        raise FileExistsError(
            f"{path} was not written by {GENERATOR} (use --force to overwrite)"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_index(workspace), encoding="utf-8")
    return path


def _is_ours(path: Path) -> bool:
    """Whether a file carries this tool's generator marker.

    Args:
        path: File to inspect.

    Returns:
        bool: ``True`` when the marker is within the first few
        kilobytes; ``False`` when it is absent or unreadable.
    """
    try:
        with path.open(encoding="utf-8") as handle:
            head = handle.read(_MARKER_WINDOW)
    except (OSError, UnicodeDecodeError):
        return False
    return GENERATOR_META in head


def _entries(workspace: Workspace) -> list[Entry]:
    """Collect every readable bundle in a workspace.

    A directory that is not a bundle is reported rather than raising:
    one stray folder among a dozen good ones must not empty the page.

    Args:
        workspace: Whose ``bundles/`` directory to scan.

    Returns:
        list[Entry]: One entry per directory, in name order.
    """
    if not workspace.bundles.is_dir():
        return []
    origins = read_origins(workspace)
    return [
        _entry(workspace, directory, origins)
        for directory in sorted(workspace.bundles.iterdir())
        if directory.is_dir()
    ]


def _entry(
    workspace: Workspace, directory: Path, origins: dict[str, dict]
) -> Entry:
    """Describe one bundle directory.

    Args:
        workspace: The workspace the directory sits in.
        directory: The candidate bundle directory.
        origins: The workspace's origin record.

    Returns:
        Entry: What the index shows for it.
    """
    try:
        bundle = read_bundle(directory)
    except BundleError as exc:
        return Entry(
            name=directory.name,
            level=None,
            pieces=None,
            source=None,
            origin=None,
            output=None,
            problem=str(exc),
        )

    source = Path(bundle.template.original_path).name
    record = origins.get(source)
    output = workspace.output_path(directory.name)
    return Entry(
        name=directory.name,
        level=bundle.level,
        pieces=len(bundle.pieces),
        source=source,
        origin=str(record["origin"]) if record and "origin" in record else None,
        output=output.name if output.is_file() else None,
        problem=None,
    )


def _sources_section(workspace: Workspace, sources: list[str]) -> str:
    """Render the list of ingested documents.

    Args:
        workspace: The workspace being rendered.
        sources: The stored source names.

    Returns:
        str: The section's HTML.
    """
    if not sources:
        return "<h2>Sources</h2>\n<p>nothing ingested yet</p>"
    origins = read_origins(workspace)
    items = []
    for name in sources:
        record = origins.get(name)
        line = f"<strong>{escape(name)}</strong>"
        if record and "origin" in record:
            line += f" &mdash; from {escape(str(record['origin']))}"
        items.append(f"<li>{line}</li>")
    return "<h2>Sources</h2>\n<ul>\n" + "\n".join(items) + "\n</ul>"


def _bundles_section(entries: list[Entry]) -> str:
    """Render the list of bundles.

    Args:
        entries: What each bundle directory holds.

    Returns:
        str: The section's HTML.
    """
    if not entries:
        return "<h2>Bundles</h2>\n<p>none yet</p>"
    items = "\n".join(f"<li>{_describe(entry)}</li>" for entry in entries)
    return "<h2>Bundles</h2>\n<ul>\n" + items + "\n</ul>"


def _describe(entry: Entry) -> str:
    """Render one bundle as the contents of a list item.

    Args:
        entry: The bundle to describe.

    Returns:
        str: HTML naming the bundle, where it came from, and what was
        made of it.
    """
    if entry.problem is not None:
        return (
            f"<strong>{escape(entry.name)}</strong>"
            f" &mdash; unreadable: {escape(entry.problem)}"
        )

    facts = [
        _count(entry.pieces or 0, "piece"),
        f"split at h{entry.level}",
    ]
    if entry.source is not None:
        fact = f"from {escape(entry.source)}"
        if entry.origin is not None:
            fact += f" ({escape(entry.origin)})"
        facts.append(fact)

    line = _link(f"{BUNDLES_DIR}/{entry.name}/{BUNDLE_INDEX}", entry.name)
    line += " &mdash; " + ", ".join(facts)
    if entry.output is not None:
        line += " &middot; " + _link(f"{OUTPUT_DIR}/{entry.output}", "assembled")
    return line


def _link(relative: str, label: str) -> str:
    """Render an anchor to something inside the workspace.

    Both halves are encoded: a bundle directory is named after a
    document, so neither its path nor its name can be assumed safe as
    HTML or as a URL.

    Args:
        relative: Path relative to the workspace root.
        label: Text to show.

    Returns:
        str: An ``<a>`` element.
    """
    return f'<a href="{quote(relative)}">{escape(label)}</a>'


def _count(number: int, noun: str) -> str:
    """Render a count with a pluralized noun.

    Args:
        number: The count.
        noun: Singular form.

    Returns:
        str: ``"1 piece"``, ``"0 pieces"``, ``"2 pieces"``.
    """
    return f"{number} {noun}" if number == 1 else f"{number} {noun}s"
