"""Load a source document and convert it to an HTML fragment.

A :class:`SourceDoc` pairs the originating file with the HTML mammoth
produces from it. The conversion runs once, at load time, so a caller
that both inspects and splits a document pays for it only once.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import mammoth


@dataclass(frozen=True)
class SourceDoc:
    """A docx file paired with the HTML fragment mammoth produced from it.

    Attributes:
        path: Path to the originating file on disk.
        fragment: HTML fragment with no ``<html>`` or ``<body>``
            wrapper. Empty paragraphs are preserved so blank lines
            survive the conversion.
    """

    path: Path
    fragment: str


def read(path: str | Path) -> SourceDoc:
    """Load a docx file and convert it to an HTML fragment.

    Args:
        path: Path to the input file. The extension selects the
            conversion; only ``.docx`` is supported today.

    Returns:
        SourceDoc: The path paired with its HTML fragment.

    Raises:
        FileNotFoundError: If ``path`` does not exist.
        NotImplementedError: If the file's extension is not supported.
        OSError: On read failure.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(p)
    fmt = p.suffix.lstrip(".").lower()
    if fmt == "docx":
        with p.open("rb") as f:
            result = mammoth.convert_to_html(f, ignore_empty_paragraphs=False)
    else:
        raise NotImplementedError(
            f"unsupported format: {fmt!r}; only 'docx' is supported"
        )
    return SourceDoc(path=p, fragment=result.value)
