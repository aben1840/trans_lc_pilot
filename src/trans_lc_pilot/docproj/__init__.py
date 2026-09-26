"""Document processing: load a docx, split it at headings, write the pieces.

:func:`read` pairs a source file with the HTML fragment mammoth
produces from it; :mod:`~trans_lc_pilot.docproj.html_headings` splits
that fragment at headings;
:mod:`~trans_lc_pilot.docproj.presentation` writes the results to disk
and opens them in a browser.

Typical usage::

    from trans_lc_pilot.docproj import read, split_by_headings

    doc = read("input.docx")
    articles = split_by_headings(doc.fragment, level=1)
"""
from __future__ import annotations

from . import html_headings, presentation
from .article import Article
from .html_headings import heading_counts, split_by_headings
from .source import SourceDoc, read

__all__ = [
    "Article",
    "SourceDoc",
    "heading_counts",
    "html_headings",
    "presentation",
    "read",
    "split_by_headings",
]
