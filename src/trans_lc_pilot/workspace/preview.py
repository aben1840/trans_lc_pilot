"""The HTML preview ``trans-lc-pilot preview`` puts in front of a reader.

Separate from :mod:`trans_lc_pilot.docproj.presentation`, which
serializes HTML but knows nothing about where a workspace keeps things.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

from ..docproj.presentation import wrap_as_document
from ..docproj.source_doc import SourceDoc
from .layout import Workspace

PREFIX = "docproj-source-"


def write_preview(doc: SourceDoc, workspace: Workspace) -> Path:
    """Write ``doc``'s HTML fragment to a fresh file in workspace scratch.

    The output is the raw HTML mammoth generates from the docx — the
    document as a reader sees it — wrapped in a standalone document so
    that preserved empty ``<p>`` elements render as blank lines.

    A new file per call, never overwritten and never cleaned up: a
    preview is a glance at one conversion, not a work product.

    Args:
        doc: The source document to write.
        workspace: Whose scratch directory receives the file.

    Returns:
        Path: Path of the written HTML file.

    Raises:
        OSError: On I/O failure while creating or writing the file.
    """
    workspace.tmp.mkdir(parents=True, exist_ok=True)
    html = wrap_as_document(doc.fragment, title=f"Source: {doc.path.name}")

    fd, name = tempfile.mkstemp(
        prefix=PREFIX, suffix=".html", dir=workspace.tmp
    )
    os.close(fd)
    path = Path(name)
    path.write_text(html, encoding="utf-8")
    return path
