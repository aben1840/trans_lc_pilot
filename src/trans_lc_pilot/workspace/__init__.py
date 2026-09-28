"""The root directory every artifact of one working set lives under.

A workspace fixes what :mod:`trans_lc_pilot.docproj` deliberately does
not: where things go. ``docproj`` acts on the paths a caller hands it;
this package decides those paths, ingests the source documents they
derive from, and renders the aggregate view over the result.

Layout::

    <workspace>/
      index.html        aggregate view of every bundle
      sources/          ingested source documents, and .origins.json
      bundles/          one directory per (source, heading level)
      output/           docx assembled from a bundle
      .tmp/             HTML previews written by ``trans-lc-pilot preview``
"""
from __future__ import annotations

from .index import Entry, render_index, write_index
from .ingest import IngestError, Source, ingest, list_sources, read_origins
from .layout import (
    BUNDLES_DIR,
    INDEX_NAME,
    ORIGINS_NAME,
    OUTPUT_DIR,
    SOURCES_DIR,
    TMP_DIR,
    Workspace,
)
from .preview import write_preview

__all__ = [
    "BUNDLES_DIR",
    "INDEX_NAME",
    "ORIGINS_NAME",
    "OUTPUT_DIR",
    "SOURCES_DIR",
    "TMP_DIR",
    "Entry",
    "IngestError",
    "Source",
    "Workspace",
    "ingest",
    "list_sources",
    "read_origins",
    "render_index",
    "write_index",
    "write_preview",
]
