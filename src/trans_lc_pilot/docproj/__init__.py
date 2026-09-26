"""Document Projection (DocProj): a format-agnostic view of a document.

The canonical data lives in :class:`DocProj` (a dataclass). HTML is the
first concrete rendering; Markdown and JSON are reserved for future
steps and currently raise :class:`NotImplementedError`.

Typical usage::

    from trans_lc_pilot.docproj import read

    proj = read("input.docx")
    html = proj.render("html")
    # proj.render("markdown")  # raises NotImplementedError today
"""
from __future__ import annotations

from . import html_headings, presentation
from .document import RENDERERS, Block, DocProj, Renderer, register_renderer
from .inspection import render_html, render_json, render_markdown
from .readers import READERS, Reader, read, register_reader
from .html_headings import (
    Article,
    heading_counts,
    split_by_headings,
)