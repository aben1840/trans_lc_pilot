"""Document Projection (DocProj): a format-agnostic view of a document.

The canonical data lives in :class:`DocProj` (a dataclass). HTML is the
first concrete rendering; Markdown and JSON are reserved for future
steps and currently raise :class:`NotImplementedError`.

:meth:`DocProj.source_fragment` is a distinct path: it renders the
originating docx via mammoth (bypassing :attr:`blocks`) to produce the
HTML a reader sees — useful for downstream tools that expect raw HTML.

Format fidelity lives at three levels:

* **Block hierarchy** — :class:`Block` base with subclasses
  :class:`ParagraphBlock`, :class:`HeadingBlock`, :class:`TableBlock`,
  :class:`ImageBlock`. Each subtype owns only the fields that make sense
  for it, so consumers get static type guarantees.
* **Span**  — run-level inline formatting inside a paragraph/heading.
* **Cell**  — table cell with its own spans.

Span and Cell are frozen (format facts do not mutate); the Block
subclasses are mutable because translation edits text in place.
"""
from __future__ import annotations

from abc import ABC
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import mammoth


@dataclass(frozen=True)
class Span:
    """A run-level inline fragment with its formatting.

    Invariant across the containing :class:`ParagraphBlock` /
    :class:`HeadingBlock`:
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
class Block(ABC):
    """Abstract base for all block types.

    Holds only the fields common to every block subtype. The ``kind``
    attribute is set by each subclass as a fixed string — consumers
    should prefer ``isinstance`` checks over string comparison.

    ``Block`` itself cannot be instantiated. Use one of the concrete
    subclasses: :class:`ParagraphBlock`, :class:`HeadingBlock`,
    :class:`TableBlock`, or :class:`ImageBlock`.

    Attributes:
        idx: Zero-based position in :attr:`DocProj.blocks`.
        text: Plain-text content of the block. Empty string when not
            applicable (e.g. bare images).
        kind: Discriminator string. Subclasses override this as a class
            attribute (see :class:`ParagraphBlock`, :class:`HeadingBlock`,
            :class:`TableBlock`, :class:`ImageBlock`).
        page_index: Zero-based page number the block appears on. Docx
            has no explicit pagination; readers estimate this.
        has_image: ``True`` if the block contains at least one image.
        in_table: ``True`` if the block originates inside a table.
        bbox: Optional ``(x, y, width, height)`` in PDF points; ``None``
            for docx-sourced blocks.
        kind_confidence: Reader's confidence in the block's classification,
            in ``[0.0, 1.0]``. ``1.0`` for docx ground truth.
        signals: Reader-specific tags explaining how the block was
            classified (e.g. ``["python_docx_reader", "style_id:Heading1"]``).
    """

    idx: int
    text: str = ""
    kind: str = ""
    page_index: int = 0
    has_image: bool = False
    in_table: bool = False
    bbox: tuple[float, float, float, float] | None = None
    kind_confidence: float = 1.0
    signals: list[str] = field(default_factory=list)

    def __new__(cls, *args, **kwargs):
        """Prevents direct instantiation of the abstract base."""
        if cls is Block:
            raise TypeError(
                "Block is abstract — instantiate ParagraphBlock, "
                "HeadingBlock, TableBlock, or ImageBlock instead"
            )
        return super().__new__(cls)


@dataclass
class ParagraphBlock(Block):
    """A paragraph-level block with inline formatting.

    ``spans`` is always populated (defaulting to an empty list for
    readers that cannot extract run-level detail). ``align``, indents,
    and spacing remain optional because not every paragraph carries them.

    Attributes:
        spans: Run-level inline formatting. Consistent with ``text``.
        align: Paragraph alignment — ``"left"``, ``"center"``,
            ``"right"``, ``"justify"`` — or ``None`` when unknown.
        indent_first_line_pt: First-line indent in pt, or ``None``.
        line_spacing: Line-spacing factor (e.g. ``2.0`` for double), or
            ``None`` when not set.
        space_before_pt: Space before the paragraph in pt, or ``None``.
        space_after_pt: Space after the paragraph in pt, or ``None``.
        style_hint: Reader-supplied style label (e.g. ``"Normal"``).
            ``None`` when not applicable.
        docx_para_idx: Index into the original ``doc.paragraphs`` list.
            Only set by the python-docx reader; used for backfill
            writers. ``None`` for non-docx sources.
    """

    kind: str = "paragraph"
    spans: list[Span] = field(default_factory=list)
    align: str | None = None
    indent_first_line_pt: float | None = None
    line_spacing: float | None = None
    space_before_pt: float | None = None
    space_after_pt: float | None = None
    style_hint: str | None = None
    docx_para_idx: int | None = None


@dataclass
class HeadingBlock(ParagraphBlock):
    """A heading — a paragraph with a heading level.

    Inherits all paragraph-level formatting (spans, alignment, spacing)
    because headings are styled paragraphs.

    Attributes:
        level: Heading level (1-6). Always set — no ``None`` case here.
        level_confidence: Reader's confidence in the ``level`` assignment,
            in ``[0.0, 1.0]``. ``1.0`` for docx ground truth.
    """

    kind: str = "heading"
    level: int = 1
    level_confidence: float = 1.0


@dataclass
class TableBlock(Block):
    """A table — a 2-D grid of :class:`Cell` objects.

    ``rows`` is always populated (defaulting to an empty grid for
    readers that cannot extract table structure). Paragraph-level
    formatting (spans, align) does not apply — that lives on the cells.

    Attributes:
        rows: Table structure, a 2-D list of :class:`Cell`.
        style_hint: Reader-supplied style label (e.g. ``"Table Grid"``).
            ``None`` when not applicable.
        docx_para_idx: Index of the anchor paragraph in the original
            docx (the paragraph immediately before the table). Used for
            positioning by backfill writers. ``None`` for non-docx sources.
    """

    kind: str = "table"
    rows: list[list[Cell]] = field(default_factory=list)
    style_hint: str | None = None
    docx_para_idx: int | None = None


@dataclass
class ImageBlock(Block):
    """A bare image block — no text, no inline formatting.

    Carries only base-class fields plus an optional image format tag.
    """

    kind: str = "image"
    image_format: str | None = None


@dataclass
class DocProj:
    """Format-agnostic projection of a document.

    Attributes:
        source_path: Path to the originating file on disk.
        source_format: Origin format (e.g. ``"docx"``, ``"pdf"``).
        blocks: Ordered list of blocks in reading order. Items are one of
            :class:`ParagraphBlock`, :class:`HeadingBlock`,
            :class:`TableBlock`, or :class:`ImageBlock`.
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

    def source_fragment(self) -> str:
        """Return the HTML fragment mammoth produces from the source docx.

        This bypasses :attr:`blocks` — it re-converts the originating
        file from scratch. The result is the document as a reader sees
        it, with empty paragraphs preserved so blank lines survive the
        conversion.

        mammoth is re-run on each call rather than cached in
        :attr:`metadata`: it is cheap, and caching would inflate every
        projection with HTML that most callers never ask for.

        Returns:
            str: HTML fragment, with no ``<html>`` or ``<body>`` wrapper.

        Raises:
            FileNotFoundError: If :attr:`source_path` is no longer there.
            OSError: On read failure.
        """
        with self.source_path.open("rb") as f:
            result = mammoth.convert_to_html(f, ignore_empty_paragraphs=False)
        return result.value


Renderer = Callable[[DocProj], str]
RENDERERS: dict[str, Renderer] = {}


def register_renderer(fmt: str, fn: Renderer) -> None:
    """Register a renderer under the given format name.

    Args:
        fmt: Format identifier (e.g. ``"html"``, ``"markdown"``).
        fn: Callable that turns a :class:`DocProj` into a string.
    """
    RENDERERS[fmt] = fn
