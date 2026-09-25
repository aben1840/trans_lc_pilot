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
    """

    number: int
    title: str
    html: str = ""

    @property
    def is_preamble(self) -> bool:
        """Whether this piece is the content before the first heading."""
        return self.number == 0
