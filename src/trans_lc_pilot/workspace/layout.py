"""Where a workspace keeps its artifacts.

Naming lives here rather than in :mod:`trans_lc_pilot.docproj` so that
module stays path-agnostic: it acts on the paths a caller hands it and
never derives one of its own.

Nothing here creates a directory. Every path is derived on demand, and
the write that uses one makes its own parents — so inspecting a
workspace never leaves an empty ``sources/`` behind.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

SOURCES_DIR = "sources"
BUNDLES_DIR = "bundles"
OUTPUT_DIR = "output"
TMP_DIR = ".tmp"
ORIGINS_NAME = ".origins.json"
INDEX_NAME = "index.html"


@dataclass(frozen=True)
class Workspace:
    """A root directory every artifact of one working set lives under.

    Attributes:
        root: The directory itself. Held as given — it need not exist,
            and is not created here.
    """

    root: Path

    @classmethod
    def at(cls, root: str | Path) -> Workspace:
        """Return the workspace rooted at ``root``.

        Args:
            root: The workspace root directory. Need not exist.

        Returns:
            Workspace: The workspace. No directory is created.
        """
        return cls(root=Path(root))

    @property
    def sources(self) -> Path:
        """The ingested source documents, and the record of their origins."""
        return self.root / SOURCES_DIR

    @property
    def bundles(self) -> Path:
        """The bundles split from those sources."""
        return self.root / BUNDLES_DIR

    @property
    def output(self) -> Path:
        """The docx assembled from those bundles."""
        return self.root / OUTPUT_DIR

    @property
    def tmp(self) -> Path:
        """Scratch: the HTML preview ``--convert`` writes."""
        return self.root / TMP_DIR

    @property
    def index(self) -> Path:
        """The aggregate page listing every bundle."""
        return self.root / INDEX_NAME

    @property
    def origins(self) -> Path:
        """Where each ingested source came from, and what it held."""
        return self.sources / ORIGINS_NAME

    def bundle_dir(self, source_name: str, level: int) -> Path:
        """Return the bundle directory for a source split at ``level``.

        Args:
            source_name: The source document's file name, e.g.
                ``"report.docx"``. A full path also works; only its stem
                is used.
            level: Heading level the split uses, 1-6.

        Returns:
            Path: ``<root>/bundles/<source-stem>-h<level>``.
        """
        return self.bundles / f"{Path(source_name).stem}-h{level}"

    def output_path(self, bundle_name: str | Path) -> Path:
        """Return the default output path for a bundle.

        Args:
            bundle_name: The bundle directory's name, or a path whose
                final component is one.

        Returns:
            Path: ``<root>/output/<bundle-name>.docx``.
        """
        return self.output / f"{Path(bundle_name).name}.docx"
