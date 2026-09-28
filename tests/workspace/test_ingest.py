from __future__ import annotations

from pathlib import Path

import pytest

from trans_lc_pilot.cli import main
from trans_lc_pilot.workspace import (
    IngestError,
    Workspace,
    ingest,
    list_sources,
    read_origins,
)

FIXTURES = Path(__file__).parents[1] / "fixtures"
ARTICLES = FIXTURES / "articles.docx"
FORMATTED = FIXTURES / "formatted.docx"


@pytest.fixture
def workspace(tmp_path: Path) -> Workspace:
    return Workspace.at(tmp_path)


def test_ingest_copies_a_source_under_its_own_name(workspace: Workspace) -> None:
    source = ingest(workspace, ARTICLES)

    assert source.path == workspace.sources / "articles.docx"
    assert source.path.is_file()
    assert source.origin == str(ARTICLES)
    assert source.stored is True
    assert read_origins(workspace)["articles.docx"]["origin"].endswith("articles.docx")


def test_ingest_of_identical_content_is_a_no_op(workspace: Workspace) -> None:
    ingest(workspace, ARTICLES)

    source = ingest(workspace, ARTICLES)

    assert source.stored is False
    assert list_sources(workspace) == ["articles.docx"]


def test_ingest_of_a_source_already_in_sources_is_not_self_copied(
    workspace: Workspace,
) -> None:
    first = ingest(workspace, ARTICLES)

    again = ingest(workspace, first.path)

    assert again.stored is False
    assert again.path == first.path


def test_ingest_refuses_other_content_under_a_taken_name(
    workspace: Workspace, tmp_path: Path
) -> None:
    ingest(workspace, ARTICLES)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    clash = elsewhere / "articles.docx"
    clash.write_bytes(FORMATTED.read_bytes())

    with pytest.raises(IngestError, match="--as"):
        ingest(workspace, clash)

    assert list_sources(workspace) == ["articles.docx"]


def test_as_gives_the_copy_that_name(workspace: Workspace) -> None:
    assert ingest(workspace, ARTICLES, as_name="report").path.name == "report.docx"
    assert (
        ingest(workspace, ARTICLES, as_name="report.docx").path.name
        == "report.docx"
    )


def test_ingest_reuses_the_spelling_already_on_disk(workspace: Workspace) -> None:
    first = ingest(workspace, ARTICLES, as_name="Report.docx")

    again = ingest(workspace, ARTICLES, as_name="report.docx")

    assert first.path.name == "Report.docx"
    assert again.path.name == "Report.docx"


@pytest.mark.parametrize(
    "name",
    [
        "",
        "../evil",
        "sub/evil",
        "CON",
        "con",
        "lpt1",
        "report.",
        "report ",
        ".hidden",
        'bad"name',
    ],
)
def test_as_refuses_names_that_cannot_be_files(
    workspace: Workspace, name: str
) -> None:
    with pytest.raises(IngestError, match="unusable name"):
        ingest(workspace, ARTICLES, as_name=name)

    assert list_sources(workspace) == []


def test_corrupt_origins_does_not_block_an_ingest(workspace: Workspace) -> None:
    workspace.sources.mkdir(parents=True)
    workspace.origins.write_text("{ not json", encoding="utf-8")

    assert read_origins(workspace) == {}
    assert ingest(workspace, ARTICLES).stored is True


def test_missing_origins_is_not_an_error(workspace: Workspace) -> None:
    assert read_origins(workspace) == {}


def test_an_unreadable_source_is_refused_before_anything_is_stored(
    tmp_path: Path,
) -> None:
    text = tmp_path / "notes.txt"
    text.write_text("not a docx", encoding="utf-8")
    root = tmp_path / "ws"

    code = main(["--split", str(text), "--workspace", str(root), "--quiet"])

    assert code == 1
    assert not (root / "sources").exists()
    assert not root.exists()
