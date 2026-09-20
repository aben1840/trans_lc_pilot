---
description: Split a .docx into one HTML file per heading, plus an index page. Use when the user asks to 分割 or 拆分 a docx, to 按标题拆成几篇, or to "split this docx by headings" / "break this document into articles".
allowed-tools: Bash(uv run trans-lc-pilot *)
---

# Split a docx by headings

A split runs at **one heading level**, and which level is a judgement
call: the same document split at level 1 and at level 2 yields
different pieces, and neither is "the" right answer. The CLI therefore
reports what a document has and leaves the choice to the user. Never
pick a level silently.

## Steps

1. **Get the path.** If the user did not name a file, ask. Resolve
   relative paths against the repository root.

2. **Convert the docx and let it open.** This is the step that puts the
   document in front of the user:

   ```bash
   uv run trans-lc-pilot --convert <file>
   ```

   The command converts the source docx to HTML with mammoth — the
   document as a reader sees it, not a structural summary — and opens
   it in the browser. Say that it opened. Add `--quiet` only when no
   browser can appear (headless or remote).

   This is what the user reads while choosing a level in step 4. The
   split's `index.html` is a separate, later open — see step 5.

3. **Inspect the headings — never split blind.**

   ```bash
   uv run trans-lc-pilot --list-levels <file>
   ```

   Writes nothing. Prints one line per level present, e.g. `h2: 5`.
   `no headings found` means the document has no heading styles at all.

4. **Show the inventory and the candidates, then let the user choose.**
   The converted document is on screen, so point at it: say what each
   level would produce — e.g. "The document has H2×5 and no H1, so
   splitting at H2 gives 5 pieces while H1 has no boundary at all."
   Skip this question only when the user already named a level.

   Headings here are Word *heading styles* as mammoth maps them. Bold
   or oversized text is not a heading, so a document can legitimately
   have none — that is a fact about the document, not an error.

5. **Split — the index opens itself.**

   ```bash
   uv run trans-lc-pilot --split <file> --level N
   ```

   This writes the pieces and opens `index.html`, so the user can click
   through what was produced. Say that it opened. `--quiet` suppresses
   the open when no browser can appear (headless or remote).

6. **Report what actually happened**, from the command's own output.
   Two results are easy to misread, so call them out:

   - **`articles: 1`** together with a `note:` line — there was no
     heading at that level, so the document was left whole. Say so
     plainly, and repeat the levels the document does have so the user
     can retry with one of them.
   - **A preamble** (`000-preamble.html`) — whatever preceded the first
     heading. It is front matter, not an article; name it as such.

7. **Ask whether the split is right.** The index is on screen, so this
   is the moment to confirm: name how many pieces there are and ask
   whether that matches what they wanted. If not, the levels from step
   4 are the alternatives — re-run step 5 at a different one. Do not
   close the turn on the report alone.

## Notes

- Output lands in `<repo>/.tmp/`: `--convert` writes one
  `docproj-source-XXXX.html`, `--split` writes a directory
  `articles-XXXX/` holding one file per piece plus `index.html` linking
  them. Names are random and nothing is ever cleaned up. Both open in
  the browser at their own step — the document after step 2, the index
  after step 5 — and `--quiet` suppresses either open.
- Splitting produces HTML, not docx. Splitting a docx into sibling
  docx files is not implemented — do not promise it.
- `--level` is validated as 1-6; anything else is rejected by argparse
  before the document is touched.
- Failures print `error: ...` and exit non-zero. Relay the message
  rather than retrying against a path you guessed.
