"""Bringing a source document into a workspace.

A workspace owns its inputs. Once a document is split, the copy under
``sources/`` is what the bundle records as its template, so a bundle
stays reproducible even after the file the user pointed at moves or
changes.

One writer at a time is assumed. The origin record is read-modify-written,
so two ingests at once could lose an entry; the collision decision never
consults it, so the worst case is a missing provenance line rather than
a wrong file.

The document's format is the caller's to check — :func:`ingest` copies
bytes and never parses, so a caller that has already read the document
with :func:`trans_lc_pilot.docproj.source_doc.read` does not pay for a
second parse or a second copy of the extension rule.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from ..docproj.bundle import sha256_file
from .layout import Workspace

SUFFIX = ".docx"

_ILLEGAL = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED = frozenset(
    ["CON", "PRN", "AUX", "NUL"]
    + [f"COM{number}" for number in range(1, 10)]
    + [f"LPT{number}" for number in range(1, 10)]
)


class IngestError(ValueError):
    """A source document cannot be brought into the workspace."""


@dataclass(frozen=True)
class Source:
    """An ingested source document.

    Attributes:
        path: The copy under ``sources/``. This is what a split reads
            and what a bundle records.
        stored: Whether this call wrote the copy, as opposed to finding
            identical content already there.
        origin: The file the caller named, as it was given.
    """

    path: Path
    stored: bool
    origin: str


def ingest(
    workspace: Workspace,
    source: str | Path,
    *,
    as_name: str | None = None,
) -> Source:
    """Copy ``source`` into the workspace and return the stored copy.

    The same content stored twice is a no-op, so splitting a document
    that is already in the workspace costs nothing. Different content
    under a name already taken is refused rather than overwritten: the
    stored copy is what earlier bundles were built from, and replacing
    it silently is how edits are lost.

    Args:
        workspace: Whose ``sources/`` directory receives the copy.
        source: The document to bring in, at any path.
        as_name: Name to store it under, ``.docx`` optional. ``None``
            uses the source's own file name.

    Returns:
        Source: The stored copy and where it came from.

    Raises:
        IngestError: If ``as_name`` cannot be a file name, or if that
            name already holds different content.
        FileNotFoundError: If ``source`` is not a file.
        OSError: On I/O failure.
    """
    origin = Path(source)
    if not origin.is_file():
        raise FileNotFoundError(origin)

    name = _name_for(workspace, origin, as_name)
    target = workspace.sources / name

    if target.is_file():
        if sha256_file(target) == sha256_file(origin):
            return Source(path=target, stored=False, origin=str(origin))
        raise IngestError(
            f"{name} is already stored in {workspace.sources.name}/"
            f" with different content; pass --as NAME to store this copy"
            f" under another name, or delete the stored copy to refresh it"
        )

    # Only reached with different content, so origin and target cannot be
    # the same file and the copy cannot be a self-copy.
    workspace.sources.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(origin, target)
    _record_origin(workspace, name, origin, target)
    return Source(path=target, stored=True, origin=str(origin))


def read_origins(workspace: Workspace) -> dict[str, dict]:
    """Read the record of where each ingested copy came from.

    A provenance line is a convenience, never a precondition: an
    unreadable record must not stop a split, so anything unexpected
    yields an empty one.

    Args:
        workspace: Whose origin record to read.

    Returns:
        dict[str, dict]: Stored name mapped to its record — ``origin``,
        ``sha256`` and ``ingested_at``.
    """
    try:
        data = json.loads(workspace.origins.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(key): value for key, value in data.items() if isinstance(value, dict)}


def list_sources(workspace: Workspace) -> list[str]:
    """Return the names of every document ingested into a workspace.

    Args:
        workspace: Whose ``sources/`` directory to list.

    Returns:
        list[str]: File names, sorted. Empty when nothing is ingested,
        or when the directory does not exist yet.
    """
    if not workspace.sources.is_dir():
        return []
    return sorted(
        entry.name
        for entry in workspace.sources.iterdir()
        if entry.is_file() and not entry.name.startswith(".")
    )


def _name_for(workspace: Workspace, origin: Path, as_name: str | None) -> str:
    """Return the name to store ``origin`` under.

    An explicit ``as_name`` is checked and normalized. Either way,
    a spelling already on disk wins — so a name never flips between
    runs, and a bundle never ends up named for a case the directory
    does not actually use.

    Args:
        workspace: Whose ``sources/`` directory the name is for.
        origin: The document being ingested.
        as_name: The name the caller asked for, if any.

    Returns:
        str: A file name ending in ``.docx``.

    Raises:
        IngestError: If ``as_name`` cannot be a file name.
    """
    name = _checked(as_name) if as_name is not None else origin.name
    stored = _existing(workspace, name)
    return stored if stored is not None else name


def _checked(name: str) -> str:
    """Validate a caller-supplied name and give it a ``.docx`` suffix.

    Refused rather than repaired: a sanitized name is not the name the
    caller asked for, and finding that out later is worse than hearing
    it now.

    Args:
        name: The requested name, ``.docx`` optional.

    Returns:
        str: The name, with exactly one ``.docx`` suffix.

    Raises:
        IngestError: If the name cannot be a file name on Windows or
            POSIX, or is a reserved device name.
    """
    stem = name[: -len(SUFFIX)] if name.casefold().endswith(SUFFIX) else name
    if not stem:
        raise IngestError(f"unusable name: {name!r} (empty)")
    if _ILLEGAL.search(name):
        raise IngestError(
            f"unusable name: {name!r}"
            " (no path separators, drive colons or < > : \" / \\ | ? *)"
        )
    if stem != stem.strip(" ."):
        raise IngestError(
            f"unusable name: {name!r} (no leading or trailing dots or spaces)"
        )
    if stem.split(".")[0].upper() in _RESERVED:
        raise IngestError(f"unusable name: {name!r} (reserved on Windows)")
    return f"{stem}{SUFFIX}"


def _existing(workspace: Workspace, name: str) -> str | None:
    """Return the on-disk spelling of ``name`` in ``sources/``, if any.

    Matching folds case and Unicode normalization so a name already
    taken on a case-insensitive filesystem is recognised, and the
    spelling on disk is reused. On a case-sensitive filesystem the same
    code matches nothing and a second file is written, which is correct
    there.

    Args:
        workspace: Whose ``sources/`` directory to look in.
        name: The file name to look for.

    Returns:
        str | None: The existing entry's name, or ``None``.
    """
    if not workspace.sources.is_dir():
        return None
    wanted = _fold(name)
    for entry in workspace.sources.iterdir():
        if entry.is_file() and _fold(entry.name) == wanted:
            return entry.name
    return None


def _fold(name: str) -> str:
    """Fold a file name for comparison across platforms.

    Args:
        name: The file name.

    Returns:
        str: NFC-normalized, then case-folded.
    """
    return unicodedata.normalize("NFC", name).casefold()


def _record_origin(
    workspace: Workspace, name: str, origin: Path, target: Path
) -> None:
    """Record where an ingested copy came from.

    Written through a sibling temporary file: a half-written record
    would be worse than none, since every aggregate render reads it.

    Args:
        workspace: Whose origin record to update.
        name: The stored name.
        origin: The path the caller gave.
        target: The stored copy.

    Raises:
        OSError: On I/O failure.
    """
    records = read_origins(workspace)
    records[name] = {
        "origin": str(origin.resolve()),
        "sha256": sha256_file(target),
        "ingested_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    temporary = workspace.origins.with_suffix(f"{workspace.origins.suffix}.tmp")
    temporary.write_text(
        json.dumps(records, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, workspace.origins)
