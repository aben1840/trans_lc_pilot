from __future__ import annotations

import json
import shutil
from pathlib import Path

from trans_lc_pilot.docproj import assemble_docx, read
from trans_lc_pilot.docproj.bundle import (
    SCHEMA_VERSION,
    read_bundle,
    sha256_file,
    validate,
    write_bundle,
)

FIXTURES = Path(__file__).parents[1] / "fixtures"
ARTICLES = FIXTURES / "articles.docx"


def test_split_then_assemble_round_trips(tmp_path: Path) -> None:
    doc = read(ARTICLES)
    root = tmp_path / "bundle"

    written = write_bundle(doc, level=1, out_dir=root)
    parsed = read_bundle(root)
    result = assemble_docx(root, tmp_path / "out.docx")

    assert written == parsed
    assert result.output.is_file()
    assert result.pieces >= 1
    assert result.edited == ()


def test_a_manifest_from_before_the_workspace_still_reads(tmp_path: Path) -> None:
    """The manifest shape is unchanged, so old bundles keep working."""
    root = tmp_path / "old-h1"
    root.mkdir()
    shutil.copyfile(ARTICLES, root / "template.docx")
    piece = root / "001-intro.html"
    piece.write_text("<p>hello</p>", encoding="utf-8")
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "version": 1,
                "template": {
                    "path": "template.docx",
                    "original_path": "C:/docs/articles.docx",
                    "sha256": sha256_file(root / "template.docx"),
                },
                "level": 1,
                "pieces": [
                    {
                        "number": 1,
                        "title": "Intro",
                        "file": "001-intro.html",
                        "sha256": sha256_file(piece),
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    bundle = read_bundle(root)

    assert bundle.version == SCHEMA_VERSION
    assert bundle.level == 1
    assert bundle.template.original_path == "C:/docs/articles.docx"
    assert [entry.title for entry in bundle.pieces] == ["Intro"]
    assert validate(bundle, root).ok
