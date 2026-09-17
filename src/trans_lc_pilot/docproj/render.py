"""Built-in renderers for DocProj.

HTML is the complete rendering today. Markdown and JSON are reserved
for future steps and currently raise :class:`NotImplementedError`.
"""
from __future__ import annotations

from html import escape

from .model import DocProj, register_renderer

_CSS = """
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
       max-width: 960px; margin: 1.5em auto; padding: 0 1em; color: #222; }
h1 { border-bottom: 1px solid #ccc; padding-bottom: 0.3em; }
table { border-collapse: collapse; width: 100%; font-size: 0.9em; }
th, td { border: 1px solid #ddd; padding: 4px 8px; text-align: left;
         vertical-align: top; }
th { background: #f3f3f3; }
tr.conf-high { background: #e8f5e9; }
tr.conf-med  { background: #fff8e1; }
tr.conf-low  { background: #ffebee; }
td.text { font-family: ui-monospace, "SF Mono", Menlo, monospace;
          font-size: 0.85em; word-break: break-word; }
td.muted { color: #888; font-size: 0.85em; }
.meta { color: #555; font-size: 0.9em; }
"""


def _conf_class(conf: float) -> str:
    """Map a confidence score to a CSS row class."""
    if conf >= 0.8:
        cls = "conf-high"
    elif conf >= 0.5:
        cls = "conf-med"
    else:
        cls = "conf-low"
    return cls


def _kind_display(kind: str, level: int | None) -> str:
    """Short label for the ``kind`` column in the HTML table."""
    if kind == "heading" and level is not None:
        label = f"H{level}"
    elif kind == "table":
        label = "TBL"
    elif kind == "image":
        label = "IMG"
    else:
        label = kind
    return label


def render_html(proj: DocProj) -> str:
    """Render :class:`DocProj` as a self-contained HTML document.

    The output is a single HTML page with inline CSS and a table
    summarising every block. Confidence drives row background colour so
    low-confidence classifications stand out at a glance.
    """
    rows: list[str] = []
    for b in proj.blocks:
        cls = _conf_class(b.kind_confidence)
        kind_disp = _kind_display(b.kind, b.level)
        text = (b.text or "").replace("\n", " ")
        truncated = len(text) > 200
        if truncated:
            text = text[:200] + "…"
        signals = ", ".join(b.signals) if b.signals else "—"
        rows.append(
            f'<tr class="{cls}">'
            f"<td>{b.idx}</td>"
            f'<td class="muted">{escape(kind_disp)}</td>'
            f'<td class="muted">{b.page_index}</td>'
            f'<td class="muted">{b.kind_confidence:.2f}</td>'
            f'<td class="text">{escape(text)}</td>'
            f'<td class="muted">{escape(signals)}</td>'
            f"</tr>"
        )

    title = escape(proj.source_path.name)
    src = escape(str(proj.source_path))
    fmt = escape(proj.source_format)
    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        f"<title>DocProj: {title}</title>\n"
        f"<style>{_CSS}</style>\n"
        "</head>\n"
        "<body>\n"
        f"<h1>DocProj: {title}</h1>\n"
        f'<p class="meta"><strong>Format:</strong> {fmt} &middot; '
        f"<strong>Blocks:</strong> {len(proj.blocks)} &middot; "
        f"<strong>Path:</strong> {src}</p>\n"
        "<table>\n"
        "<thead><tr>"
        "<th>idx</th><th>kind</th><th>page</th><th>conf</th>"
        "<th>text</th><th>signals</th>"
        "</tr></thead>\n"
        "<tbody>\n"
        + "\n".join(rows)
        + "\n</tbody>\n"
        "</table>\n"
        "</body>\n"
        "</html>\n"
    )


def render_markdown(proj: DocProj) -> str:
    """Render :class:`DocProj` as a compact Markdown outline.

    Reserved for a future step. Calling this raises
    :class:`NotImplementedError`.
    """
    raise NotImplementedError(
        "Markdown renderer is reserved for a future step "
        "(see plan: docproj module)"
    )


def render_json(proj: DocProj) -> str:
    """Render :class:`DocProj` as JSON for diff and debug.

    Reserved for a future step. Calling this raises
    :class:`NotImplementedError`.
    """
    raise NotImplementedError(
        "JSON renderer is reserved for a future step "
        "(see plan: docproj module)"
    )


register_renderer("html", render_html)
register_renderer("markdown", render_markdown)
register_renderer("json", render_json)
