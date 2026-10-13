"""Idempotently upsert a plugin entry into a Workbuddy marketplace manifest.

Usage::

    python patch_marketplace.py <marketplace.json> <plugin-name> <plugin-source>

Reads the JSON file at ``<marketplace.json>``, removes any existing
entry whose ``name`` equals ``<plugin-name>`` from the ``plugins``
list, appends a fresh ``{"name": <plugin-name>, "source":
<plugin-source>}`` (creating the list if absent), and writes the
file back with 2-space indent and UTF-8 encoding so the surrounding
``setup.cmd`` can detect a successful run.

The script uses only the standard library so it runs against any
Python 3.12+ without an extra dependency, matching the wheel
shipped in the same zip.

Raises:
    FileNotFoundError: If ``<marketplace.json>`` does not exist.
    json.JSONDecodeError: If the file is not valid JSON.
    OSError: On any underlying filesystem error.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def upsert_plugin(
    marketplace_path: Path, name: str, source: str
) -> None:
    """Insert or replace the plugin entry named ``name``.

    Args:
        marketplace_path: Path to a Workbuddy ``marketplace.json``
            file. Must already exist; this function does not create
            parent directories.
        name: Plugin name used to deduplicate entries. Any pre-existing
            entry with the same name is dropped before the new one is
            appended, so the operation is idempotent.
        source: Value for the new entry's ``source`` field — typically
            a marketplace-relative path like
            ``"./plugins/trans-lc-pilot"``.
    """
    data = json.loads(marketplace_path.read_text(encoding="utf-8"))
    plugins = data.setdefault("plugins", [])
    plugins[:] = [p for p in plugins if p.get("name") != name]
    plugins.append({"name": name, "source": source})
    marketplace_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def main(argv: list[str]) -> int:
    """Entry point for the console script.

    Args:
        argv: Argument vector excluding the program name.

    Returns:
        int: ``0`` on success, ``1`` on usage error or filesystem
        failure. The caller (``setup.cmd``) propagates this exit code.
    """
    if len(argv) != 3:
        print(
            "usage: patch_marketplace.py "
            "<marketplace.json> <plugin-name> <plugin-source>",
            file=sys.stderr,
        )
        return 1
    marketplace_path = Path(argv[0])
    try:
        upsert_plugin(marketplace_path, argv[1], argv[2])
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
