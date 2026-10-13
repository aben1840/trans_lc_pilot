"""Tests for the standalone ``tools/patch_marketplace.py`` script.

The script is bundled into ``dist/trans-lc-pilot.zip`` at ``tools/`` and
invoked by ``setup.cmd`` to upsert the host's my-experts
``marketplace.json``. It must use only the standard library because
it runs before the project wheel is installed.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools.patch_marketplace import main, upsert_plugin

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "tools" / "patch_marketplace.py"


def _write_marketplace(path: Path, plugins: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "name": "my-experts",
                "description": "host marketplace",
                "plugins": plugins,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_upsert_appends_when_absent(tmp_path: Path) -> None:
    mkt = tmp_path / ".codebuddy-plugin" / "marketplace.json"
    _write_marketplace(mkt, plugins=[])

    upsert_plugin(mkt, "trans-lc-pilot", "./plugins/trans-lc-pilot")

    data = json.loads(mkt.read_text(encoding="utf-8"))
    assert data["plugins"] == [
        {"name": "trans-lc-pilot", "source": "./plugins/trans-lc-pilot"}
    ]


def test_upsert_replaces_existing_entry(tmp_path: Path) -> None:
    mkt = tmp_path / "marketplace.json"
    _write_marketplace(
        mkt,
        plugins=[
            {"name": "workbuddy-scout", "source": "./plugins/workbuddy-scout"},
            {"name": "trans-lc-pilot", "source": "./plugins/trans-lc-pilot/0.0.1"},
        ],
    )

    upsert_plugin(mkt, "trans-lc-pilot", "./plugins/trans-lc-pilot")

    data = json.loads(mkt.read_text(encoding="utf-8"))
    assert data["plugins"] == [
        {"name": "workbuddy-scout", "source": "./plugins/workbuddy-scout"},
        {"name": "trans-lc-pilot", "source": "./plugins/trans-lc-pilot"},
    ]


def test_upsert_creates_plugins_list_when_missing(tmp_path: Path) -> None:
    mkt = tmp_path / "marketplace.json"
    mkt.write_text('{"name": "my-experts"}', encoding="utf-8")

    upsert_plugin(mkt, "trans-lc-pilot", "./plugins/trans-lc-pilot")

    data = json.loads(mkt.read_text(encoding="utf-8"))
    assert data["plugins"] == [
        {"name": "trans-lc-pilot", "source": "./plugins/trans-lc-pilot"}
    ]


def test_upsert_preserves_utf8_non_ascii(tmp_path: Path) -> None:
    mkt = tmp_path / "marketplace.json"
    _write_marketplace(
        mkt,
        plugins=[{"name": "workbuddy-scout", "description": "小探"}],
    )

    upsert_plugin(mkt, "trans-lc-pilot", "./plugins/trans-lc-pilot")

    # File must remain valid UTF-8 with non-ASCII content preserved.
    raw = mkt.read_bytes()
    assert "小探".encode() in raw
    data = json.loads(raw)
    assert data["plugins"][0]["description"] == "小探"


def test_main_usage_error_returns_1(capsys: object) -> None:
    rc = main(["only-one-arg"])
    assert rc == 1


def test_main_creates_plugin_entry(tmp_path: Path) -> None:
    mkt = tmp_path / "mkt.json"
    mkt.write_text('{"name": "my-experts", "plugins": []}', encoding="utf-8")

    rc = main([str(mkt), "trans-lc-pilot", "./plugins/trans-lc-pilot"])

    assert rc == 0
    data = json.loads(mkt.read_text(encoding="utf-8"))
    assert data["plugins"] == [
        {"name": "trans-lc-pilot", "source": "./plugins/trans-lc-pilot"}
    ]


def test_main_propagates_missing_file_error(tmp_path: Path) -> None:
    missing = tmp_path / "absent.json"
    rc = main([str(missing), "trans-lc-pilot", "./plugins/trans-lc-pilot"])
    assert rc == 1


def test_main_propagates_invalid_json(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    rc = main([str(bad), "trans-lc-pilot", "./plugins/trans-lc-pilot"])
    assert rc == 1


def test_script_runs_as_module(tmp_path: Path) -> None:
    """The script can be invoked via ``python tools/patch_marketplace.py``."""
    mkt = tmp_path / "mkt.json"
    mkt.write_text('{"name": "my-experts", "plugins": []}', encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), str(mkt), "trans-lc-pilot",
         "./plugins/trans-lc-pilot"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(mkt.read_text(encoding="utf-8"))
    assert data["plugins"][-1] == {
        "name": "trans-lc-pilot",
        "source": "./plugins/trans-lc-pilot",
    }


def test_script_uses_stdlib_only(tmp_path: Path) -> None:
    """The script must not import anything outside the standard library.

    Catches accidental reintroduction of a project import (e.g. the
    wheel) that would break ``setup.cmd``'s pre-install run.
    """
    src = SCRIPT_PATH.read_text(encoding="utf-8")
    for line in src.splitlines():
        stripped = line.strip()
        if not (stripped.startswith("import ") or stripped.startswith("from ")):
            continue
        if stripped.startswith("from __future__"):
            continue
        # Whitelist only the standard-library modules we use.
        module = stripped.split()[1].split(".")[0]
        assert module in {"json", "sys", "pathlib"}, (
            f"non-stdlib import in patch_marketplace.py: {stripped}"
        )
