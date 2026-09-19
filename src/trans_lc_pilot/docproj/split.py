"""Split a document into articles at headings.

Operates on the HTML fragment mammoth produces, so each article keeps
whatever formatting a reader sees — bold runs, tables, images — rather
than being reconstructed from parsed blocks.
"""
from __future__ import annotations

from dataclasses import dataclass

from bs4 import BeautifulSoup, NavigableString, Tag


@dataclass(frozen=True)
class Article:
    """One piece of a document, split at a heading.

    Attributes:
        number: ``0`` for the preamble, ``1..N`` for the articles.
        title: The heading text, or an empty string when there is none
            (the preamble, or a document that has no headings at all).
        html: The piece as an HTML fragment.
    """

    number: int
    title: str
    html: str

    @property
    def is_preamble(self) -> bool:
        """Whether this piece is the content before the first heading."""
        return self.number == 0


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
