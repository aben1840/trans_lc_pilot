# trans-lc-pilot

Minimal LangChain agent pilot.

## Setup

```bash
uv sync
cp .env.example .env  # then fill OPENAI_API_KEY
```

## Usage

```bash
# one-shot
uv run trans-lc-pilot "What time is it in UTC?"

# REPL
uv run trans-lc-pilot

# override model
uv run trans-lc-pilot --model gpt-4o "hello"
```

## Layout

```
src/trans_lc_pilot/
  config.py   # env-driven Settings
  tools.py    # @tool definitions
  agent.py    # build_agent / run_once
  cli.py      # entry point
```
