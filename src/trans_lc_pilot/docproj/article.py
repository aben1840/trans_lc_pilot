"""Data model for an article split from a document."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Article:
    """One piece of a document, split at a heading.

    Attributes:
        number: ``0`` for the preamble, ``1..N`` for the articles.
        title: The heading text, or an empty string when there is none
            (the preamble, or a document that has no headings at all).
        html: The piece as an HTML fragment.
        block_indices: Indices into :attr:`DocProj.blocks` covered by
            this article. Populated only by :func:`split_docproj_by_headings`
            (路线 A); empty for :func:`split_by_headings` (路线 B).
        docx_para_indices: Values of ``docx_para_idx`` on the
            :class:`ParagraphBlock` items this article covers. Same
            population rule as ``block_indices``.
        docx_table_indices: Values of ``docx_table_idx`` on the
            :class:`TableBlock` items this article covers. Same
            population rule as ``block_indices``.
    """

    number: int
    title: str
    html: str = ""
    block_indices: tuple[int, ...] = ()
    docx_para_indices: tuple[int, ...] = ()
    docx_table_indices: tuple[int, ...] = ()

    @property
    def is_preamble(self) -> bool:
        """Whether this piece is the content before the first heading."""
        return self.number == 0

    @property
    def has_anchors(self) -> bool:
        """Whether this article carries backfill anchors (路线 A)."""
        return bool(self.block_indices)
