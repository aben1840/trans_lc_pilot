from __future__ import annotations

from pathlib import Path

from trans_lc_pilot.langchain_agent.tools import default_tools

ARTICLES = Path(__file__).parents[1] / "fixtures" / "articles.docx"


def by_name() -> dict:
    """Return the default tools keyed by name."""
    return {tool.name: tool for tool in default_tools()}


def test_default_tools_is_the_documented_set() -> None:
    assert list(by_name()) == [
        "get_current_time",
        "list_docx_heading_levels",
        "preview_docx",
        "split_docx_by_headings",
        "assemble_docx_from_bundle",
    ]


def test_writing_tools_take_a_workspace_and_the_reader_does_not() -> None:
    tools = by_name()

    for name in (
        "preview_docx",
        "split_docx_by_headings",
        "assemble_docx_from_bundle",
    ):
        assert "workspace" in tools[name].args

    assert "workspace" not in tools["list_docx_heading_levels"].args


def test_only_the_split_tool_can_rename_a_source() -> None:
    tools = by_name()

    assert "as_name" in tools["split_docx_by_headings"].args
    assert "as_name" not in tools["preview_docx"].args


def test_only_assembly_can_choose_where_its_output_goes() -> None:
    """A bundle belongs in the workspace; an assembled docx may be delivered."""
    tools = by_name()

    assert "output_dir" not in tools["split_docx_by_headings"].args
    assert "output_path" in tools["assemble_docx_from_bundle"].args


def test_split_tool_ingests_and_writes_the_workspace(tmp_path: Path) -> None:
    output = by_name()["split_docx_by_headings"].invoke(
        {
            "file_path": str(ARTICLES),
            "level": 1,
            "workspace": str(tmp_path),
            "open_browser": False,
        }
    )

    assert "stored:" in output
    assert (tmp_path / "sources" / "articles.docx").is_file()
    assert (tmp_path / "bundles" / "articles-h1" / "manifest.json").is_file()
    assert (tmp_path / "index.html").is_file()
