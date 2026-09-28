from __future__ import annotations

from pathlib import Path

from trans_lc_pilot.workspace import Workspace

FIXTURE = "report.docx"


def test_layout_derives_every_path_from_root(tmp_path: Path) -> None:
    workspace = Workspace.at(tmp_path)

    assert workspace.sources == tmp_path / "sources"
    assert workspace.bundles == tmp_path / "bundles"
    assert workspace.output == tmp_path / "output"
    assert workspace.tmp == tmp_path / ".tmp"
    assert workspace.index == tmp_path / "index.html"
    assert workspace.origins == tmp_path / "sources" / ".origins.json"


def test_layout_creates_nothing(tmp_path: Path) -> None:
    workspace = Workspace.at(tmp_path)
    # Touch every derived path; none may appear on disk.
    _ = (
        workspace.sources,
        workspace.bundles,
        workspace.output,
        workspace.tmp,
        workspace.index,
        workspace.origins,
        workspace.bundle_dir(FIXTURE, 1),
        workspace.output_path("report-h1"),
    )

    assert list(tmp_path.iterdir()) == []


def test_bundle_dir_names_by_stem_and_level(tmp_path: Path) -> None:
    workspace = Workspace.at(tmp_path)

    assert workspace.bundle_dir(FIXTURE, 2).name == "report-h2"
    assert workspace.bundle_dir("report.docx", 2).parent == tmp_path / "bundles"
    # A full path is accepted; only the stem is used.
    assert workspace.bundle_dir("/elsewhere/report.docx", 1).name == "report-h1"


def test_output_path_names_by_bundle(tmp_path: Path) -> None:
    workspace = Workspace.at(tmp_path)

    assert workspace.output_path("report-h1").name == "report-h1.docx"
    assert workspace.output_path("report-h1").parent == tmp_path / "output"
    assert workspace.output_path(tmp_path / "bundles" / "report-h1").name == (
        "report-h1.docx"
    )
