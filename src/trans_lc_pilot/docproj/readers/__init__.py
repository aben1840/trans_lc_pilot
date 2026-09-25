"""Registry of input format readers.

Readers convert files on disk into :class:`DocProj` instances. Each
reader self-registers against a format identifier (typically the file
extension without the leading dot) at import time.
"""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from ..document import DocProj

Reader = Callable[[Path], DocProj]
READERS: dict[str, Reader] = {}


def register_reader(fmt: str, reader: Reader) -> None:
    """Register a reader under the given format name.

    Args:
        fmt: Format identifier, conventionally the lowercase file
            extension without the leading dot (e.g. ``"docx"``).
        reader: Callable that turns a :class:`pathlib.Path` into a
            :class:`DocProj`.
    """
    READERS[fmt] = reader


def read(path: str | Path) -> DocProj:
    """Read a file into a :class:`DocProj` using the registered reader.

    Args:
        path: Path to the input file. The extension determines which
            reader is dispatched.

    Returns:
        DocProj: The populated projection.

    Raises:
        FileNotFoundError: If ``path`` does not exist.
        NotImplementedError: If no reader is registered for the file's
            extension.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(p)
    fmt = p.suffix.lstrip(".").lower()
    reader = READERS.get(fmt)
    if reader is None:
        raise NotImplementedError(
            f"No reader registered for {fmt!r}; available: {sorted(READERS)}"
        )
    return reader(p)


# Import readers so they self-register on package import.
from . import docx as _docx_reader  # noqa: E402, F401
