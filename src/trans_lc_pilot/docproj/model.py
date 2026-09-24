"""Document Projection (DocProj): a format-agnostic view of a document.

The canonical data lives in :class:`DocProj` (a dataclass). HTML is the
first concrete rendering; Markdown and JSON are reserved for future
steps and currently raise :class:`NotImplementedError`.

Format fidelity lives at three levels:

* **Block** — coarse structure (heading / paragraph / table / image)
* **Span**  — run-level inline formatting inside a block
* **Cell**  — table cell with its own spans

All three are dataclasses with optional fields; omitting them is the
normal path for readers that cannot extract the detail (e.g. PDF
readers infer bold from fontname heuristics, plain-text readers leave
spans as ``None``).
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Span:
    """A run-level inline fragment with its formatting.

    Invariant across the containing :class:`Block`:
    ``"".join(s.text for s in block.spans) == block.text``.

    Format attributes that are ``False`` / ``None`` mean "not set" —
    the value falls back to whatever enclosing style the reader did or
    did not capture.
    """

    text: str
    bold: bool = False
    italic: bool = False
    underline: bool = False
    font_name: str | None = None
    font_size_pt: float | None = None
    color_rgb: str | None = None

    @property
    def is_plain(self) -> bool:
        """Whether this span carries no explicit formatting."""
        return not any(
            [
                self.bold,
                self.italic,
                self.underline,
                self.font_name is not None,
                self.font_size_pt is not None,
                self.color_rgb is not None,
            ]
        )


@dataclass(frozen=True)
class Cell:
    """A single table cell.

    A cell carries its inline spans — the writer is responsible for
    turning them back into the output format's cell structure.
    """

    spans: tuple[Span, ...]
    row_span: int = 1
    col_span: int = 1

    @property
    def text(self) -> str:
        """Concatenated plain text of the cell."""
        return "".join(s.text for s in self.spans)


@dataclass
class Block:
    """A single block in the document.

    Blocks cover the coarse-grained elements a downstream split-decision
    needs: headings, paragraphs, tables, and images. Run-level formatting
    lives in :class:`Span` (attached via the optional ``spans`` field),
    table structure lives in ``rows`` (a 2-D grid of :class:`Cell`).

    ``spans``, ``rows``, and the paragraph-level attributes (``align``,
    indents, spacing) are all optional. Readers that cannot extract them
    (e.g. a plain-text reader) simply leave them ``None`` and consumers
    must tolerate that.

    ``docx_para_idx`` is set only by the python-docx reader and lets a
    writer locate the original OOXML paragraph for a backfill edit. PDF
    readers (and future formats) always leave it ``None``.

    Attributes:
        idx: Zero-based position in :attr:`DocProj.blocks`.
        kind: One of ``"heading"``, ``"paragraph"``, ``"table"``,
            ``"image"``.
        level: Heading level (1-6) when ``kind == "heading"``; ``None``
            otherwise.
        style_hint: Reader-supplied style label (e.g. ``"Heading 2"``,
            ``"Normal"``). ``None`` when not applicable.
        text: Plain-text content of the block (concatenated for tables).
            Empty string when not applicable (e.g. bare images).
        spans: Run-level inline formatting. Must be consistent with
            ``text``. ``None`` when the reader did not capture it.
        align: Paragraph alignment — ``"left"``, ``"center"``,
            ``"right"``, ``"justify"`` — or ``None`` when unknown.
        indent_first_line_pt: First-line indent in pt, or ``None``.
        line_spacing: Line-spacing factor (e.g. ``2.0`` for double), or
            ``None`` when not set.
        space_before_pt: Space before the paragraph in pt, or ``None``.
        space_after_pt: Space after the paragraph in pt, or ``None``.
        rows: Table structure, a 2-D list of :class:`Cell`. Only set when
            ``kind == "table"``; ``None`` otherwise.
        docx_para_idx: Index into the original ``doc.paragraphs`` list.
            Only set by the python-docx reader; used for backfill
            writers. ``None`` for non-docx sources.
        page_index: Zero-based page number the block appears on. Docx
            has no explicit pagination; readers estimate this.
        has_image: ``True`` if the block contains at least one image.
        in_table: ``True`` if the block originates inside a table.
        bbox: Optional ``(x, y, width, height)`` in PDF points; ``None``
            for docx-sourced blocks.
        kind_confidence: Reader's confidence in the ``kind`` assignment,
            in ``[0.0, 1.0]``. ``1.0`` for docx ground truth.
        level_confidence: Reader's confidence in the ``level`` for
            headings; ``None`` when not applicable.
        signals: Reader-specific tags explaining how the block was
            classified (e.g. ``["python_docx_reader", "style_id:Heading1"]``).
    """

    idx: int
    kind: str
    level: int | None = None
    style_hint: str | None = None
    text: str = ""
    spans: list[Span] | None = None
    align: str | None = None
    indent_first_line_pt: float | None = None
    line_spacing: float | None = None
    space_before_pt: float | None = None
    space_after_pt: float | None = None
    rows: list[list[Cell]] | None = None
    docx_para_idx: int | None = None
    page_index: int = 0
    has_image: bool = False
    in_table: bool = False
    bbox: tuple[float, float, float, float] | None = None
    kind_confidence: float = 1.0
    level_confidence: float | None = None
    signals: list[str] = field(default_factory=list)


@dataclass
class DocProj:
    """Format-agnostic projection of a document.

    Attributes:
        source_path: Path to the originating file on disk.
        source_format: Origin format (e.g. ``"docx"``, ``"pdf"``).
        blocks: Ordered list of blocks in reading order.
        metadata: Reader-supplied extras (warnings, raw HTML length,
            page count hint, etc.). Not part of the stable schema.
    """

    source_path: Path
    source_format: str
    blocks: list[Block]
    metadata: dict = field(default_factory=dict)

    def render(self, fmt: str = "html") -> str:
        """Render this DocProj to the requested representation.

        Args:
            fmt: One of the registered renderer names. ``"html"`` is
                available today; ``"markdown"`` and ``"json"`` are
                reserved and raise :class:`NotImplementedError`.

        Returns:
            str: The rendered document.

        Raises:
            NotImplementedError: If no renderer is registered for
                ``fmt``.
        """
        renderer = RENDERERS.get(fmt)
        if renderer is None:
            raise NotImplementedError(
                f"No renderer registered for {fmt!r}; "
                f"available: {sorted(RENDERERS)}"
            )
        return renderer(self)


Renderer = Callable[[DocProj], str]
RENDERERS: dict[str, Renderer] = {}


def register_renderer(fmt: str, fn: Renderer) -> None:
    """Register a renderer under the given format name.

    Args:
        fmt: Format identifier (e.g. ``"html"``, ``"markdown"``).
        fn: Callable that turns a :class:`DocProj` into a string.
    """
    RENDERERS[fmt] = fn
