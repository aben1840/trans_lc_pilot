from __future__ import annotations

from pathlib import Path

from trans_lc_pilot.cli import main
from trans_lc_pilot.workspace import Workspace, render_index, write_index

FIXTURES = Path(__file__).parent.parent / "fixtures"
ARTICLES = FIXTURES / "articles.docx"


def test_render_index_of_an_untouched_workspace(tmp_path: Path) -> None:
    html = render_index(Workspace.at(tmp_path))

    assert "0 bundles from 0 sources." in html
    assert "nothing ingested yet" in html
    assert "none yet" in html


def test_write_index_refuses_a_foreign_file(tmp_path: Path) -> None:
    workspace = Workspace.at(tmp_path)
    workspace.index.write_text("<html>mine</html>", encoding="utf-8")

    try:
        write_index(workspace)
    except FileExistsError as exc:
        assert "trans-lc-pilot" in str(exc)
    else:
        raise AssertionError("a foreign index.html was overwritten")


def test_write_index_replaces_its_own_file(tmp_path: Path) -> None:
    workspace = Workspace.at(tmp_path)

    write_index(workspace)
    first = workspace.index.read_text(encoding="utf-8")
    write_index(workspace)

    assert "trans-lc-pilot" in first
    assert workspace.index.read_text(encoding="utf-8") == first


def test_index_escapes_a_name_and_quotes_a_href(tmp_path: Path) -> None:
    # A source named for the ampersand that used to break <title>.
    awkward = tmp_path / "elsewhere"
    awkward.mkdir()
    named = awkward / "R&D.docx"
    named.write_bytes(ARTICLES.read_bytes())
    root = tmp_path / "ws"

    code = main(
        [
            "--split",
            str(named),
            "--level",
            "1",
            "--workspace",
            str(root),
            "--quiet",
        ]
    )
    html = (root / "index.html").read_text(encoding="utf-8")

    assert code == 0
    assert "R&amp;D" in html
    assert "R&D" not in html
    assert 'href="bundles/R%26D-h1/index.html"' in html
