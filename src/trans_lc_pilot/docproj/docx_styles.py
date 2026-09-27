"""Resolve a template's styles into the lookups a rebuild needs.

Headings are keyed by outline level rather than by name. A style name is
localized — ``Heading 1`` in one Word, ``标题 1`` in another — and by the
time an HTML fragment exists the original name is gone anyway, while
``w:outlineLvl`` means the same thing in every language and is what Word
itself uses for the navigation pane and for tables of contents.

Lists and tables offer no such language-independent key, so they fall
back to a name lookup and may end up unstyled against a template whose
built-in styles are named in another language;
:mod:`trans_lc_pilot.docproj.docx_body` reports that when it happens.
"""
from __future__ import annotations

from dataclasses import dataclass

from docx.document import Document as DocxDocument
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml.ns import qn

MAX_HEADING_LEVEL = 6

_HEADING_PREFIXES = ("Heading", "标题")
_BULLET_NAMES = ("List Bullet", "项目符号")
_NUMBER_NAMES = ("List Number", "编号")
_TABLE_NAMES = ("Table Grid", "网格型")


@dataclass(frozen=True)
class Styles:
    """The style names a rebuild looks up while rendering.

    Attributes:
        heading: Heading level (1-6) mapped to a style name the template
            defines. Levels the template cannot express are absent.
        bullet: Style for unordered list items, or ``None``.
        number: Style for ordered list items, or ``None``.
        table: Style for tables, or ``None``.
        body: The template's default paragraph style, or ``None`` to let
            python-docx choose.
    """

    heading: dict[int, str]
    bullet: str | None
    number: str | None
    table: str | None
    body: str | None


def resolve(document: DocxDocument) -> Styles:
    """Map a template's styles onto what a rebuild needs.

    Args:
        document: The template, opened by python-docx.

    Returns:
        Styles: Style names to apply, ``None`` where the template offers
        nothing suitable.
    """
    paragraph_styles = [
        style
        for style in document.styles
        if style.type == WD_STYLE_TYPE.PARAGRAPH
    ]
    return Styles(
        heading=_heading_styles(paragraph_styles),
        bullet=_named_style(document, _BULLET_NAMES, WD_STYLE_TYPE.PARAGRAPH),
        number=_named_style(document, _NUMBER_NAMES, WD_STYLE_TYPE.PARAGRAPH),
        table=_named_style(document, _TABLE_NAMES, WD_STYLE_TYPE.TABLE),
        body=_default_paragraph_style(document),
    )


def _heading_styles(styles: list) -> dict[int, str]:
    """Group paragraph styles by the heading level they stand for.

    Args:
        styles: The template's paragraph styles.

    Returns:
        dict[int, str]: Heading level mapped to a style name. A level
        claimed by several styles prefers the one named like a heading.
    """
    candidates: dict[int, list[str]] = {}
    for style in styles:
        outline = _outline_level(style)
        if outline is None or not 0 <= outline < MAX_HEADING_LEVEL:
            continue
        candidates.setdefault(outline + 1, []).append(_style_name(style))
    return {
        level: _preferred(level, names) for level, names in candidates.items()
    }


def _preferred(level: int, names: list[str]) -> str:
    """Pick the style to use for one heading level.

    Args:
        level: Heading level, 1-6.
        names: Styles declaring that level as their outline level.

    Returns:
        str: The first style named like the level, else the first one.
    """
    for name in names:
        if _named_like_heading(level, name):
            return name
    return names[0]


def _named_like_heading(level: int, name: str) -> bool:
    """Whether a style name reads as the heading of ``level``.

    Args:
        level: Heading level, 1-6.
        name: Style name, e.g. ``"Heading 1"`` or ``"标题 1"``.

    Returns:
        bool: ``True`` when the name is a heading prefix followed by the
        level number.
    """
    stripped = name.strip()
    for prefix in _HEADING_PREFIXES:
        if stripped.startswith(prefix) and stripped[len(prefix) :].strip() == str(
            level
        ):
            return True
    return False


def _outline_level(style) -> int | None:
    """Return the outline level a paragraph style declares.

    python-docx exposes no property for it, so the style XML is read
    directly.

    Args:
        style: A paragraph style.

    Returns:
        int | None: Outline level, ``0`` for a top-level heading, or
        ``None`` when the style declares none.
    """
    properties = style.element.find(qn("w:pPr"))
    if properties is None:
        return None
    outline = properties.find(qn("w:outlineLvl"))
    if outline is None:
        return None
    try:
        return int(outline.get(qn("w:val")))
    except (TypeError, ValueError):
        return None


def _default_paragraph_style(document: DocxDocument) -> str | None:
    """Return the name of the template's default paragraph style.

    Read from the XML because the default is declared by an attribute,
    not by the name ``Normal``.

    Args:
        document: The template, opened by python-docx.

    Returns:
        str | None: The style name, or ``None`` when none is declared.
    """
    for element in document.styles.element.findall(qn("w:style")):
        if element.get(qn("w:type")) != "paragraph":
            continue
        if element.get(qn("w:default")) in {"1", "true", "on"}:
            name = element.find(qn("w:name"))
            if name is not None:
                return name.get(qn("w:val"))
    return None


def _named_style(
    document: DocxDocument,
    names: tuple[str, ...],
    style_type: WD_STYLE_TYPE,
) -> str | None:
    """Return the first of ``names`` the template defines.

    Args:
        document: The template, opened by python-docx.
        names: Candidate style names, in order of preference.
        style_type: The style type those names must have.

    Returns:
        str | None: The first name the template defines, else ``None``.
    """
    available = {
        _style_name(style)
        for style in document.styles
        if style.type == style_type
    }
    for name in names:
        if name in available:
            return name
    return None


def _style_name(style) -> str:
    """Return a style's name, tolerating unnamed styles.

    Args:
        style: Any style.

    Returns:
        str: The name, or an empty string.
    """
    return style.name or ""
