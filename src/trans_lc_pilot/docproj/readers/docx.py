"""Read a .docx file into a :class:`DocProj` via python-docx.

Pipeline:
    docx → Document(str(path)) → walk doc.element.body children (OOXML order)
    → paragraph → run-level Span extraction
    → table → Cell grid extraction

python-docx is used directly (no mammoth intermediate step) so that
run-level formatting — bold, italic, underline, font name / size / color,
paragraph alignment, indents, spacing — is preserved in the resulting
:class:`Block` tree. These are things mammoth silently discards, making
them unavailable to writers that need to reconstruct the source (e.g.
a "translate in place" writer that edits the original docx).

Heading identification reads ``p.style.style_id`` (e.g. ``"Heading1"``)
rather than the localized ``style.name`` so it works regardless of the
Word UI language that created the document.
"""
from __future__ import annotations

import re
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Emu

from ..document import (
    Block,
    Cell,
    DocProj,
    HeadingBlock,
    ParagraphBlock,
    Span,
    TableBlock,
)
from . import register_reader

_EMU_PER_PT = 12700.0  # Word stores sizes in English Metric Units


def _emu_to_pt(value: Emu | float | None) -> float | None:
    """Convert an EMU length to pt; returns ``None`` when input is falsy."""
    if value is None:
        return None
    return float(value) / _EMU_PER_PT


_ALIGN_MAP = {
    WD_ALIGN_PARAGRAPH.LEFT: "left",
    WD_ALIGN_PARAGRAPH.CENTER: "center",
    WD_ALIGN_PARAGRAPH.RIGHT: "right",
    WD_ALIGN_PARAGRAPH.JUSTIFY: "justify",
    WD_ALIGN_PARAGRAPH.DISTRIBUTE: "justify",
}


