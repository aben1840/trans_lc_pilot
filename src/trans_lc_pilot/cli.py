"""Command-line entry: one-shot prompt or the interactive REPL."""
from __future__ import annotations

import argparse
import sys
import traceback

from . import repl
from .agent import build_agent, run_once
from .config import load_settings
from .docproj import DocProj, heading_counts, present, read, split_by_headings


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse command-line arguments.

    Document actions are options rather than subcommands on purpose: the
    ``prompt`` positional is free-form, so ``trans-lc-pilot split x.docx``
    would be indistinguishable from a prompt that starts with the word
    "split". An option keeps the prompt path untouched.

    Args:
        argv: Argument vector excluding the program name; typically
            ``sys.argv[1:]``.

    Returns:
        argparse.Namespace: Parsed arguments. ``prompt`` is a list of
        strings (empty when omitted, in which case ``main`` enters
        REPL mode unless a document action was given).
    """
    parser = argparse.ArgumentParser(prog="trans-lc-pilot")
    parser.add_argument("prompt", nargs="*", help="Prompt text; omit for REPL.")
    action = parser.add_mutually_exclusive_group()
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


def _run_oneshot(prompt: str) -> int:
    """Send one prompt to the agent, print the reply, and finish.

    Args:
        prompt: Natural-language prompt.

    Returns:
        int: ``0`` on success; failures propagate to :func:`main`.
    """
    print(run_once(build_agent(load_settings()), prompt))
    return 0


def _run_interactive() -> int:
    """Enter the interactive REPL.

    Returns:
        int: Exit code from the REPL loop.
    """
    return repl.run(load_settings())


def _dispatch(argv: list[str]) -> int:
    """Route an argument vector to a document action, one-shot, or REPL.

    Args:
        argv: Argument vector excluding the program name.

    Returns:
        int: ``0`` on success; ``1`` when the arguments do not fit the
        mode they selected.
    """
    args = parse_args(argv)
    if not args.split and args.level is not None:
        print("error: --level requires --split", file=sys.stderr)
        return 1
    elif not (args.convert or args.split) and args.quiet:
        print("error: --quiet requires --convert or --split", file=sys.stderr)
        return 1
    if args.list_levels or args.convert or args.split:
        return _run_document_action(args)
    if args.prompt:
        exit_code = _run_oneshot(" ".join(args.prompt))
    else:
        exit_code = _run_interactive()
    return exit_code


def _run_document_action(args: argparse.Namespace) -> int:
    """Run ``--list-levels``, ``--convert`` or ``--split`` against one file.

    Args:
        args: Parsed arguments holding exactly one of those options.

    Returns:
        int: ``0`` on success, ``1`` on a reported failure. Expected
        failures are printed without a traceback; anything else
        propagates to :func:`main`.
    """
    if args.prompt:
        joined = " ".join(args.prompt)
        print(
            f"error: document actions take no prompt, got {joined!r}",
            file=sys.stderr,
        )
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
    articles = split_by_headings(fragment, level=level)
    index_path = present.write_articles(proj, level=level)

    print(f"source: {proj.source_path}")
    print(f"level: {level}")
    print(f"articles: {len(articles)}")
    if any(article.is_preamble for article in articles):
        print("preamble: yes (content before the first heading)")
    if len(articles) == 1 and not articles[0].title:
        print(f"note: no heading at level {level}; document left whole")
    print("heading levels in document:")
    _print_levels(heading_counts(fragment))
    print(f"index: {index_path}")
    if open_after:
        print(present.open_in_browser(index_path))
    return 0


def main(argv: list[str] | None = None) -> int:
    """Entry point for the ``trans-lc-pilot`` console script.

    Ways in:

    * ``trans-lc-pilot`` — interactive REPL.
    * ``trans-lc-pilot "prompt"`` — one-shot agent call.
    * ``trans-lc-pilot --list-levels FILE`` — print FILE's heading
      levels and exit, writing nothing.
    * ``trans-lc-pilot --convert FILE [--quiet]`` — convert FILE to
      HTML via mammoth and open it, unless ``--quiet``.
    * ``trans-lc-pilot --split FILE [--level N] [--quiet]`` — split
      FILE into one HTML file per heading under ``<repo>/.tmp/``, and
      open the index page unless ``--quiet``.

    Args:
        argv: Optional argument vector excluding the program name;
            defaults to ``sys.argv[1:]`` when ``None``.

    Returns:
        int: Exit code; ``0`` for a clean run or REPL exit
        (``Ctrl-D`` / ``Ctrl-C``), ``1`` when an exception is caught
        and reported to ``stderr``.
    """
    argv = list(argv if argv is not None else sys.argv[1:])
    try:
        exit_code = _dispatch(argv)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
