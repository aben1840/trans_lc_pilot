"""Registry of output format writers.

Writers turn a :class:`DocProj` back into a file on disk. Each writer
self-registers against a format identifier at import time.

Two writer strategies are supported today for docx:

* **Backfill** — open the original docx and edit it in place, replacing
  text while preserving the original OOXML formatting. This is the
  path to prefer when the caller has the original file because it keeps
  styles, images, headers/footers, and layout exactly intact.

* **Build from scratch** — construct a new docx from the blocks using
  python-docx's ``Document()``. Loses anything not captured in the
  projection (styles, headers/footers, page layout) but does not need
  the original file.
"""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from ..document import DocProj

Writer = Callable[[DocProj, Path], None]
WRITERS: dict[str, Writer] = {}


def register_writer(fmt: str, writer: Writer) -> None:
    """Register a writer under the given format name.

    Args:
        fmt: Format identifier conventionally the lowercase file
            extension without the leading dot (e.g. ``"docx"``).
        writer: Callable that turns a :class:`DocProj` and an output
            path into a file on disk.
    """
    WRITERS[fmt] = writer


def write(
    proj: DocProj,
    output_path: str | Path,
    *,
    original_path: str | Path | None = None,
) -> None:
    """Write a :class:`DocProj` to disk using the registered writer.

    When ``original_path`` is supplied and the writer supports it, a
    backfill edit is performed — the original file is opened and
    modified in place, preserving styles and layout. When absent the
    writer builds a fresh document from the projection.

    Args:
        proj: Projection to write.
        output_path: Where to write the output file.
        original_path: Optional path to the original source file.
            Writers that cannot backfill ignore this argument.

    Raises:
        NotImplementedError: If no writer is registered for the output
            extension.
    """
    out = Path(output_path)
    fmt = out.suffix.lstrip(".").lower()
    writer = WRITERS.get(fmt)
    if writer is None:
        raise NotImplementedError(
            f"No writer registered for {fmt!r}; available: {sorted(WRITERS)}"
        )
    if original_path is not None:
        writer_with_backfill = getattr(writer, "_supports_backfill", False)
        if writer_with_backfill:
            writer(proj, out, original_path=Path(original_path))
            return
    writer(proj, out)


from . import docx as _docx_writer  # noqa: E402 F401