def docx_to_docproj(path: str | Path) -> DocProj:
    """Convert a .docx file to a :class:`DocProj`.

    Args:
        path: Path to the .docx file.

    Returns:
        DocProj: A populated projection. Run-level formatting is
        captured as :class:`Span` objects attached to each block;
        paragraph-level attributes (alignment, indents, spacing) are
        attached directly to the :class:`Block`.

    Raises:
        FileNotFoundError: If ``path`` does not exist.
        ValueError: If ``path`` does not have a ``.docx`` extension.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(p)
    if p.suffix.lower() != ".docx":
        raise ValueError(f"Expected .docx extension, got {p.suffix!r}")

    doc = Document(str(p))
    blocks: list[Block] = []
    para_counter = 0
    block_idx = 0
    table_counter = 0

    table_elements = {tbl._tbl: tbl for tbl in doc.tables}

    for child in doc.element.body:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag

        if tag == "p":
            para = doc.paragraphs[para_counter]
            para_counter += 1
            block = _para_to_block(para, block_idx, docx_para_idx=para_counter - 1)
            if block is not None:
                blocks.append(block)
                block_idx += 1

        elif tag == "tbl":
            table = table_elements.get(child)
            if table is not None:
                blocks.append(
                    _table_to_block(table, block_idx, docx_table_idx=table_counter)
                )
                table_counter += 1
                block_idx += 1

    return DocProj(
        source_path=p,
        source_format="docx",
        blocks=blocks,
        metadata={
            "reader": "python-docx",
            "python_docx_para_count": para_counter,
            "python_docx_table_count": len(doc.tables),
        },
    )


def _para_to_block(para, idx: int, *, docx_para_idx: int) -> ParagraphBlock | None:
    """Turn one python-docx Paragraph into a paragraph or heading block.

    Returns ``None`` for paragraphs that are empty *and* carry no runs —
    these are the ones mammoth drops too, so we drop them here to keep
    the block count comparable between readers. Paragraphs that have
    runs but whose text strips to empty (e.g. whitespace-only) are still
    emitted: they may carry explicit formatting the writer needs.
    """
    style_id = ""
    style_name = None
    if para.style is not None:
        style_id = para.style.style_id or ""
        style_name = para.style.name

    m = re.match(r"Heading\s*(\d)", style_id, re.IGNORECASE)
    is_heading = bool(m)
    level = int(m.group(1)) if m else 1

    if not para.text.strip() and not para.runs:
        return None

    spans = _extract_spans(para.runs)

    align = _ALIGN_MAP.get(para.alignment) if para.alignment is not None else None

    pf = para.paragraph_format
    indent_first = (
        _emu_to_pt(pf.first_line_indent)
        if pf.first_line_indent is not None
        else None
    )
    if indent_first is not None and pf.left_indent is not None:
        indent_first -= _emu_to_pt(pf.left_indent) or 0

    common = {
        "idx": idx,
        "text": para.text,
        "spans": spans,
        "align": align,
        "indent_first_line_pt": indent_first,
        "line_spacing": pf.line_spacing,
        "space_before_pt": _emu_to_pt(pf.space_before),
        "space_after_pt": _emu_to_pt(pf.space_after),
        "style_hint": style_name,
        "docx_para_idx": docx_para_idx,
        "kind_confidence": 1.0,
        "signals": ["python_docx_reader", f"style_id:{style_id or 'None'}"],
    }

    if is_heading:
        return HeadingBlock(
            **common,
            level=level,
            level_confidence=1.0,
        )
    return ParagraphBlock(**common)


def _extract_spans(runs) -> list[Span]:
    """Turn a list of python-docx runs into :class:`Span` objects.

    Adjacent runs with identical formatting are merged to reduce noise —
    Word produces many tiny runs from edits, but the output model is
    happier when a single bold span is one :class:`Span`, not ten.
    """
    raw: list[Span] = []
    for run in runs:
        if not run.text:
            continue
        rgb = str(run.font.color.rgb) if (
            run.font.color is not None and run.font.color.rgb is not None
        ) else None
        raw.append(
            Span(
                text=run.text,
                bold=bool(run.bold),
                italic=bool(run.italic),
                underline=bool(run.underline),
                font_name=run.font.name,
                font_size_pt=_emu_to_pt(run.font.size),
                color_rgb=rgb,
            )
        )
    return _merge_adjacent(raw)


def _merge_adjacent(spans: list[Span]) -> list[Span]:
    """Merge consecutive spans that share the same formatting attributes.

    The text parts are concatenated; the formatting tuple is taken from
    the first span of each run.
    """
    if len(spans) <= 1:
        return spans

    merged: list[Span] = [spans[0]]
    for span in spans[1:]:
        last = merged[-1]
        if (
            last.bold == span.bold
            and last.italic == span.italic
            and last.underline == span.underline
            and last.font_name == span.font_name
            and last.font_size_pt == span.font_size_pt
            and last.color_rgb == span.color_rgb
        ):
            merged[-1] = Span(
                text=last.text + span.text,
                bold=last.bold,
                italic=last.italic,
                underline=last.underline,
                font_name=last.font_name,
                font_size_pt=last.font_size_pt,
                color_rgb=last.color_rgb,
            )
        else:
            merged.append(span)
    return merged


def _table_to_block(table, idx: int, *, docx_table_idx: int) -> TableBlock:
    """Turn one python-docx Table into a :class:`TableBlock` with a Cell grid."""
    rows: list[list[Cell]] = []
    text_lines: list[str] = []

    for row in table.rows:
        cells_row: list[Cell] = []
        cell_texts: list[str] = []
        for cell in row.cells:
            cell_spans: list[Span] = []
            for para in cell.paragraphs:
                cell_spans.extend(_extract_spans(para.runs))
            cells_row.append(Cell(spans=tuple(cell_spans)))
            cell_texts.append("".join(s.text for s in cell_spans))
        rows.append(cells_row)
        text_lines.append(" | ".join(cell_texts))

    return TableBlock(
        idx=idx,
        text="\n".join(text_lines),
        rows=rows,
        in_table=True,
        style_hint=table.style.name if table.style is not None else None,
        kind_confidence=1.0,
        signals=["python_docx_reader", "tag:tbl"],
        docx_table_idx=docx_table_idx,
    )


register_reader("docx", docx_to_docproj)
