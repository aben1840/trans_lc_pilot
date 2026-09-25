"""Docx writer: backfill into the original file, or build a new one.

The backfill strategy is deliberately conservative — it edits only what
it knows it can edit safely and falls back to "clear + rebuild a single
run" for anything ambiguous. The goal is "text changes, formatting stays"
for the common case (span count == run count), not perfection for every
edge case Word can produce.
"""
from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.shared import Pt

from ..document import (
    Cell,
    DocProj,
    HeadingBlock,
    ImageBlock,
    ParagraphBlock,
    Span,
    TableBlock,
)
from . import register_writer

_EMU_PER_PT = 12700.0


def write_docx(
    proj: DocProj,
    output_path: Path,
    *,
    original_path: Path | None = None,
) -> None:
    """Write a :class:`DocProj` to a ``.docx`` file.

    Args:
        proj: Projection to write.
        output_path: Where to write the output.
        original_path: Optional path to the original source docx. When
            provided, the writer opens that file in backfill mode and
            edits paragraphs in place, preserving all OOXML formatting.
            When absent, a fresh document is built from the blocks.
    """
    if original_path is not None:
        _assemble_by_backfill(proj, original_path, output_path)
    else:
        _build_from_scratch(proj, output_path)


write_docx._supports_backfill = True  # type: ignore[attr-defined]


def _assemble_by_backfill(proj: DocProj, original: Path, output: Path) -> None:
    """Open ``original``, edit paragraphs in place, save to ``output``."""
    doc = Document(str(original))
    para_blocks: dict[int, ParagraphBlock] = {}
    for b in proj.blocks:
        if b.docx_para_idx is not None and isinstance(b, ParagraphBlock):
            para_blocks[b.docx_para_idx] = b

    for idx, block in para_blocks.items():
        if idx < len(doc.paragraphs):
            _replace_para_text(doc.paragraphs[idx], block)

    doc.save(str(output))


def _replace_para_text(para, block: ParagraphBlock) -> None:
    """Replace the text of ``para`` with ``block.text``, preserving format.

    Strategy:

    1. If the block carries spans that match the existing runs 1:1 —
       replace each run's text in place. Formatting is untouched.
    2. Otherwise — clear all runs and rebuild the paragraph from
       ``block.spans``, preserving paragraph-level attributes (style,
       alignment, indents).
    3. Fallback — just set ``para.text`` and hope for the best. This
       last-resort path is only hit when spans are ``None`` entirely.
    """
    if block.spans and len(block.spans) == len(para.runs):
        _replace_runs_1to1(para, block.spans)
        return

    if block.spans:
        _rebuild_para_from_spans(para, block.spans)
        return

    para.text = block.text


def _replace_runs_1to1(para, spans: list[Span]) -> None:
    """Set each run's text to the corresponding span's text.

    All run-level formatting — bold, italic, underline, font name /
    size / color — stays exactly as it was in the original docx.
    """
    for run, span in zip(para.runs, spans, strict=True):
        run.text = span.text


def _rebuild_para_from_spans(para, spans: list[Span]) -> None:
    """Clear all runs and rebuild from ``spans``.

    The paragraph's style, alignment, and paragraph_format are left
    untouched — only the runs inside are replaced. Each span becomes
    one run with formatting applied from the span's fields.
    """
    for run in list(para.runs):
        run._element.getparent().remove(run._element)

    for span in spans:
        run = para.add_run(span.text)
        if span.bold:
            run.bold = True
        if span.italic:
            run.italic = True
        if span.underline:
            run.underline = True
        if span.font_name:
            run.font.name = span.font_name
        if span.font_size_pt is not None:
            run.font.size = Pt(span.font_size_pt)
        if span.color_rgb:
            try:
                from docx.shared import RGBColor
                run.font.color.rgb = RGBColor.from_string(span.color_rgb)
            except (ValueError, AttributeError):
                pass


def _build_from_scratch(proj: DocProj, output: Path) -> None:
    """Build a brand-new docx from ``proj.blocks``."""
    doc = Document()

    for block in proj.blocks:
        if isinstance(block, HeadingBlock):
            para = doc.add_heading(block.text, level=block.level)
        elif isinstance(block, TableBlock) and block.rows:
            n_rows = len(block.rows)
            n_cols = max((len(r) for r in block.rows), default=0)
            table = doc.add_table(rows=n_rows, cols=n_cols)
            table.style = "Table Grid"
            for r_idx, row in enumerate(block.rows):
                for c_idx, cell in enumerate(row):
                    if c_idx < len(table.rows[r_idx].cells):
                        _write_cell(table.rows[r_idx].cells[c_idx], cell)
            continue
        elif isinstance(block, ImageBlock):
            doc.add_paragraph(f"[image placeholder: {block.text!r}]")
            continue
        elif isinstance(block, ParagraphBlock):
            para = doc.add_paragraph()

            if block.spans:
                _rebuild_para_from_spans(para, block.spans)
            else:
                para.add_run(block.text)

            if block.align == "center":
                para.alignment = 1  # WD_ALIGN_PARAGRAPH.CENTER
            elif block.align == "right":
                para.alignment = 2
            elif block.align == "justify":
                para.alignment = 3

    doc.save(str(output))


def _write_cell(cell_element, cell: Cell) -> None:
    """Populate one docx table cell from a :class:`Cell`."""
    cell_element.text = ""
    for span in cell.spans:
        para = (
            paragraphs[0]
            if (paragraphs := cell_element.paragraphs)
            else cell_element.add_paragraph()
        )
        if para.text:
            para = cell_element.add_paragraph()
        run = para.add_run(span.text)
        if span.bold:
            run.bold = True
        if span.italic:
            run.italic = True
        if span.underline:
            run.underline = True
        if span.font_name:
            run.font.name = span.font_name
        if span.font_size_pt is not None:
            run.font.size = Pt(span.font_size_pt)
        if span.color_rgb:
            try:
                from docx.shared import RGBColor
                run.font.color.rgb = RGBColor.from_string(span.color_rgb)
            except (ValueError, AttributeError):
                pass


register_writer("docx", write_docx)
