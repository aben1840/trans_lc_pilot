"""Split a document into articles at headings.

The splitter operates on the HTML fragment produced by mammoth. This is
the path used by the default CLI and the LangChain agent.
"""
from __future__ import annotations

from bs4 import BeautifulSoup, NavigableString, Tag

from .article import Article


def split_by_headings(fragment: str, level: int = 1) -> list[Article]:
    """Split an HTML fragment into articles at each heading of ``level``.

    Content before the first matching heading becomes a preamble
    article (number ``0``), emitted only when it is non-empty. Content
    after the last heading belongs to the last article; headings at
    other levels stay inside whichever article contains them.

    A fragment with no heading at ``level`` yields a single article
    holding the whole document — an undivided document is a valid
    result, not a failure.

    Args:
        fragment: HTML fragment, typically from mammoth.
        level: Heading level to split on, 1-6.

    Returns:
        list[Article]: Pieces in document order.
    """
    soup = BeautifulSoup(fragment, "html.parser")
    nodes = [node for node in soup.children if _is_significant(node)]
    target = f"h{level}"
    starts = [i for i, node in enumerate(nodes) if _is_heading(node, target)]

    if not starts:
        return [Article(number=1, title="", html=_serialize(nodes))]

    articles: list[Article] = []
    if starts[0] > 0:
        preamble = _serialize(nodes[: starts[0]])
        if preamble.strip():
            articles.append(Article(number=0, title="", html=preamble))

    number = 1
    for position, start in enumerate(starts):
        end = starts[position + 1] if position + 1 < len(starts) else len(nodes)
        chunk = nodes[start:end]
        title = chunk[0].get_text(" ", strip=True)
        articles.append(Article(number=number, title=title, html=_serialize(chunk)))
        number += 1

    return articles


def heading_counts(fragment: str) -> dict[int, int]:
    """Count top-level headings by level in an HTML fragment.

    Applies the same node rules as :func:`split_by_headings`, so the
    counts predict exactly what a split at each level would do. In
    particular a heading nested inside a ``<div>`` or a table is not
    counted, because it is not a split boundary either.

    Use this to choose a level before splitting: reporting the levels a
    document actually has is what lets a caller decide, rather than
    guessing.

    Args:
        fragment: HTML fragment, typically from mammoth.

    Returns:
        dict[int, int]: Heading level (1-6) mapped to how many
        top-level headings of that level the fragment holds. Levels
        with no headings are absent, so a document without headings
        yields an empty dict.
    """
    soup = BeautifulSoup(fragment, "html.parser")
    counts: dict[int, int] = {}
    for node in soup.children:
        if not _is_significant(node):
            continue
        level = _heading_level(node)
        if level is not None:
            counts[level] = counts.get(level, 0) + 1
    return counts


def _is_significant(node: object) -> bool:
    """Whether a top-level node carries content worth keeping.

    Whitespace-only text nodes between tags are dropped so the
    serialized output has no stray blank lines.

    Args:
        node: A child of the parsed fragment.

    Returns:
        bool: ``True`` for tags and non-blank text.
    """
    is_text = isinstance(node, NavigableString)
    return bool(str(node).strip()) if is_text else True


_HEADING_TAGS = frozenset(f"h{level}" for level in range(1, 7))


def _heading_level(node: object) -> int | None:
    """Return the heading level of a node, or ``None`` when it is not one.

    Deliberately separate from :func:`_is_heading`, which matches an
    arbitrary tag name and so would also accept a stray ``<h7>``. That
    path is unreachable through the REPL or the CLI — both validate the
    level as 1-6 — and for those the two agree.

    Args:
        node: A child of the parsed fragment.

    Returns:
        int | None: ``1``-``6`` for ``<h1>``-``<h6>``, else ``None``.
    """
    if isinstance(node, Tag) and node.name in _HEADING_TAGS:
        return int(node.name[1])
    return None


def _is_heading(node: object, target: str) -> bool:
    """Whether a node is a heading tag of the target name.

    Args:
        node: A child of the parsed fragment.
        target: Tag name to match, e.g. ``"h1"``.

    Returns:
        bool: ``True`` when the node is that heading.
    """
    return isinstance(node, Tag) and node.name == target


def _serialize(nodes: list) -> str:
    """Concatenate parsed nodes back into an HTML fragment.

    Args:
        nodes: Top-level nodes to serialize.

    Returns:
        str: The serialized fragment.
    """
    return "".join(str(node) for node in nodes)