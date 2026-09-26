# trans-lc-pilot

A Workbuddy Expert Plugin: LangChain-powered document processing behind two parallel CLI entry points.

## Setup

```bash
uv sync
cp .env.example .env   # then fill OPENAI_API_KEY — required by the agent entry only
```

## Usage

```bash
# docx → HTML (no LLM, no API key)
uv run trans-lc-pilot --list-levels FILE
uv run trans-lc-pilot --convert FILE [--quiet]
uv run trans-lc-pilot --split FILE [--level N] [--quiet]

# LangChain agent (requires OPENAI_API_KEY)
uv run trans-lc-pilot-agent "split this document at level 2 headings"
uv run trans-lc-pilot-agent            # interactive REPL
```

## Layout

```
src/trans_lc_pilot/
  docproj/           # document processing core
    source.py        # load a docx and convert it to an HTML fragment (mammoth)
    html_headings.py # split a fragment at headings
    article.py       # the Article model
    presentation.py  # write HTML, open a browser
  cli.py             # trans-lc-pilot entry (argparse, no LLM)
  langchain_agent/   # trans-lc-pilot-agent runtime (config, prompt, tools, agent, repl, entry)
agents/              # expert persona (Workbuddy)
skills/              # available capabilities
```

All writes land in `.tmp/` at the repo root (git-ignored). The source docx is never modified.
