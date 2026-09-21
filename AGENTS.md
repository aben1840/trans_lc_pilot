# Repository Guidelines

Contributor guide for `trans-lc-pilot`, a minimal LangChain tool-calling agent
served through a small CLI. Keep changes tight, typed, and environment-driven.

## Working Agreement

**Clarify before acting.** When a request is ambiguous, or a decision has more
than one defensible answer, stop and ask before proceeding — do not pick one at
random. State the options and their trade-offs, then let the human decide. This
covers naming, module layout, file formats, dependency choices, and scope, not
just commits.

Answer from the repository when the repository already answers it (existing
style, prior decisions, `git log`); ask only about genuine forks in the road.

When a decision cannot wait, make it visible in the response: say what was
chosen, what the alternatives were, and what changing course later would cost.

## Skills

项目的 skills 存放在 `skills/<skill-name>/SKILL.md`，与任何特定 agent 的目录约定无关。每个 skill 描述一项可用能力、适用场景、执行步骤和注意事项。当前提供：

- **split-docx** — 按标题拆分 docx 为多个 HTML，附带索引页

新增 skill 时，在 `skills/` 下新建 kebab-case 目录，内含一份 `SKILL.md`（YAML frontmatter + Markdown 正文），然后更新本节清单。

## Project Structure & Module Organization

The project follows a `src/`-layout Python package. All application code lives
under `src/trans_lc_pilot/`:

- `config.py` — frozen `Settings` dataclass loaded from `.env` via `python-dotenv`.
- `tools.py` — `@tool` definitions and the `default_tools()` registry.
- `agent.py` — `build_llm`, `build_agent`, and `run_once`; owns the system prompt.
- `cli.py` — argparse entry point and REPL loop (script: `trans-lc-pilot`).

Top-level files: `pyproject.toml` (Hatchling build, project metadata, script
entry point), `uv.lock` (pinned deps), `README.md`, `.env.example`, `.gitignore`.

## Build, Test, and Development Commands

Use `uv` for everything; do not hand-edit `uv.lock` or call `pip` directly.

- `uv sync` — install/lock dependencies into the local `.venv`.
- `uv run trans-lc-pilot "prompt"` — one-shot invocation of the agent.
- `uv run trans-lc-pilot` — launch the interactive REPL.
- `cp .env.example .env` then fill `OPENAI_API_KEY` before first run.

There is no test runner wired up yet; see *Testing Guidelines* below.

## Coding Style & Naming Conventions

- Python ≥ 3.12. Every module starts with `from __future__ import annotations`.
- Type hints on all public functions and dataclass fields; prefer modern syntax
  (`str | None`, `list[str]`).
- `snake_case` for modules, functions, and variables; `PascalCase` for classes
  (e.g. `Settings`). Module filenames are short nouns (`agent.py`, `tools.py`).
- Keep functions small and pure where possible; side effects belong in `cli.py`.
- Express branching with `if … elif … else` chains. 
  - Prefer this:

    ```python
    if kind == "docx":
        reader = docx_to_docproj
    elif kind == "md":
        reader = md_to_docproj
    else:
        raise ValueError(f"unsupported kind: {kind}")
    return reader(path)
    ```

  - Not this:

    ```python
    if kind == "docx":
        return docx_to_docproj(path)
    if kind == "md":
        return md_to_docproj(path)
    raise ValueError(f"unsupported kind: {kind}")
    ```
  
- `ruff` is the configured linter (see `[tool.ruff]` in `pyproject.toml`).
  Run `uv run ruff check .` to lint, `uv run ruff check --fix .` to apply
  safe auto-fixes. Public functions, classes, and modules must carry
  Google-style docstrings (pydocstyle `D` rules, `convention = "google"`).
  No formatter is configured yet — keep 4-space indent, double-quoted
  strings, and trailing commas in multi-line literals.

## Testing Guidelines

No tests are checked in today. When adding them, place them under
`tests/` mirroring `src/trans_lc_pilot/` (e.g. `tests/test_tools.py`) and use
`pytest`. Name tests `test_<unit>_<behavior>` and keep them hermetic — mock the
LLM and never hit the network with real API keys. Run with `uv run pytest`.

## Commit & Pull Request Guidelines

The repository has no commits yet, so adopt a lightweight convention going
forward: short imperative subject (≤ 72 chars), optional body explaining *why*.
Suggested prefixes: `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`.
PRs should describe the user-visible change, link any tracking issue, and note
env or model-impacting changes (e.g. new required `OPENAI_*` variables).

**Review requirement:** every commit must go through human review and explicit
approval before it lands — no unattended or auto-commits. Agents and bots may
prepare commits (stage files, draft messages, show diffs) and may run
`git commit` **only when a human has explicitly asked them to in the current
turn** (e.g. "请提交当前变更", "commit these changes"). Otherwise, hold for a
reviewer to run `git commit` / merge.

## Security & Configuration Tips

- Never commit `.env`; it is git-ignored. Only `.env.example` belongs in the repo.
- `OPENAI_API_KEY` is required at runtime — `build_llm` raises if it is missing.
- `OPENAI_BASE_URL` lets you point at a compatible local or hosted endpoint;
  leave unset for OpenAI.