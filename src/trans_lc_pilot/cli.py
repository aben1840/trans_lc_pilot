"""Command-line entry: docx processing only.

Each document action is a subcommand, so its options are scoped to it
and argparse enforces what may be combined — there is no compatibility
matrix to keep in step with the parser. All LLM-driven agent behaviour
lives on ``trans-lc-pilot-agent`` (see
:mod:`trans_lc_pilot.langchain_agent.entry`).
"""
from __future__ import annotations

import argparse
import sys
import traceback
from dataclasses import replace
from pathlib import Path

from .docproj import (
    BundleError,
    SourceDoc,
    bundle,
    heading_counts,
    presentation,
    read,
)
from .workspace import (
    IngestError,
    Workspace,
    ingest,
    write_index,
    write_preview,
)


def _writing_parser() -> argparse.ArgumentParser:
    """Return the options shared by the subcommands that write.

    Returns:
        argparse.ArgumentParser: A parent parser, for ``parents=``.
    """
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument(
        "--workspace",
        metavar="DIR",
        help="Root directory every artifact lands under (default: CWD).",
    )
    parent.add_argument(
        "--quiet",
        action="store_true",
        help="Write without opening anything.",
    )
    return parent


def _overwriting_parser() -> argparse.ArgumentParser:
    """Return the options shared by the subcommands that overwrite.

    Returns:
        argparse.ArgumentParser: A parent parser, for ``parents=``.
    """
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing output.",
    )
    return parent


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Argument vector excluding the program name; typically
            ``sys.argv[1:]``.

    Returns:
        argparse.Namespace: Parsed arguments. ``command`` names the
        subcommand that ran; ``file`` or ``bundle`` holds its input.
    """
    parser = argparse.ArgumentParser(prog="trans-lc-pilot")
    actions = parser.add_subparsers(dest="command", required=True)

    inspect = actions.add_parser(
        "inspect",
        help="Print the heading levels in FILE and exit; writes nothing.",
        description=(
            "Report how many headings FILE has at each level, so a"
            " caller can choose what to split on. Reads only: no"
            " workspace, no output."
        ),
    )
    inspect.add_argument("file", metavar="FILE")

    preview = actions.add_parser(
        "preview",
        parents=[_writing_parser()],
        help="Convert FILE to HTML via mammoth, open it, and exit.",
        description=(
            "Convert FILE to the HTML a reader sees, write it to the"
            " workspace scratch, and open it. A preview is a glance:"
            " the document is not ingested into sources/."
        ),
    )
    preview.add_argument("file", metavar="FILE")

    split = actions.add_parser(
        "split",
        parents=[_writing_parser(), _overwriting_parser()],
        help="Split FILE into a bundle of HTML pieces and exit.",
        description=(
            "Ingest FILE into the workspace, then split it at headings"
            " of one level into a bundle: one editable HTML file per"
            " piece, a manifest recording their order, an index page,"
            " and a copy of the document that later supplies the"
            " styles. The bundle lands at"
            " <workspace>/bundles/<source-stem>-h<level>."
        ),
    )
    split.add_argument("file", metavar="FILE")
    split.add_argument(
        "--level",
        type=int,
        choices=range(1, 7),
        help="Heading level to split on (default: 1).",
    )
    split.add_argument(
        "--as",
        dest="as_name",
        metavar="NAME",
        help=(
            "Store the source under NAME in the workspace instead of"
            " its own file name. Needed when that name is already"
            " taken by a different document."
        ),
    )
    assemble = actions.add_parser(
        "assemble",
        parents=[_writing_parser(), _overwriting_parser()],
        help="Assemble a bundle's pieces into a new docx and exit.",
        description=(
            "Rebuild a bundle's pieces into a docx, in the order its"
            " manifest gives. The template copy supplies what HTML"
            " cannot: styles, theme, page setup, headers and footers."
        ),
    )
    assemble.add_argument("bundle", metavar="BUNDLE_DIR")
    assemble.add_argument(
        "--out",
        metavar="FILE",
        help="Where to write the docx (default: <workspace>/output/<bundle>.docx).",
    )
    assemble.add_argument(
        "--template",
        metavar="FILE",
        help="Take styles from FILE instead of the bundle's own copy.",
    )
    return parser.parse_args(argv)


def _workspace(args: argparse.Namespace) -> Workspace:
    """Return the workspace a writing subcommand should use.

    Args:
        args: Parsed arguments from a subcommand that takes
            ``--workspace``.

    Returns:
        Workspace: The requested root, or the working directory.
    """
    return Workspace.at(args.workspace or Path.cwd())


def _run_document_action(args: argparse.Namespace) -> int:
    """Run the chosen subcommand against its input.

    Args:
        args: Parsed arguments holding one subcommand's options.

    Returns:
        int: ``0`` on success, ``1`` on a reported failure. Expected
        failures are printed without a traceback; anything else
        propagates to :func:`main`.
    """
    if args.command == "assemble":
        return _assemble(args)

    try:
        doc = read(args.file)
        if args.command == "inspect":
            return _inspect(doc)
        elif args.command == "preview":
            return _preview(doc, args)
        else:
            return _split(doc, args)
    except FileNotFoundError as exc:
        print(f"error: file not found: {exc}", file=sys.stderr)
        return 1
    except (IngestError, NotImplementedError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def _inspect(doc: SourceDoc) -> int:
    """Print the heading levels present in a document's HTML fragment.

    Reads only — nothing is written anywhere, which is why this
    subcommand takes no workspace.

    Args:
        doc: Source document whose fragment is scanned for headings.

    Returns:
        int: Always ``0``. A document with no headings at all is a
        valid document, not a failure.
    """
    _print_levels(heading_counts(doc.fragment))
    return 0


def _print_levels(counts: dict[int, int]) -> None:
    """Print a heading-level inventory, one level per line.

    Args:
        counts: Heading level mapped to how many headings it holds.
    """
    if not counts:
        print("no headings found")
        return
    for level in sorted(counts):
        print(f"h{level}: {counts[level]}")


def _preview(doc: SourceDoc, args: argparse.Namespace) -> int:
    """Convert a source docx to HTML and report where it went.

    This is the raw mammoth conversion of the source — the document as
    a reader sees it. It writes to the workspace scratch only: a
    preview is a glance, so it does not ingest the document into
    ``sources/``.

    Args:
        doc: Source document to convert.
        args: Parsed ``preview`` arguments.

    Returns:
        int: ``0`` on success.
    """
    path = write_preview(doc, _workspace(args))
    print(f"source: {doc.path}")
    print(f"html: {path}")
    if not args.quiet:
        print(presentation.open_in_browser(path))
    return 0


def _split(doc: SourceDoc, args: argparse.Namespace) -> int:
    """Split a document into a bundle and report what happened.

    The document is ingested into the workspace first: a bundle records
    that copy as its template, so what it was built from stays put even
    if the file the caller named later moves or changes.

    The report always names the level actually used and every level the
    document has, so a caller that passed no ``--level`` can still see
    what the default chose and what else was available.

    Args:
        doc: Source document to split.
        args: Parsed ``split`` arguments.

    Returns:
        int: ``0`` on success.
    """
    workspace = _workspace(args)
    source = ingest(workspace, doc.path, as_name=args.as_name)
    doc = replace(doc, path=source.path)

    level = 1 if args.level is None else args.level
    root = workspace.bundle_dir(doc.path.name, level)
    record = bundle.write_bundle(doc, level=level, out_dir=root, force=args.force)
    index_path = root / bundle.INDEX_NAME

    print(f"source: {source.origin}")
    if source.stored:
        print(f"stored: {source.path}")
    print(f"level: {level}")
    print(f"articles: {len(record.articles)}")
    if record.preamble is not None:
        print("preamble: yes (content before the first heading)")
    if len(record.articles) == 1 and not record.articles[0].title:
        print(f"note: no heading at level {level}; document left whole")
    print("heading levels in document:")
    _print_levels(heading_counts(doc.fragment))
    print(f"bundle: {root}")
    print(f"index: {index_path}")
    _refresh_index(workspace, args.force)
    if not args.quiet:
        # The bundle's own index lists the pieces; the workspace index
        # above it lists bundles, so it is not what a split should open.
        print(presentation.open_in_browser(index_path))
    return 0


def _assemble(args: argparse.Namespace) -> int:
    """Assemble a bundle into a new docx and report what happened.

    Args:
        args: Parsed ``assemble`` arguments.

    Returns:
        int: ``0`` on success, ``1`` on a reported failure.
    """
    workspace = _workspace(args)
    root = Path(args.bundle)
    out_path = Path(args.out) if args.out else workspace.output_path(root)
    try:
        result = bundle.assemble_docx(
            root, out_path, template=args.template, force=args.force
        )
    except FileNotFoundError as exc:
        print(f"error: file not found: {exc}", file=sys.stderr)
        return 1
    except (BundleError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"bundle: {root}")
    print(f"pieces: {result.pieces}")
    print(f"output: {result.output}")
    print(_edited_line(result.edited))
    for message in result.warnings:
        print(f"warning: {message}")
    _refresh_index(workspace, args.force)
    if not args.quiet:
        print(presentation.open_in_browser(result.output))
    return 0


def _edited_line(edited: tuple[int, ...]) -> str:
    """Describe which pieces differ from the hash taken at split time.

    Args:
        edited: Numbers of the pieces that were touched.

    Returns:
        str: A line naming them, or stating that none changed.
    """
    if not edited:
        return "edited: none (every piece still matches its split-time hash)"
    return "edited: " + ", ".join(f"{number:03d}" for number in edited)


def _refresh_index(workspace: Workspace, force: bool) -> None:
    """Rewrite the workspace index, reporting rather than failing.

    A split or an assembly is the work; the index is derived from it.
    Refusing the command because a page could not be refreshed would
    report the wrong thing.

    Args:
        workspace: Whose index to refresh.
        force: Overwrite a file this tool did not write.
    """
    try:
        write_index(workspace, force=force)
    except OSError as exc:
        print(f"warning: workspace index not written: {exc}")


def main(argv: list[str] | None = None) -> int:
    """Entry point for the ``trans-lc-pilot`` console script.

    Document-only operations::

        trans-lc-pilot inspect  FILE
        trans-lc-pilot preview  FILE [--workspace DIR] [--quiet]
        trans-lc-pilot split    FILE [--level N] [--as NAME] [--workspace DIR]
                                [--quiet] [--force]
        trans-lc-pilot assemble BUNDLE_DIR [--out FILE] [--template FILE]
                                [--workspace DIR] [--quiet] [--force]

    Every artifact lands under ``--workspace DIR``, the working
    directory by default. ``inspect`` writes nothing, so it takes none.

    Args:
        argv: Optional argument vector excluding the program name;
            defaults to ``sys.argv[1:]`` when ``None``.

    Returns:
        int: Exit code; ``0`` on success, ``1`` on failure.
    """
    argv = list(argv if argv is not None else sys.argv[1:])
    try:
        args = parse_args(argv)
        exit_code = _run_document_action(args)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
