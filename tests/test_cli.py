from __future__ import annotations

from pathlib import Path

import pytest

from trans_lc_pilot.cli import main, parse_args
from trans_lc_pilot.workspace import Workspace, list_sources

FIXTURE = Path(__file__).parent / "fixtures" / "articles.docx"


def split(root: Path, *extra: str) -> int:
    """Split the fixture into ``root``; ``--quiet`` keeps the browser shut."""
    return main(["split", str(FIXTURE), "--workspace", str(root), "--quiet", *extra])


def test_a_subcommand_is_required() -> None:
    with pytest.raises(SystemExit):
        parse_args([])


def test_each_subcommand_takes_its_own_input() -> None:
    assert parse_args(["inspect", "a.docx"]).file == "a.docx"
    assert parse_args(["preview", "a.docx"]).file == "a.docx"
    assert parse_args(["split", "a.docx"]).file == "a.docx"
    assert parse_args(["assemble", "bundle"]).bundle == "bundle"


def test_subcommands_accept_the_options_they_declare() -> None:
    split_args = parse_args(
        ["split", "a.docx", "--level", "2", "--as", "n", "--force", "--quiet"]
    )

    assert split_args.level == 2
    assert split_args.as_name == "n"
    assert split_args.force is True
    assert split_args.quiet is True
    assert split_args.workspace is None

    assemble_args = parse_args(
        ["assemble", "b", "--out", "o.docx", "--template", "t.docx"]
    )

    assert assemble_args.out == "o.docx"
    assert assemble_args.template == "t.docx"


@pytest.mark.parametrize(
    "argv",
    [
        ["inspect", "a.docx", "--workspace", "w"],
        ["inspect", "a.docx", "--quiet"],
        ["inspect", "a.docx", "--force"],
        ["preview", "a.docx", "--as", "n"],
        ["preview", "a.docx", "--force"],
        ["preview", "a.docx", "--template", "t.docx"],
        ["split", "a.docx", "--template", "t.docx"],
        ["split", "a.docx", "--out", "d"],
        ["assemble", "b", "--as", "n"],
        ["assemble", "b", "--level", "2"],
    ],
)
def test_options_are_scoped_to_their_subcommand(argv: list[str]) -> None:
    """argparse rejects these outright — no compatibility matrix needed."""
    with pytest.raises(SystemExit):
        parse_args(argv)


def test_inspect_carries_no_workspace_at_all() -> None:
    assert not hasattr(parse_args(["inspect", "a.docx"]), "workspace")


def test_help_is_scoped_to_the_subcommand(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit):
        parse_args(["split", "--help"])
    split_help = capsys.readouterr().out

    with pytest.raises(SystemExit):
        parse_args(["inspect", "--help"])
    inspect_help = capsys.readouterr().out

    assert "--level" in split_help
    assert "--workspace" in split_help
    assert "--level" not in inspect_help
    assert "--workspace" not in inspect_help


def test_split_creates_the_workspace(tmp_path: Path) -> None:
    # --quiet: without it the run tries to open a browser.
    code = split(tmp_path, "--level", "1")

    assert code == 0
    assert (tmp_path / "sources" / "articles.docx").is_file()
    assert (tmp_path / "bundles" / "articles-h1" / "manifest.json").is_file()
    assert (tmp_path / "index.html").is_file()


def test_a_second_split_joins_the_same_workspace(tmp_path: Path) -> None:
    split(tmp_path, "--level", "1")
    split(tmp_path, "--level", "2")

    assert list_sources(Workspace.at(tmp_path)) == ["articles.docx"]
    assert sorted(entry.name for entry in (tmp_path / "bundles").iterdir()) == [
        "articles-h1",
        "articles-h2",
    ]


def test_split_at_a_taken_level_is_refused(tmp_path: Path) -> None:
    split(tmp_path, "--level", "1")

    code = split(tmp_path, "--level", "1")

    assert code == 1
    assert (tmp_path / "bundles" / "articles-h1" / "manifest.json").is_file()


def test_assemble_writes_into_the_output_directory(tmp_path: Path) -> None:
    split(tmp_path, "--level", "1")

    code = main(
        [
            "assemble",
            str(tmp_path / "bundles" / "articles-h1"),
            "--workspace",
            str(tmp_path),
            "--quiet",
        ]
    )

    assert code == 0
    assert (tmp_path / "output" / "articles-h1.docx").is_file()
    assert "assembled" in (tmp_path / "index.html").read_text(encoding="utf-8")


def test_a_foreign_index_is_left_alone(tmp_path: Path) -> None:
    mine = tmp_path / "index.html"
    mine.write_text("<html>my own page</html>", encoding="utf-8")

    code = split(tmp_path, "--level", "1")

    # The split is the work; the index is derived from it.
    assert code == 0
    assert mine.read_text(encoding="utf-8") == "<html>my own page</html>"


def test_preview_does_not_ingest(tmp_path: Path) -> None:
    code = main(
        ["preview", str(FIXTURE), "--workspace", str(tmp_path), "--quiet"]
    )

    assert code == 0
    assert list((tmp_path / ".tmp").glob("docproj-source-*.html"))
    assert not (tmp_path / "sources").exists()


def test_inspect_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Run from an empty directory: inspect takes no --workspace, so
    # anything it wrote would land here.
    monkeypatch.chdir(tmp_path)

    code = main(["inspect", str(FIXTURE)])

    assert code == 0
    assert list(tmp_path.iterdir()) == []
