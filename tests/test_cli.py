from __future__ import annotations

from pathlib import Path

from trans_lc_pilot.cli import _check_option_combinations, main, parse_args
from trans_lc_pilot.workspace import Workspace, list_sources

FIXTURE = Path(__file__).parent / "fixtures" / "articles.docx"


def problems(argv: list[str]) -> list[str]:
    """Return the problems reported for one argument vector."""
    return _check_option_combinations(parse_args(argv))


def split(root: Path, *extra: str) -> int:
    """Split the fixture into ``root``; ``--quiet`` keeps the browser shut."""
    return main(["--split", str(FIXTURE), "--workspace", str(root), "--quiet", *extra])


def test_options_rejected_with_an_action_they_do_not_belong_to() -> None:
    assert problems(["--list-levels", "a.docx", "--level", "2"]) != []
    assert problems(["--list-levels", "a.docx", "--out", "d"]) != []
    assert problems(["--list-levels", "a.docx", "--workspace", "w"]) != []
    assert problems(["--list-levels", "a.docx", "--quiet"]) != []
    assert problems(["--convert", "a.docx", "--out", "o"]) != []
    assert problems(["--convert", "a.docx", "--force"]) != []
    assert problems(["--convert", "a.docx", "--template", "t.docx"]) != []
    assert problems(["--convert", "a.docx", "--as", "n"]) != []
    assert problems(["--assemble", "b", "--as", "n"]) != []


def test_options_accepted_by_the_actions_that_write() -> None:
    assert problems(["--convert", "a.docx", "--workspace", "w"]) == []
    assert problems(["--split", "a.docx", "--workspace", "w"]) == []
    assert problems(["--split", "a.docx", "--as", "n"]) == []
    assert problems(["--assemble", "b", "--workspace", "w"]) == []
    assert problems(["--split", "a.docx"]) == []
    assert problems(["--assemble", "b"]) == []


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
            "--assemble",
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
