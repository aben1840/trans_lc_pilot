"""Document Projection (DocProj): a format-agnostic view of a document.

The canonical data lives in :class:`DocProj` (a dataclass). HTML is the
first concrete rendering; Markdown and JSON are reserved for future
steps and currently raise :class:`NotImplementedError`.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Block:
    """A single block in the document.

    Blocks cover the coarse-grained elements a downstream split-decision
    needs: headings, paragraphs, tables, and images. Run-level formatting
    is intentionally not modeled — DocProj is a *projection*, not a full
    document tree.

    Attributes:
        idx: Zero-based position in :attr:`DocProj.blocks`.
        kind: One of ``"heading"``, ``"paragraph"``, ``"table"``,
            ``"image"``.
        level: Heading level (1-6) when ``kind == "heading"``; ``None``
            otherwise.
        style_hint: Reader-supplied style label (e.g. ``"h1"``,
            ``"title"``, ``"body"``). ``None`` when not applicable.
        text: Plain-text content of the block (concatenated for tables).
            Empty string when not applicable (e.g. for bare images).
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
            classified (e.g. ``["mammoth_conversion", "tag:h1"]``).
    """

    idx: int
    kind: str
    level: int | None = None
    style_hint: str | None = None
    text: str = ""
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
