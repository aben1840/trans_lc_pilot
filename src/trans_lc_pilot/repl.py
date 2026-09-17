"""The project's single interactive REPL.

Lines beginning with ``/`` are commands; any other line is sent to the
agent as a prompt. ``/docproj FILE`` loads a document, after which
``/render`` operates on it. Every command is a slash command and the
prompt never changes — there is no separate mode.

The agent is built lazily, on the first natural-language line, so a
document can be loaded and rendered without ``OPENAI_API_KEY``.
"""
from __future__ import annotations

import sys
import termios
import tty
from collections.abc import Callable

from .agent import build_agent, run_once
from .config import Settings
from .docproj import DocProj, present, read

HELP = """\
Commands:
  /docproj FILE        Load a document for inspection.
  /render html         Render the loaded projection to HTML in a temp file.
  /render html --open  Same, then open it in the default browser.
  /help                Show this message.
  /quit                Exit the REPL (Ctrl-D / Ctrl-C also work).
Any other line is sent to the agent as a prompt.
"""


class Session:
    """Mutable REPL state.

    Attributes:
        proj: The loaded projection, or ``None`` when nothing is loaded.
    """

    def __init__(
        self,
        settings: Settings,
        agent_factory: Callable[[Settings], object] = build_agent,
        runner: Callable[[object, str], str] = run_once,
    ) -> None:
        """Initialize the session.

        Args:
            settings: Runtime configuration for the agent.
            agent_factory: Builds the agent on first use.
            runner: Sends a prompt to the agent and returns its reply.
        """
        self.settings = settings
        self.proj: DocProj | None = None
        self._agent_factory = agent_factory
        self._runner = runner
        self._agent: object | None = None

    def get_agent(self) -> object:
        """Return the agent, building it on first use.

        Returns:
            object: The compiled agent.
        """
        if self._agent is None:
            self._agent = self._agent_factory(self.settings)
        return self._agent

    def ask(self, line: str) -> str:
        """Send ``line`` to the agent and return its reply.

        Args:
            line: Natural-language prompt.

        Returns:
            str: The agent's final assistant text.
        """
        return self._runner(self.get_agent(), line)


def _cmd_docproj(session: Session, rest: list[str]) -> None:
    """Load a document into the session.

    Args:
        session: Current REPL session.
        rest: Arguments after ``/docproj``; expects one path.
    """
    if len(rest) != 1:
        print("usage: /docproj <FILE>")
    else:
        try:
            session.proj = read(rest[0])
            blocks = len(session.proj.blocks)
            print(f"loaded {session.proj.source_path} ({blocks} blocks)")
        except FileNotFoundError:
            print(f"error: file not found: {rest[0]}")
        except (NotImplementedError, ValueError) as exc:
            print(f"error: {exc}")


def _cmd_render(session: Session, rest: list[str]) -> None:
    """Render the loaded projection.

    Args:
        session: Current REPL session.
        rest: Arguments after ``/render``; ``<format> [--open]``.
    """
    if session.proj is None:
        print("error: no document loaded (use /docproj FILE)")
    else:
        fmt = rest[0] if rest else ""
        open_flag = "--open" in rest[1:]
        if fmt == "html":
            path = present.write_html(session.proj)
            print(f"written: {path}")
            if open_flag:
                print(present.open_in_browser(path))
        else:
            print(f"error: unsupported format {fmt!r}; available: html")


def _handle_command(session: Session, line: str) -> bool:
    """Run a ``/``-prefixed command.

    Args:
        session: Current REPL session.
        line: The input line, stripped but not yet tokenized.

    Returns:
        bool: ``True`` to keep the REPL running, ``False`` to exit.
    """
    tokens = line.split()
    command, rest = tokens[0], tokens[1:]
    if command in {"/quit", "/exit"}:
        return False
    elif command == "/help":
        print(HELP, end="")
    elif command == "/docproj":
        _cmd_docproj(session, rest)
    elif command == "/render":
        _cmd_render(session, rest)
    else:
        print(f"unknown command: {command!r} (try '/help')")
    return True


def _enable_utf8_line_editing() -> None:
    """Enable ``IUTF8`` on the controlling TTY, when there is one.

    Without it the kernel's line discipline deletes one byte at a time,
    leaving orphan continuation bytes so wide CJK characters appear to
    "half-delete".
    """
    if sys.stdin.isatty():
        try:
            attrs = termios.tcgetattr(sys.stdin.fileno())
            attrs[0] |= tty.IUTF8
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSANOW, attrs)
        except (termios.error, AttributeError, OSError):
            pass


def run(
    settings: Settings,
    *,
    agent_factory: Callable[[Settings], object] = build_agent,
    runner: Callable[[object, str], str] = run_once,
) -> int:
    """Run the REPL until EOF, ``Ctrl-C``, or a quit command.

    Args:
        settings: Runtime configuration; used only when the agent is
            first needed.
        agent_factory: Builds the agent on first use. Injectable for
            tests.
        runner: Sends a prompt to the agent. Injectable for tests.

    Returns:
        int: ``0`` on a clean exit.
    """
    session = Session(settings, agent_factory, runner)

    print("trans-lc-pilot REPL. Ctrl-D to exit.")
    _enable_utf8_line_editing()
    while True:
        try:
            line = input("> ").strip()
        except EOFError:
            print()
            return 0
        except KeyboardInterrupt:
            print()
            return 0
        if not line:
            continue
        if line.startswith("/"):
            if not _handle_command(session, line):
                return 0
        else:
            try:
                print(session.ask(line))
            except Exception as exc:
                print(f"error: {exc}", file=sys.stderr)
