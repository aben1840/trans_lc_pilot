"""Command-line entry: docx processing only.

Document actions are mutually exclusive options. All LLM-driven agent
behaviour lives on ``trans-lc-pilot-agent`` (see
:mod:`trans_lc_pilot.langchain_agent.entry`).
"""
from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path

from .docproj import (
    BundleError,
    SourceDoc,
    bundle,
    heading_counts,
    presentation,
    read,
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse command-line arguments.

    Document actions are options rather than subcommands so a caller
    can invoke any one of them directly.

    Args:
        argv: Argument vector excluding the program name; typically
            ``sys.argv[1:]``.

    Returns:
        argparse.Namespace: Parsed arguments. Exactly one of
        ``list_levels``, ``convert``, ``split``, or ``assemble`` is set.
    """
    parser = argparse.ArgumentParser(prog="trans-lc-pilot")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument(
        "--list-levels",
        metavar="FILE",
        help="Print the heading levels in FILE and exit; writes nothing.",
    )
    action.add_argument(
        "--convert",
        metavar="FILE",
        help="Convert FILE to HTML via mammoth, open it, and exit.",
    )
    action.add_argument(
        "--split",
        metavar="FILE",
        help="Split FILE into a bundle of HTML pieces and exit.",
    )
    action.add_argument(
        "--assemble",
        metavar="BUNDLE_DIR",
        help="Assemble a bundle's pieces into a new docx and exit.",
    )
    parser.add_argument(
        "--level",
        type=int,
        choices=range(1, 7),
        help="Heading level for --split (default: 1).",
    )
    parser.add_argument(
        "--out",
        metavar="PATH",
        help="With --split, the bundle directory; with --assemble, the output file.",
    )
    parser.add_argument(
        "--template",
        metavar="FILE",
        help="With --assemble, take styles from FILE instead of the bundled copy.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="With --split or --assemble, overwrite existing output.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="With --convert, --split or --assemble, write without opening anything.",
    )
    return parser.parse_args(argv)


def _check_option_combinations(args: argparse.Namespace) -> list[str]:
    """Report options used with an action they do not belong to.

    Args:
        args: Parsed arguments.

    Returns:
        list[str]: One message per invalid combination; empty when every
        option agrees with the chosen action.
    """
    problems: list[str] = []
    if not args.split and args.level is not None:
        problems.append("--level requires --split")
    if not (args.split or args.assemble) and args.out is not None:
        problems.append("--out requires --split or --assemble")
    if args.template is not None and not args.assemble:
        problems.append("--template requires --assemble")
    if args.force and not (args.split or args.assemble):
        problems.append("--force requires --split or --assemble")
    if not (args.convert or args.split or args.assemble) and args.quiet:
        problems.append("--quiet requires --convert, --split or --assemble")
    return problems


def _run_document_action(args: argparse.Namespace) -> int:
    """Run one document action against one input.

    Args:
        args: Parsed arguments holding exactly one of the actions.

    Returns:
        int: ``0`` on success, ``1`` on a reported failure. Expected
        failures are printed without a traceback; anything else
        propagates to :func:`main`.
    """
    problems = _check_option_combinations(args)
    if problems:
        for problem in problems:
            print(f"error: {problem}", file=sys.stderr)
        return 1

    if args.assemble:
        return _assemble_bundle(args, not args.quiet)

    path = args.list_levels or args.convert or args.split
    try:
        doc = read(path)
        if args.list_levels:
            return _list_levels(doc)
        elif args.convert:
            return _convert_document(doc, not args.quiet)
        else:
            return _split_document(
                doc,
                1 if args.level is None else args.level,
                not args.quiet,
                args.out,
                args.force,
            )
    except FileNotFoundError as exc:
        print(f"error: file not found: {exc}", file=sys.stderr)
        return 1
    except (NotImplementedError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def _list_levels(doc: SourceDoc) -> int:
    """Print the heading levels present in a document's HTML fragment.

    Reads only — nothing is written anywhere.

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


def _convert_document(doc: SourceDoc, open_after: bool) -> int:
    """Convert a source docx to HTML and report where it went.

    This is the raw mammoth conversion of the source — the document as a
    reader sees it.

    Args:
        doc: Source document to convert.
        open_after: Whether to open the written HTML in the browser.

    Returns:
        int: ``0`` on success.
    """
    path = presentation.write_source_html(doc)
    print(f"source: {doc.path}")
    print(f"html: {path}")
    if open_after:
        print(presentation.open_in_browser(path))
    return 0


def _split_document(
    doc: SourceDoc,
    level: int,
    open_after: bool,
    out_dir: str | None,
    force: bool,
) -> int:
    """Split a document into a bundle and report what happened.

    The report always names the level actually used and every level the
    document has, so a caller that passed no ``--level`` can still see
    what the default chose and what else was available.

    Args:
        doc: Source document to split.
        level: Heading level to split at.
        open_after: Whether to open the index page once it is written.
        out_dir: Bundle directory, or ``None`` for the default location.
        force: Whether to overwrite a bundle directory that is not empty.

    Returns:
        int: ``0`` on success.
    """
    root = Path(out_dir) if out_dir else bundle.default_dir(doc.path, level)
    record = bundle.write_bundle(doc, level=level, out_dir=root, force=force)
    index_path = root / bundle.INDEX_NAME

    print(f"source: {doc.path}")
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
    if open_after:
        print(presentation.open_in_browser(index_path))
    return 0


def _assemble_bundle(args: argparse.Namespace, open_after: bool) -> int:
    """Assemble a bundle into a new docx and report what happened.

    Args:
        args: Parsed arguments holding ``--assemble``.
        open_after: Whether to open the written docx once it exists.

    Returns:
        int: ``0`` on success, ``1`` on a reported failure.
    """
    root = Path(args.assemble)
    out_path = Path(args.out) if args.out else bundle.default_output(root)
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
    if open_after:
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


def main(argv: list[str] | None = None) -> int:
    """Entry point for the ``trans-lc-pilot`` console script.

    Document-only operations::

        trans-lc-pilot --list-levels FILE
        trans-lc-pilot --convert FILE [--quiet]
        trans-lc-pilot --split FILE [--level N] [--out DIR] [--quiet]
        trans-lc-pilot --assemble BUNDLE_DIR [--out FILE] [--quiet]

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
