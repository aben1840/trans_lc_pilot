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
uv run trans-lc-pilot inspect  FILE
uv run trans-lc-pilot preview  FILE [--workspace DIR] [--quiet]
uv run trans-lc-pilot split    FILE [--level N] [--as NAME] [--workspace DIR]
                                    [--quiet] [--force]
uv run trans-lc-pilot assemble BUNDLE_DIR [--out FILE] [--template FILE]
                                    [--workspace DIR] [--quiet] [--force]

# --workspace DIR roots every artifact (default: the current working directory).
# inspect writes nothing, so it takes no workspace.
uv run trans-lc-pilot split report.docx --workspace ./work

# LangChain agent (requires OPENAI_API_KEY)
uv run trans-lc-pilot-agent "split this document at level 2 headings"
uv run trans-lc-pilot-agent            # interactive REPL
```

## The workspace

Everything one working set produces lands under a single root — `--workspace DIR`,
the current working directory by default:

```
<workspace>/
  index.html      aggregate view: every bundle, its source, its assembly
  sources/        the documents that were split, and .origins.json
  bundles/        one directory per (source, heading level)
  output/         docx assembled from a bundle
  .tmp/           scratch: the HTML previews `preview` writes
```

A split writes a **bundle**: a directory holding one HTML file per piece, an
`index.html` linking them, a `manifest.json` recording their order, and a copy of
the source document. Edit the pieces, then assemble them back into a new docx —
the bundled copy supplies the styles, so page setup, headers, footers and theme
survive.

Splitting **ingests** the document: it is copied into `sources/` and the bundle
records that copy, so the bundle stays reproducible after the file you named
moves or changes. Splitting the same content again is a no-op. Different content
under a name already taken is refused — pass `--as NAME` to keep both, or delete
the stored copy to refresh it. `preview` does not ingest: a glance does not
commit the document to the workspace.

A split refuses a bundle directory that already holds files; an assembly refuses
an existing output file. Both need `--force`. `split` takes no `--out` — a bundle
has to live inside the workspace, or the aggregate index would not see it. An
assembled docx is a deliverable, so `assemble --out` may put it anywhere.

Fidelity is best-effort and bounded by what HTML can express: headings,
paragraphs, bold/italic/underline, lists, tables and inlined images are carried
over; numbering, footnotes, text boxes and section breaks are not. Every
`assemble` run prints a `warning:` line for each construct it could not carry,
so nothing is lost in silence. The source docx is never modified.

## Layout

```
src/trans_lc_pilot/
  docproj/           # document processing core — knows no paths of its own
    source_doc.py    # load a docx and convert it to an HTML fragment (mammoth)
    html_headings.py # split a fragment at headings
    article.py       # the Article model
    bundle.py        # the bundle: manifest, template copy, index, pieces, and
                     # the operations on it (write_bundle / assemble_docx)
    docx_styles.py   # resolve a template's styles (headings by outline level)
    docx_body.py     # HTML elements → docx body content
    presentation.py  # serialize HTML, open files
  workspace/         # where artifacts go: the root, ingest, the aggregate index
  cli.py             # trans-lc-pilot entry (argparse, no LLM)
  langchain_agent/   # trans-lc-pilot-agent runtime (config, prompt, tools, agent, repl, entry)
agents/              # expert persona (Workbuddy)
skills/              # available capabilities
```

`docproj` acts on the paths a caller hands it and never derives one of its own;
`workspace` decides those paths. A workspace root may hold the user's documents,
so `sources/`, `bundles/`, `output/`, `.tmp/` and the root `index.html` are
git-ignored in this repo.
