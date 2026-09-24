"""Split a document into articles at headings.

Two split paths live side-by-side here:

* :func:`split_by_headings` — operates on the HTML fragment mammoth
  produces; the legacy path used by the default CLI. Kept because the
  LangChain agent still talks HTML upstream and we do not want to break
  that mid-flight.

* :func:`split_blocks_by_headings` — operates on :class:`Block` lists
  directly. The new path; it does not need HTML at all and so works for
  any reader (docx via python-docx, PDF via pdfplumber, plain-text).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from bs4 import BeautifulSoup, NavigableString, Tag

from .model import Block


@dataclass(frozen=True)
class Article:
    """One piece of a document, split at a heading.

    Either ``html`` or ``blocks`` is populated depending on which split
    path produced this article. Downstream code that writes to disk uses
    ``html``; code that wants to reason about or translate the structure
    uses ``blocks``.

    Attributes:
        number: ``0`` for the preamble, ``1..N`` for the articles.
        title: The heading text, or an empty string when there is none
            (the preamble, or a document that has no headings at all).
        html: The piece as an HTML fragment (legacy path). Empty string
            when this article was produced by :func:`split_blocks_by_headings`.
        blocks: The piece as a list of :class:`Block` (new path). Empty
            list when produced by :func:`split_by_headings`.
        docx_para_range: ``(first_para_idx, last_para_idx_inclusive)``
            of this article in the original docx's paragraph list, or
            ``None`` when the reader did not supply the information.
            Used by backfill writers to locate the article's region.
    """

    number: int
    title: str
    html: str = ""
    blocks: list[Block] = field(default_factory=list)
    docx_para_range: tuple[int, int] | None = None

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


def split_blocks_by_headings(blocks: list[Block], level: int = 1) -> list[Article]:
    """Split a :class:`Block` list into articles at each heading of ``level``.

    Semantically identical to :func:`split_by_headings` — same preamble
    rule, same single-article fallback when no headings match — but
    consumes :class:`Block` objects rather than HTML fragments. This
    makes it work for any reader, not just docx mammoth.

    Args:
        blocks: Ordered list of blocks in reading order.
        level: Heading level to split on, 1-6.

    Returns:
        list[Article]: Pieces in document order. Each article carries
        its ``blocks`` populated; ``html`` is empty.
    """
    heading_positions = [
        i for i, b in enumerate(blocks)
        if b.kind == "heading" and b.level == level
    ]

    articles: list[Article] = []
    if heading_positions and heading_positions[0] > 0:
        articles.append(Article(
            number=0,
            title="",
            blocks=list(blocks[: heading_positions[0]]),
        ))

    number = 1
    for pos, start in enumerate(heading_positions):
        end = (
            heading_positions[pos + 1]
            if pos + 1 < len(heading_positions)
            else len(blocks)
        )
        chunk = blocks[start:end]
        articles.append(Article(
            number=number,
            title=chunk[0].text,
            blocks=list(chunk),
            docx_para_range=_range_of_docx_para_idx(chunk),
        ))
        number += 1

    if not heading_positions:
        articles.append(Article(
            number=1,
            title="",
            blocks=list(blocks),
        ))

    return articles


def heading_counts_for_blocks(blocks: list[Block]) -> dict[int, int]:
    """Count top-level headings by level in a :class:`Block` list.

    Same semantics as :func:`heading_counts` but operates directly on
    blocks. Useful as a level-picker for callers that have a
    :class:`DocProj` already — no need to serialize HTML just to count
    headings.

    Args:
        blocks: Ordered list of blocks.

    Returns:
        dict[int, int]: Heading level (1-6) mapped to how many blocks
        of ``kind="heading"`` carry that level. Absent levels mean no
        headings at that level.
    """
    counts: dict[int, int] = {}
    for b in blocks:
        if b.kind == "heading" and b.level is not None:
            counts[b.level] = counts.get(b.level, 0) + 1
    return counts


def _range_of_docx_para_idx(blocks: list[Block]) -> tuple[int, int] | None:
    """Return the ``(min, max)`` of ``docx_para_idx`` across ``blocks``.

    Returns ``None`` when no block carries a ``docx_para_idx`` — which
    is the case for PDF readers or plain-text readers that do not map
    blocks back to an OOXML paragraph index.
    """
    indices = [b.docx_para_idx for b in blocks if b.docx_para_idx is not None]
    if not indices:
        return None
    return (min(indices), max(indices))
