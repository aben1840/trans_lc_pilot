"""Command-line entry: docx processing only.

Document actions are mutually exclusive options. All LLM-driven agent
behaviour lives on ``trans-lc-pilot-agent`` (see
:mod:`trans_lc_pilot.langchain_agent.entry`).
"""
from __future__ import annotations

import argparse
import sys
import traceback

from .docproj import DocProj, heading_counts, present, read, split_by_headings


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse command-line arguments.

    Document actions are options rather than subcommands so a caller
    can invoke any one of them directly.

    Args:
        argv: Argument vector excluding the program name; typically
            ``sys.argv[1:]``.

    Returns:
        argparse.Namespace: Parsed arguments. Exactly one of
        ``list_levels``, ``convert``, or ``split`` is set.
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
        help="Split FILE into one HTML file per heading and exit.",
    )
    parser.add_argument(
        "--level",
        type=int,
        choices=range(1, 7),
        help="Heading level for --split (default: 1).",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="With --convert or --split, write the output without opening it.",
    )
    return parser.parse_args(argv)


def _run_document_action(args: argparse.Namespace) -> int:
    """Run ``--list-levels``, ``--convert`` or ``--split`` against one file.

    Args:
        args: Parsed arguments holding exactly one of those options.

    Returns:
        int: ``0`` on success, ``1`` on a reported failure. Expected
        failures are printed without a traceback; anything else
        propagates to :func:`main`.
    """
    if not args.split and args.level is not None:
        print("error: --level requires --split", file=sys.stderr)
        return 1
    if not (args.convert or args.split) and args.quiet:
        print("error: --quiet requires --convert or --split", file=sys.stderr)
        return 1

    path = args.list_levels or args.convert or args.split
    try:
        proj = read(path)
        if args.list_levels:
            return _list_levels(proj)
        elif args.convert:
            return _convert_document(proj, not args.quiet)
        else:
            return _split_document(
                proj,
                1 if args.level is None else args.level,
                not args.quiet,
            )
    except FileNotFoundError as exc:
        print(f"error: file not found: {exc}", file=sys.stderr)
        return 1
    except (NotImplementedError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def _list_levels(proj: DocProj) -> int:
    """Print the heading levels present in a projection's source.

    Reads only — nothing is written anywhere.

    Args:
        proj: Projection whose source is re-read for headings.

    Returns:
        int: Always ``0``. A document with no headings at all is a
        valid document, not a failure.
    """
    _print_levels(heading_counts(present.source_fragment(proj)))
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


def _convert_document(proj: DocProj, open_after: bool) -> int:
    """Convert a projection's source docx to HTML and report where it went.

    This is the raw mammoth conversion of the source — the document as a
    reader sees it — not the tabular view of the parsed projection.

    Args:
        proj: Projection whose source is to be converted.
        open_after: Whether to open the written HTML in the browser.

    Returns:
        int: ``0`` on success.
    """
    path = present.write_source_html(proj)
    print(f"source: {proj.source_path}")
    print(f"html: {path}")
    if open_after:
        print(present.open_in_browser(path))
    return 0


def _split_document(proj: DocProj, level: int, open_after: bool) -> int:
    """Split a projection, write the pieces, and report what happened.

    The report always names the level actually used and every level the
    document has, so a caller that passed no ``--level`` can still see
    what the default chose and what else was available.

    Args:
        proj: Projection to split.
        level: Heading level to split at.
        open_after: Whether to open the index page once it is written.

    Returns:
        int: ``0`` on success.
    """
    fragment = present.source_fragment(proj)
    art_list = split_by_headings(fragment, level=level)
    index_path = present.write_articles(proj, level=level)

    print(f"source: {proj.source_path}")
    print(f"level: {level}")
    print(f"articles: {len(art_list)}")
    if any(article.is_preamble for article in art_list):
        print("preamble: yes (content before the first heading)")
    if len(art_list) == 1 and not art_list[0].title:
        print(f"note: no heading at level {level}; document left whole")
    print("heading levels in document:")
    _print_levels(heading_counts(fragment))
    print(f"index: {index_path}")
    if open_after:
        print(present.open_in_browser(index_path))
    return 0


def main(argv: list[str] | None = None) -> int:
    """Entry point for the ``trans-lc-pilot`` console script.

    Document-only operations::

        trans-lc-pilot --list-levels FILE
        trans-lc-pilot --convert FILE [--quiet]
        trans-lc-pilot --split FILE [--level N] [--quiet]

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
