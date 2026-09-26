"""Extract a contiguous fragment from a docx into a standalone docx.

This module is deliberately self-contained: it does not import from
:mod:`trans_lc_pilot.docproj` or any of its submodules. It is a
plain python-docx + lxml utility that operates directly on the OOXML
layer.

Typical use — given a source docx, extract paragraphs 2, 3, 5 and
table 0 into a new docx::

    fragment_bytes = extract_docx_fragment(
        source_path=Path("input.docx"),
        para_indices=[2, 3, 5],
        table_indices=[0],
    )
    Path("fragment.docx").write_bytes(fragment_bytes)
"""
from __future__ import annotations

from contextlib import suppress
from copy import deepcopy
from io import BytesIO
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn


def extract_docx_fragment(
    source_path: Path,
    para_indices: list[int],
    table_indices: list[int] | None = None,
) -> bytes:
    """Extract selected paragraphs and tables into a standalone docx.

    The extracted fragment is a valid .docx file that opens in Word.
    Formatting, styles, images, and numbering are preserved as much as
    possible by copying the underlying OOXML elements and the parts
    they depend on (styles.xml, numbering.xml, image relationships).

    Args:
        source_path: Path to the source docx.
        para_indices: Zero-based indices into ``Document.paragraphs``
            for the paragraphs to include. Order in the list does not
            matter — they are inserted in body order.
        table_indices: Zero-based indices into ``Document.tables``
            for the tables to include, or ``None`` if no tables.

    Returns:
        bytes: The fragment packaged as a .docx file (a ZIP archive).

    Raises:
        ValueError: If any index is out of range for the source docx.
        OSError: On read/write failure.
    """
    if table_indices is None:
        table_indices = []

    source = Document(str(source_path))
    new_doc = Document()

    _validate_indices(source, para_indices, table_indices)

    _copy_parts(source, new_doc)

    body = source.element.body
    new_body = new_doc.element.body

    # Build a single list of (kind, index, element) in body order
    items = _collect_elements(body, source, para_indices, table_indices)

    for _kind, _idx, element in items:
        new_body.append(deepcopy(element))

    _ensure_sectpr(body, new_body)

    buf = BytesIO()
    new_doc.save(buf)
    return buf.getvalue()


def _validate_indices(
    source: Document,
    para_indices: list[int],
    table_indices: list[int],
) -> None:
    """Guard against out-of-range indices with clear error messages."""
    n_paras = len(source.paragraphs)
    n_tables = len(source.tables)

    bad_paras = [i for i in para_indices if i < 0 or i >= n_paras]
    if bad_paras:
        raise ValueError(
            f"Paragraph indices {bad_paras} out of range "
            f"(document has {n_paras} paragraphs)"
        )

    bad_tables = [i for i in table_indices if i < 0 or i >= n_tables]
    if bad_tables:
        raise ValueError(
            f"Table indices {bad_tables} out of range "
            f"(document has {n_tables} tables)"
        )


def _collect_elements(
    body,
    source: Document,
    para_indices: list[int],
    table_indices: list[int],
) -> list[tuple[str, int, object]]:
    """Walk body children and pick out requested paragraphs and tables.

    python-docx's ``Document.paragraphs`` and ``Document.tables`` are
    separate enumerations over the same body, skipping each other. To
    extract both and preserve their original relative order in the
    body, we iterate body children directly and keep our own counters.
    """
    wanted_paras = set(para_indices)
    wanted_tables = set(table_indices)

    collected: list[tuple[str, int, object]] = []
    para_counter = 0
    table_counter = 0

    for child in body:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag

        if tag == "p":
            if para_counter in wanted_paras:
                collected.append(("p", para_counter, child))
            para_counter += 1
        elif tag == "tbl":
            if table_counter in wanted_tables:
                collected.append(("tbl", table_counter, child))
            table_counter += 1
        elif tag == "sectPr":
            continue
        # Other body children (e.g. bookmarks) are skipped

    return collected


def _copy_parts(source: Document, target: Document) -> None:
    """Copy styles.xml, numbering.xml, and image relationships.

    python-docx creates new default parts when you call ``Document()``.
    We overwrite them with the source versions so that style names
    (Heading 1, etc.) referenced by the copied paragraphs actually
    resolve, and so that images remain embedded.
    """
    _copy_styles_part(source, target)
    _copy_numbering_part(source, target)
    _copy_image_relationships(source, target)


def _copy_styles_part(source: Document, target: Document) -> None:
    """Replace target's styles.xml contents with the source version.

    python-docx's ``styles.element`` is the root of styles.xml (a
    part-level node) so it has no parent in the document tree. We
    clear the target's children and deep-copy the source's children
    instead of replacing the root element.
    """
    src_styles = source.styles.element
    tgt_styles = target.styles.element
    tgt_styles.clear()
    for child in src_styles:
        tgt_styles.append(deepcopy(child))


def _copy_numbering_part(source: Document, target: Document) -> None:
    """Copy numbering.xml contents, or strip it if source doesn't have one."""
    src_numbering = _get_numbering_part(source)
    tgt_numbering = _get_numbering_part(target)

    if src_numbering is not None and tgt_numbering is not None:
        tgt_root = tgt_numbering.element
        tgt_root.clear()
        for child in src_numbering.element:
            tgt_root.append(deepcopy(child))
    elif src_numbering is None and tgt_numbering is not None:
        _remove_part(target, tgt_numbering.partname)


def _get_numbering_part(doc: Document):
    try:
        return doc.part.numbering_part
    except KeyError:
        return None


def _remove_part(doc: Document, partname: str) -> None:
    """Remove a part from the target package by breaking all rels to it."""
    pkg = doc.part.package
    with suppress(KeyError):
        pkg._parts.pop(partname)
    rels_to_remove = [
        r.rId for r in list(doc.part.rels.values())
        if r.target_partname == partname
    ]
    for rId in rels_to_remove:
        del doc.part.rels[rId]


def _copy_image_relationships(source: Document, target: Document) -> None:
    """Copy image parts (relationships) that paragraphs reference.

    We walk the source body, find every ``<a:blip r:embed="rId...">``
    in paragraph runs and table cells, copy the corresponding blob
    into the target package, and update the embed id to whatever the
    new relationship got assigned.
    """
    r_id_map: dict[str, str] = {}

    def _iter_blips(element):
        return element.iter(qn("a:blip"))

    for blip in _iter_blips(source.element.body):
        old_rId = blip.get(qn("r:embed"))
        if old_rId is None or old_rId in r_id_map:
            continue

        try:
            rel = source.part.rels[old_rId]
        except KeyError:
            continue

        new_rId = target.part.relate_to(rel.target_part, rel.reltype)
        r_id_map[old_rId] = new_rId

    # Now walk the target body and fix up every copied blip
    for blip in _iter_blips(target.element.body):
        old_rId = blip.get(qn("r:embed"))
        if old_rId in r_id_map:
            blip.set(qn("r:embed"), r_id_map[old_rId])


def _ensure_sectpr(source_body, new_body) -> None:
    """Ensure the fragment has a sectPr at the end of its body.

    python-docx's ``new Document()`` creates its own default sectPr.
    If we copied paragraphs that reference the source doc's last sectPr
    (e.g. for page margins), we need the source's sectPr too — but the
    default one is usually sufficient. Here we simply make sure one
    exists at the very end of ``new_body``.
    """
    existing = new_body.find(qn("w:sectPr"))
    if existing is not None and existing.getparent() is new_body:
        # Move it to the very end (after all content we just appended)
        new_body.remove(existing)
        new_body.append(existing)
