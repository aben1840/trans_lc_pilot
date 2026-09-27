"""Document processing: load a docx, split it into a bundle, assemble it back.

:func:`read` pairs a source file with the HTML fragment mammoth produces
from it; :mod:`~trans_lc_pilot.docproj.html_headings` splits that
fragment at headings; :mod:`~trans_lc_pilot.docproj.bundle` persists a
split as a directory of editable pieces whose association is recorded in
a manifest, and rebuilds a docx from one, taking its styles from the
bundled template.

Typical usage::

    from trans_lc_pilot.docproj import read, split_by_headings

    doc = read("input.docx")
    articles = split_by_headings(doc.fragment, level=1)
"""
from __future__ import annotations

from . import bundle, docx_body, docx_styles, html_headings, presentation
from .article import Article
from .bundle import (
    AssemblyResult,
    Bundle,
    BundleError,
    Findings,
    PieceEntry,
    TemplateRef,
    assemble_docx,
    read_bundle,
    validate,
    write_bundle,
)
from .html_headings import heading_counts, split_by_headings
from .source_doc import SourceDoc, read

__all__ = [
    "Article",
    "AssemblyResult",
    "Bundle",
    "BundleError",
    "Findings",
    "PieceEntry",
    "SourceDoc",
    "TemplateRef",
    "assemble_docx",
    "bundle",
    "docx_body",
    "docx_styles",
    "heading_counts",
    "html_headings",
    "presentation",
    "read",
    "read_bundle",
    "split_by_headings",
    "validate",
    "write_bundle",
]
