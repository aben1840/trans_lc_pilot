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

from . import present
from .model import RENDERERS, Block, DocProj, Renderer, register_renderer
from .readers import READERS, Reader, read, register_reader
from .render import render_html, render_json, render_markdown

__all__ = [
    "READERS",
    "RENDERERS",
    "Block",
    "DocProj",
    "Reader",
    "Renderer",
    "present",
    "read",
    "register_reader",
    "register_renderer",
    "render_html",
    "render_json",
    "render_markdown",
]
