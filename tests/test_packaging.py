"""Tests for ``trans_lc_pilot.packaging``.

These tests cover the three-layer archive layout (installer
artifacts, generated marketplace manifest, plugin surface) without
touching the real PyPI or running ``pip wheel`` for real.
"""
from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest

from trans_lc_pilot import packaging


def test_read_pyproject_version_matches_pyproject() -> None:
    """The helper returns the version exactly as written in pyproject.toml."""
    assert packaging._read_pyproject_version() == "0.1.0"


def test_read_pyproject_version_missing(tmp_path: Path) -> None:
    """A bogus PROJECT_ROOT without pyproject.toml raises RuntimeError."""
    with (
        patch.object(packaging, "PROJECT_ROOT", tmp_path),
        pytest.raises(RuntimeError, match=re.escape("pyproject.toml")),
    ):
        packaging._read_pyproject_version()


def test_read_pyproject_version_no_match(tmp_path: Path) -> None:
    """A pyproject.toml without a ``version = "..."`` line raises."""
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "trans-lc-pilot"\n', encoding="utf-8"
    )
    with (
        patch.object(packaging, "PROJECT_ROOT", tmp_path),
        pytest.raises(RuntimeError, match=re.escape("version =")),
    ):
        packaging._read_pyproject_version()


def test_iter_plugin_files_includes_manifest_and_three_subtrees() -> None:
    rels = sorted(rel for _, rel in packaging._iter_plugin_files())
    assert ".codebuddy-plugin/plugin.json" in rels
    assert any(r.startswith("agents/") for r in rels)
    assert any(r.startswith("skills/") for r in rels)
    assert any(r.startswith("avatars/") for r in rels)


def test_iter_plugin_files_skips_pycache_and_hidden(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Both ``__pycache__/`` and hidden files/dirs are filtered out."""
    monkeypatch.setattr(packaging, "PROJECT_ROOT", tmp_path)

    (tmp_path / ".codebuddy-plugin").mkdir()
    (tmp_path / ".codebuddy-plugin" / "plugin.json").write_text("{}", encoding="utf-8")

    agents = tmp_path / "agents"
    agents.mkdir()
    (agents / "a.md").write_text("a", encoding="utf-8")
    (agents / "__pycache__").mkdir()
    (agents / "__pycache__" / "x.pyc").write_bytes(b"x")
    (agents / ".DS_Store").write_text("ds", encoding="utf-8")

    skills = tmp_path / "skills"
    skills.mkdir()
    (skills / "split").mkdir()
    (skills / "split" / "SKILL.md").write_text("s", encoding="utf-8")

    avatars = tmp_path / "avatars"
    avatars.mkdir()
    (avatars / "expert.png").write_bytes(b"png")

    rels = sorted(rel for _, rel in packaging._iter_plugin_files())
    assert rels == [
        ".codebuddy-plugin/plugin.json",
        "agents/a.md",
        "avatars/expert.png",
        "skills/split/SKILL.md",
    ]


def test_iter_plugin_files_skips_missing_subtrees(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """If a subtree does not exist, it is silently skipped."""
    monkeypatch.setattr(packaging, "PROJECT_ROOT", tmp_path)
    (tmp_path / ".codebuddy-plugin").mkdir()
    (tmp_path / ".codebuddy-plugin" / "plugin.json").write_text("{}", encoding="utf-8")
    (tmp_path / "agents").mkdir()
    (tmp_path / "agents" / "a.md").write_text("a", encoding="utf-8")

    rels = sorted(rel for _, rel in packaging._iter_plugin_files())
    # skills/ and avatars/ absent — no entries from them.
    assert rels == [".codebuddy-plugin/plugin.json", "agents/a.md"]


def test_write_plugin_bundles_three_layers(tmp_path: Path) -> None:
    """main() produces an archive with installer + manifest + plugin surface."""
    fake_wheel = tmp_path / "trans_lc_pilot-9.9.9-py3-none-any.whl"
    fake_wheel.write_bytes(b"PK\x03\x04 fake wheel bytes")

    with (
        patch.object(packaging, "_build_wheel", return_value=fake_wheel),
        patch.object(packaging, "_read_pyproject_version", return_value="9.9.9"),
    ):
        out = tmp_path / "plugin.zip"
        rc = packaging.main(["--out", str(out)])

    assert rc == 0
    assert out.is_file()

    with zipfile.ZipFile(out) as zf:
        names = zf.namelist()

        # Layer 1 — installer artifacts.
        assert "setup.cmd" in names
        assert "requirements.txt" in names
        assert any(
            n.startswith("trans_lc_pilot-") and n.endswith(".whl") for n in names
        )
        setup_body = zf.read("setup.cmd").decode("utf-8")
        assert "trans_lc_pilot-9.9.9-py3-none-any.whl" in setup_body
        assert "0.1.0" not in setup_body  # old hardcoded version gone

        # Layer 2 — generated marketplace manifest.
        manifest = json.loads(
            zf.read("plugin/.codebuddy-plugin/marketplace.json")
        )
        assert manifest["plugins"][0]["version"] == "9.9.9"
        assert (
            manifest["plugins"][0]["source"]
            == "./plugins/trans-lc-pilot/9.9.9"
        )
        assert manifest["name"] == "trans-lc-pilot-market"

        # Layer 3 — plugin surface, versioned root.
        plugin_root = "plugin/plugins/trans-lc-pilot/9.9.9"
        assert f"{plugin_root}/.codebuddy-plugin/plugin.json" in names
        assert any(n.startswith(f"{plugin_root}/agents/") for n in names)
        assert any(n.startswith(f"{plugin_root}/skills/") for n in names)
        assert any(n.startswith(f"{plugin_root}/avatars/") for n in names)


def test_main_returns_one_when_build_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Build errors are surfaced to stderr and main() returns 1."""
    with (
        patch.object(
            packaging,
            "_build_wheel",
            side_effect=RuntimeError("pip wheel exploded"),
        ),
        patch.object(packaging, "_read_pyproject_version", return_value="0.1.0"),
    ):
        rc = packaging.main(["--out", str(tmp_path / "plugin.zip")])

    assert rc == 1
    err = capsys.readouterr().err
    assert "pip wheel exploded" in err


def test_main_returns_one_when_version_missing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A missing pyproject.toml version is reported and main() returns 1."""
    with patch.object(
        packaging,
        "_read_pyproject_version",
        side_effect=RuntimeError("pyproject.toml has no [project] version"),
    ):
        rc = packaging.main(["--out", str(tmp_path / "plugin.zip")])

    assert rc == 1
    err = capsys.readouterr().err
    assert "version" in err


def test_parse_args_default_out() -> None:
    """``--out`` defaults to ``plugin.zip`` in the current directory."""
    ns = packaging.parse_args([])
    assert ns.out == "plugin.zip"


def test_parse_args_explicit_out(tmp_path: Path) -> None:
    ns = packaging.parse_args(["--out", str(tmp_path / "x.zip")])
    assert ns.out == str(tmp_path / "x.zip")
