"""The bundle: what a split produced, and how the pieces relate.

A bundle is a directory holding everything one split produced, so the
pieces can be edited and later assembled back into a docx:

* ``manifest.json`` — the association itself and its single source of
  truth: the template, the heading level used, and the ordered pieces.
* ``template.docx`` — a copy of the source document, so the bundle
  carries its own styles and survives being moved elsewhere.
* ``index.html`` — a projection of the manifest for humans.
* one HTML file per piece: ``000-preamble.html`` when the document has
  content before its first heading, ``NNN-<heading-slug>.html``
  otherwise.

The manifest is authoritative. The file names repeat the same order as
a convenience for humans and for browsers; nothing reads order from
them.

:func:`write_bundle` creates a bundle from a source document;
:func:`read_bundle` and :func:`validate` inspect one;
:func:`assemble_docx` rebuilds one into a new docx, taking its styles from
the bundled template.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
from dataclasses import dataclass
from html import escape
from pathlib import Path

from docx import Document
from docx.document import Document as DocxDocument
from docx.oxml.ns import qn

from .article import Article
from .docx_body import append_fragment
from .docx_styles import resolve
from .html_headings import split_by_headings
from .presentation import wrap_as_document
from .source_doc import SourceDoc

MANIFEST_NAME = "manifest.json"
INDEX_NAME = "index.html"
TEMPLATE_NAME = "template.docx"
SCHEMA_VERSION = 1


class BundleError(ValueError):
    """A bundle directory is missing, malformed, or of an unknown version."""


@dataclass(frozen=True)
class TemplateRef:
    """The docx a bundle takes its styles from.

    Attributes:
        path: Location of the copy inside the bundle, relative to its root.
        original_path: Where that copy came from, as resolved at split
            time. Informational only — it may not resolve on another
            machine.
        sha256: Hash of the copy, i.e. of the source as it was when the
            split ran.
    """

    path: Path
    original_path: str
    sha256: str


@dataclass(frozen=True)
class PieceEntry:
    """One editable piece of a split.

    Attributes:
        number: ``0`` for the preamble, ``1..N`` for the articles.
        title: The heading text, or an empty string for the preamble and
            for a document that has no headings at all.
        file: The piece's HTML file, relative to the bundle root.
        sha256: Hash of that file as written at split time. A mismatch
            means the piece has been edited since.
    """

    number: int
    title: str
    file: str
    sha256: str


@dataclass(frozen=True)
class Bundle:
    """A split, as persisted in ``manifest.json``.

    Attributes:
        version: Schema version of the manifest.
        template: The style source for the assembled document.
        level: Heading level the split used.
        pieces: The pieces, in document order. ``number`` is
            authoritative; the sequence is expected to be sorted by it.
    """

    version: int
    template: TemplateRef
    level: int
    pieces: tuple[PieceEntry, ...]

    @property
    def preamble(self) -> PieceEntry | None:
        """The preamble, or ``None`` when the split produced none."""
        for piece in self.pieces:
            if piece.number == 0:
                return piece
        return None

    @property
    def articles(self) -> tuple[PieceEntry, ...]:
        """The pieces that are articles, i.e. everything but the preamble."""
        return tuple(piece for piece in self.pieces if piece.number != 0)


@dataclass(frozen=True)
class Findings:
    """What :func:`validate` found in a bundle.

    Attributes:
        errors: Problems that make the bundle unassemblable.
        warnings: Things worth reporting, but not fatal.
    """

    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        """Whether the bundle holds no blocking problem."""
        return not self.errors


@dataclass(frozen=True)
class AssemblyResult:
    """What one assembly produced.

    Attributes:
        output: Path of the written docx.
        pieces: How many pieces were assembled.
        edited: Numbers of the pieces whose content differs from the hash
            recorded at split time, i.e. the ones the user touched.
        warnings: Everything that could not be carried over, plus
            whatever else is worth telling the user.
    """

    output: Path
    pieces: int
    edited: tuple[int, ...]
    warnings: tuple[str, ...]


def default_dir(source: str | Path, level: int) -> Path:
    """Return the default bundle directory for a split.

    Bundles are work products rather than scratch, so they land under the
    working directory instead of ``.tmp/``; ``bundles/`` is git-ignored.

    Args:
        source: The document being split.
        level: Heading level the split uses.

    Returns:
        Path: ``<cwd>/bundles/<source-stem>-h<level>``.
    """
    return Path.cwd() / "bundles" / f"{Path(source).stem}-h{level}"


def default_output(bundle_root: str | Path) -> Path:
    """Return the default output path for assembly.

    Args:
        bundle_root: The bundle being assembled.

    Returns:
        Path: ``<cwd>/<bundle-name>.docx``.
    """
    return Path.cwd() / f"{Path(bundle_root).name}.docx"


def piece_path(root: str | Path, piece: PieceEntry) -> Path:
    """Return the path of ``piece`` inside the bundle at ``root``.

    Args:
        root: Bundle directory.
        piece: The piece to locate.

    Returns:
        Path: The piece's HTML file.
    """
    return Path(root) / piece.file


def write_bundle(
    doc: SourceDoc,
    level: int,
    out_dir: str | Path,
    *,
    force: bool = False,
) -> Bundle:
    """Split ``doc`` and write the pieces, template copy, manifest, and index.

    Args:
        doc: The source document to split.
        level: Heading level to split on, 1-6.
        out_dir: Bundle directory; created along with its parents.
        force: Overwrite when ``out_dir`` already holds files.

    Returns:
        Bundle: The manifest that was written.

    Raises:
        FileExistsError: If ``out_dir`` is not empty and ``force`` is false.
        OSError: On I/O failure while writing.
    """
    root = Path(out_dir)
    if root.exists() and any(root.iterdir()) and not force:
        raise FileExistsError(
            f"bundle directory is not empty: {root} (use --force to overwrite)"
        )
    root.mkdir(parents=True, exist_ok=True)

    entries: list[PieceEntry] = []
    for article in split_by_headings(doc.fragment, level=level):
        name = _article_filename(article)
        path = root / name
        path.write_text(
            wrap_as_document(article.html, title=article.title or doc.path.name),
            encoding="utf-8",
        )
        entries.append(
            PieceEntry(
                number=article.number,
                title=article.title,
                file=name,
                sha256=sha256_file(path),
            )
        )

    record = Bundle(
        version=SCHEMA_VERSION,
        template=_write_template_copy(doc.path, root),
        level=level,
        pieces=tuple(entries),
    )
    (root / MANIFEST_NAME).write_text(
        json.dumps(_manifest_dict(record), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (root / INDEX_NAME).write_text(_render_index(record), encoding="utf-8")
    return record


def read_bundle(root: str | Path) -> Bundle:
    """Read the manifest of the bundle rooted at ``root``.

    Args:
        root: Bundle directory.

    Returns:
        Bundle: The parsed manifest.

    Raises:
        BundleError: If the directory holds no manifest, the JSON cannot
            be parsed, or the schema version is not supported.
    """
    root = Path(root)
    manifest = root / MANIFEST_NAME
    if not manifest.is_file():
        raise BundleError(f"not a bundle (no {MANIFEST_NAME}): {root}")
    try:
        raw = json.loads(manifest.read_text(encoding="utf-8"))
        record = Bundle(
            version=int(raw["version"]),
            template=TemplateRef(
                path=Path(raw["template"]["path"]),
                original_path=str(raw["template"].get("original_path", "")),
                sha256=str(raw["template"].get("sha256", "")),
            ),
            level=int(raw["level"]),
            pieces=tuple(
                PieceEntry(
                    number=int(item["number"]),
                    title=str(item.get("title", "")),
                    file=str(item["file"]),
                    sha256=str(item.get("sha256", "")),
                )
                for item in raw["pieces"]
            ),
        )
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise BundleError(f"unreadable {MANIFEST_NAME} in {root}: {exc}") from exc
    if record.version != SCHEMA_VERSION:
        raise BundleError(
            f"unsupported bundle version {record.version}"
            f" (expected {SCHEMA_VERSION}): {root}"
        )
    return record


def validate(bundle: Bundle, root: str | Path) -> Findings:
    """Check a bundle against the directory it came from.

    Args:
        bundle: A parsed manifest.
        root: The bundle directory that manifest came from.

    Returns:
        Findings: Blocking errors and non-fatal warnings. An edited
        piece is not a problem — it is the point of the bundle — so
        only structural damage is reported here.

    Note:
        A piece is left out of an assembly by removing its entry from
        the manifest; the numbering then has a gap, which is reported
        but not refused. Removing only the HTML file is an error, since
        the manifest is what says a piece belongs.
    """
    root = Path(root)
    errors: list[str] = []
    warnings: list[str] = []

    if not bundle.pieces:
        errors.append("bundle holds no pieces")

    for piece in bundle.pieces:
        if not (root / piece.file).is_file():
            errors.append(
                f"piece {piece.number:03d} is missing: {piece.file}"
                f" (remove its entry from {MANIFEST_NAME} to leave it out)"
            )

    numbers = [piece.number for piece in bundle.pieces]
    if len(numbers) != len(set(numbers)):
        errors.append(f"duplicate piece numbers: {sorted(numbers)}")
    if numbers.count(0) > 1:
        errors.append("more than one preamble")
    if numbers != sorted(numbers):
        errors.append(f"pieces are not in number order: {numbers}")
    gaps = sorted(set(range(1, max(numbers, default=0) + 1)) - set(numbers))
    if gaps:
        warnings.append(f"article numbering skips {gaps}; those pieces are left out")

    template_path = root / bundle.template.path
    if not template_path.is_file():
        errors.append(f"template copy is missing: {bundle.template.path}")
    elif _differs(template_path, bundle.template.sha256):
        warnings.append(f"template copy changed: {bundle.template.path}")

    original = Path(bundle.template.original_path)
    if original.is_file() and _differs(original, bundle.template.sha256):
        warnings.append(f"the original document changed after the split: {original}")

    registered = {piece.file for piece in bundle.pieces} | {INDEX_NAME}
    strays = sorted(
        path.name for path in root.glob("*.html") if path.name not in registered
    )
    if strays:
        warnings.append(f"unregistered HTML files are ignored: {', '.join(strays)}")

    return Findings(errors=tuple(errors), warnings=tuple(warnings))


def sha256_file(path: str | Path) -> str:
    """Return the hex SHA-256 of a file's bytes.

    Args:
        path: File to hash.

    Returns:
        str: Hex digest.
    """
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def assemble_docx(
    bundle_root: str | Path,
    out_path: str | Path,
    *,
    template: str | Path | None = None,
    force: bool = False,
) -> AssemblyResult:
    """Assemble a bundle's pieces into a new docx.

    The template supplies what a rebuilt document cannot invent for
    itself: styles, theme, page setup, headers and footers. Its body is
    cleared and rebuilt from the pieces in the order the manifest gives,
    so the original document acts as a style source rather than as a
    thing being edited.

    Args:
        bundle_root: The bundle directory.
        out_path: Where to write the assembled docx.
        template: A docx to take styles from instead of the bundle's own
            copy of the original.
        force: Overwrite ``out_path`` when it already exists.

    Returns:
        AssemblyResult: What was written, and what could not be carried
        over.

    Raises:
        BundleError: If the bundle is malformed or fails validation.
        FileNotFoundError: If the chosen template is not there.
        FileExistsError: If ``out_path`` exists and ``force`` is false.
        OSError: On I/O failure.
    """
    root = Path(bundle_root)
    record = read_bundle(root)
    findings = validate(record, root)
    if findings.errors:
        raise BundleError("; ".join(findings.errors))

    output = Path(out_path)
    if output.exists() and not force:
        raise FileExistsError(f"output already exists: {output}")

    template_path = root / record.template.path if template is None else Path(template)
    if not template_path.is_file():
        raise FileNotFoundError(template_path)

    document = Document(str(template_path))
    _clear_body(document)
    styles = resolve(document)

    warnings = list(findings.warnings)
    edited: list[int] = []
    for piece in record.pieces:
        path = piece_path(root, piece)
        if piece.sha256 and sha256_file(path) != piece.sha256:
            edited.append(piece.number)
        html = path.read_text(encoding="utf-8")
        for message in append_fragment(html, document, styles):
            warnings.append(f"piece {piece.number:03d}: {message}")

    output.parent.mkdir(parents=True, exist_ok=True)
    document.save(str(output))
    return AssemblyResult(
        output=output,
        pieces=len(record.pieces),
        edited=tuple(edited),
        warnings=tuple(warnings),
    )


def _differs(path: Path, expected: str) -> bool:
    """Whether a file's hash differs from the one recorded for it.

    Args:
        path: File to hash.
        expected: The hash recorded earlier, empty when there is none.

    Returns:
        bool: ``True`` when a hash was recorded and no longer matches.
    """
    return bool(expected) and sha256_file(path) != expected


def _clear_body(document: DocxDocument) -> None:
    """Remove a template's content while keeping its section properties.

    The trailing ``w:sectPr`` carries the page setup and the references
    to headers and footers, so dropping it would lose them; python-docx
    inserts new paragraphs and tables ahead of it on its own.

    Args:
        document: The template, opened by python-docx.
    """
    body = document.element.body
    for child in list(body):
        if child.tag != qn("w:sectPr"):
            body.remove(child)


def _manifest_dict(bundle: Bundle) -> dict:
    """Render a bundle as the JSON structure written to the manifest.

    Args:
        bundle: The bundle to render.

    Returns:
        dict: JSON-serializable manifest.
    """
    return {
        "version": bundle.version,
        "template": {
            "path": str(bundle.template.path),
            "original_path": bundle.template.original_path,
            "sha256": bundle.template.sha256,
        },
        "level": bundle.level,
        "pieces": [
            {
                "number": piece.number,
                "title": piece.title,
                "file": piece.file,
                "sha256": piece.sha256,
            }
            for piece in bundle.pieces
        ],
    }


def _write_template_copy(source: Path, root: Path) -> TemplateRef:
    """Copy the source document into the bundle as its template.

    Args:
        source: The document that was split.
        root: Bundle directory.

    Returns:
        TemplateRef: The copy, its origin, and its hash.
    """
    target = root / TEMPLATE_NAME
    if target.resolve() != source.resolve():
        shutil.copyfile(source, target)
    return TemplateRef(
        path=Path(TEMPLATE_NAME),
        original_path=str(source.resolve()),
        sha256=sha256_file(target),
    )


def _render_index(bundle: Bundle) -> str:
    """Render the manifest as the bundle's index page.

    Args:
        bundle: The bundle to render.

    Returns:
        str: A standalone HTML document linking every piece.
    """
    items: list[str] = []
    for piece in bundle.pieces:
        label = piece.title or "preamble"
        items.append(f'<li><a href="{piece.file}">{escape(label)}</a></li>')
    raw_name = Path(bundle.template.original_path).name or "document"
    body = (
        f"<h1>{escape(raw_name)}</h1>\n"
        f"<p>{len(bundle.articles)} article(s) split at heading level"
        f" {bundle.level}.</p>\n"
        "<ul>\n" + "\n".join(items) + "\n</ul>"
    )
    return wrap_as_document(body, title=f"Articles: {raw_name}")


def _slug(title: str, limit: int = 30) -> str:
    """Turn a heading into a filesystem-safe filename fragment.

    Args:
        title: Heading text.
        limit: Maximum length of the result.

    Returns:
        str: Slashes, colons and whitespace replaced by ``-``; falls
        back to ``"untitled"`` when nothing usable remains.
    """
    cleaned = re.sub(r'[<>:"/\\|?*\s]+', "-", title).strip("-")
    return cleaned[:limit] or "untitled"


def _article_filename(article: Article) -> str:
    """Name the output file for one piece.

    Args:
        article: The piece to name.

    Returns:
        str: ``000-preamble.html`` for the preamble, otherwise
        ``<number>-<slug>.html``.
    """
    if article.is_preamble:
        name = "000-preamble.html"
    else:
        name = f"{article.number:03d}-{_slug(article.title)}.html"
    return name
