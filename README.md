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
uv run trans-lc-pilot --split FILE [--level N] [--out DIR] [--quiet]
uv run trans-lc-pilot --assemble BUNDLE_DIR [--out FILE] [--template FILE] [--quiet]

# LangChain agent (requires OPENAI_API_KEY)
uv run trans-lc-pilot-agent "split this document at level 2 headings"
uv run trans-lc-pilot-agent            # interactive REPL
```

A split writes a **bundle**: a directory holding one HTML file per piece, an
`index.html` linking them, a `manifest.json` recording their order, and a copy of
the source document. Edit the pieces, then assemble them back into a new docx —
the bundled copy supplies the styles, so page setup, headers, footers and theme
survive. Bundles default to `<cwd>/bundles/<source-name>-h<level>/`; an assembly
defaults to `<cwd>/<bundle-name>.docx`. Neither overwrites existing output
without `--force`.

Fidelity is best-effort and bounded by what HTML can express: headings,
paragraphs, bold/italic/underline, lists, tables and inlined images are carried
over; numbering, footnotes, text boxes and section breaks are not. Every
`--assemble` run prints a `warning:` line for each construct it could not carry,
so nothing is lost in silence.

## Layout

```
src/trans_lc_pilot/
  docproj/           # document processing core
    source_doc.py    # load a docx and convert it to an HTML fragment (mammoth)
    html_headings.py # split a fragment at headings
    article.py       # the Article model
    bundle.py        # the bundle: manifest, template copy, index, pieces, and
                     # the operations on it (write_bundle / assemble_docx)
    docx_styles.py   # resolve a template's styles (headings by outline level)
    docx_body.py     # HTML elements → docx body content
    presentation.py  # serialize HTML, open files
  cli.py             # trans-lc-pilot entry (argparse, no LLM)
  langchain_agent/   # trans-lc-pilot-agent runtime (config, prompt, tools, agent, repl, entry)
agents/              # expert persona (Workbuddy)
skills/              # available capabilities
```

Previews (`--convert`) land in the repo's `.tmp/`; bundles and assembled
documents are written relative to the current working directory. Both `.tmp/` and
`bundles/` are git-ignored. The source docx is never modified.
