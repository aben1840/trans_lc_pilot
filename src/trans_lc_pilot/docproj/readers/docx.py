"""Read a .docx file into a :class:`DocProj` via mammoth + BeautifulSoup.

Pipeline:
    docx → mammoth.convert_to_html → HTML string →
    BeautifulSoup parse → walk top-level elements → Block list

Mammoth performs the OOXML → semantic HTML conversion; BeautifulSoup
walks the resulting fragment and groups cells into one block per
top-level element (heading, paragraph, table, image).
"""
from __future__ import annotations

from pathlib import Path

import mammoth
from bs4 import BeautifulSoup, NavigableString, Tag

from ..model import Block, DocProj
from . import register_reader


def docx_to_docproj(path: str | Path) -> DocProj:
    """Convert a .docx file to a :class:`DocProj`.

    Args:
        path: Path to the .docx file.

    Returns:
        DocProj: A populated projection. All blocks carry
        ``kind_confidence=1.0`` because docx classification is treated
        as ground truth.

    Raises:
        FileNotFoundError: If ``path`` does not exist.
        ValueError: If ``path`` does not have a ``.docx`` extension.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(p)
    if p.suffix.lower() != ".docx":
        raise ValueError(f"Expected .docx extension, got {p.suffix!r}")

    with p.open("rb") as f:
        result = mammoth.convert_to_html(f)
    html = result.value

    blocks = _html_to_blocks(html)

    return DocProj(
        source_path=p,
        source_format="docx",
        blocks=blocks,
        metadata={
            "mammoth_messages": [str(m) for m in result.messages],
            "source_html_chars": len(html),
        },
    )


def _html_to_blocks(html: str) -> list[Block]:
    """Walk top-level elements of an HTML fragment and produce Blocks.

    mammoth emits an HTML fragment (no ``<html>`` / ``<body>`` wrapper);
    BeautifulSoup parses it and we iterate over direct children of the
    root.
    """
    soup = BeautifulSoup(html, "html.parser")
    root = soup.body if soup.body is not None else soup

    blocks: list[Block] = []
    for elem in root.children:
        if isinstance(elem, NavigableString):
            text = str(elem).strip()
            if text:
                blocks.append(
                    Block(
                        idx=len(blocks),
                        kind="paragraph",
                        text=text,
                        kind_confidence=0.9,
                        signals=["plain_text_node"],
                    )
                )
        elif isinstance(elem, Tag):
            block = _tag_to_block(elem, idx=len(blocks))
            if block is not None:
                blocks.append(block)
    return blocks


def _tag_to_block(tag: Tag, *, idx: int) -> Block | None:
    """Convert one top-level HTML tag to a single :class:`Block`.

    Returns ``None`` for empty elements (whitespace-only paragraphs).
    """
    name = tag.name.lower()
    text = tag.get_text(" ", strip=True)

    if name in {"h1", "h2", "h3", "h4", "h5", "h6"}:
        if text:
            block = Block(
                idx=idx,
                kind="heading",
                level=int(name[1]),
                style_hint=name,
                text=text,
                kind_confidence=1.0,
                level_confidence=1.0,
                signals=["mammoth_conversion", f"tag:{name}"],
            )
        else:
            block = None
    elif name == "p":
        if text or tag.find("img"):
            block = Block(
                idx=idx,
                kind="paragraph",
                text=text,
                has_image=bool(tag.find("img")),
                kind_confidence=1.0,
                signals=["mammoth_conversion", "tag:p"],
            )
        else:
            block = None
    elif name == "table":
        block = Block(
            idx=idx,
            kind="table",
            text=_table_to_text(tag),
            in_table=True,
            kind_confidence=1.0,
            signals=["mammoth_conversion", "tag:table"],
        )
    elif name == "img":
        block = Block(
            idx=idx,
            kind="image",
            has_image=True,
            kind_confidence=1.0,
            signals=["mammoth_conversion", "tag:img"],
        )
    elif text:
        block = Block(
            idx=idx,
            kind="paragraph",
            text=text,
            kind_confidence=0.7,
            signals=["mammoth_conversion", f"unknown_tag:{name}"],
        )
    else:
        block = None
    return block


def _table_to_text(table_tag: Tag) -> str:
    """Flatten a ``<table>`` to a multi-line text representation.

    Each ``<tr>`` becomes one line; cells are joined with ``" | "``.
    """
    lines: list[str] = []
    for tr in table_tag.find_all("tr"):
        cells = [cell.get_text(" ", strip=True) for cell in tr.find_all(["td", "th"])]
        lines.append(" | ".join(cells))
    return "\n".join(lines)


register_reader("docx", docx_to_docproj)
