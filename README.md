# table-a11y

Add the missing `scope` / `id` / `headers` attributes to HTML `<table>`
elements so screen readers can correctly announce which header goes with
which cell — including tables with **multi-level or spanning headers**,
where this is genuinely hard to get right by hand.

Zero dependencies. Pure Python standard library. Never rewrites or
reformats your document — it only inserts a handful of new attributes into
existing opening tags.

```bash
pip install .
table-a11y report.html -o report.fixed.html --report changes.json
```

or as a library:

```python
from table_a11y import fix_html

fixed_html, report = fix_html(original_html)
```

## The problem this solves

For a *simple* data table — one header row and/or one header column — the
fix is well known and well tooled: add `scope="col"` to the header row's
`<th>` cells and `scope="row"` to the header column's. Several linters and
even some CMS plugins already do this automatically.

For a *complex* table — one with multi-level column headers (e.g. "North"
split into "Revenue" / "Costs"), or any header that spans multiple rows or
columns — `scope` alone can't describe the relationship. The standard
accessibility technique (WCAG H43) is to give every header cell a unique
`id` and list the relevant header `id`s in each data cell's `headers`
attribute. This is exactly the kind of thing browsers already do
*implicitly* when `headers` is absent, using a fallback header-scanning
algorithm defined in the HTML spec — but that implicit algorithm is applied
inconsistently across screen readers, which is precisely why WCAG
recommends writing the associations out explicitly instead of relying on
it. Doing that by hand for a table with nested headers means carefully
tracing, for every single data cell, which header cells geometrically sit
above and to the left of it — and updating all of it again the moment a
column gets added.

This has been a known, named gap for a long time: accessibility
practitioners on public mailing lists and government accessibility
training materials have independently commented that hand-coding `id`/
`headers` for complex tables is tedious and error-prone, and that a tool to
compute it automatically "would be extremely helpful." As far as I could
find, nothing does this today — existing tools either only handle the
simple single-row/column case, or go the opposite direction (author a
table from a spec and generate markup for it, rather than fixing markup
that already exists).

This tool implements the geometry directly: it builds the actual on-screen
grid your table produces (resolving every `rowspan`/`colspan`), classifies
the leading rows/columns as header blocks purely from which cells are
already `<th>`, and then computes exactly which header cell(s) govern each
data cell — and which higher-level header cell(s) govern each lower-level
header cell, so a sub-header like "Costs" correctly points back at its
parent group header like "North".

## What it does, concretely

- **Simple table** (single header row and/or column, no nesting): adds
  `scope="col"` / `scope="row"` to the relevant `<th>` cells.
- **Complex table** (multi-level or spanning headers): assigns a stable
  `id` to every header cell that lacks one, and a `headers` attribute to
  every data cell listing the header(s) that govern it — plus `headers` on
  lower-level header cells pointing at their parent header(s).
- **Already-accessible tables**: cells that already carry `scope` or
  `headers` are left completely untouched — this tool only fills gaps, it
  never second-guesses an author's explicit markup. Running it twice on
  its own output is a no-op.
- **Empty decorative corner cells** (the common blank top-left `<th>` in a
  table that has both row and column headers) are left alone rather than
  given a meaningless `scope`.
- **Tables with no `<th>` at all**: skipped, with a clear reason in the
  report, rather than guessing at structure. Guessing wrong is worse than
  not touching it.
- **Everything else in the document** — surrounding text, inline tags
  inside cells, whitespace, other elements — is byte-for-byte untouched.

## Usage

```bash
table-a11y INPUT.html                       # fixed HTML to stdout
table-a11y INPUT.html -o OUTPUT.html        # fixed HTML to a file
table-a11y INPUT.html -o OUTPUT.html --report report.json
table-a11y - < INPUT.html                   # read from stdin
```

`report.json` looks like:

```json
{
  "tables": [
    {
      "table_index": 0,
      "status": "fixed",
      "mode": "headers",
      "reason": null,
      "header_cells_updated": 4,
      "data_cells_updated": 8,
      "header_ids_added": 9
    }
  ]
}
```

See `examples/` for a simple table, a complex nested-header financial
table, and a table with no headers at all (to see the "skipped" path).

## Limitations (read before relying on this for compliance)

- Assumes explicit closing tags on `<tr>`/`<th>`/`<td>` (true of essentially
  all generated/CMS/static-site-generator HTML; less true of some very
  old hand-written HTML that relies on tag omission). Tables that don't
  parse cleanly are skipped with a reason, not silently mangled.
- Header-block detection is purely structural (which cells are `<th>`,
  and where). It cannot help a table that has no `<th>` elements at
  all — mark up your headers first.
- Nested `<table>` elements (a table inside a cell of another table) are
  each processed independently and correctly, but this tool does not try
  to relate one to the other.
- This is one input to accessibility, not a compliance guarantee. Please
  still test with a real screen reader, and pair this with a checker like
  axe-core or WAVE for the things it doesn't cover (captions, contrast,
  focus order, etc).

## Running the tests

```bash
python -m unittest discover -s tests -v
```

## License

AGPL-3.0-or-later — see `LICENSE`. This means: anyone can use, modify, and
redistribute this freely, but if you run a modified version of it as a
network service, you must make the source of your modified version
available to the people using that service (that's what distinguishes
AGPL from plain GPL). The "-or-later" means you're not locked to version
3 specifically — you (or anyone downstream) may instead apply the terms
of any later version the FSF publishes, per the standard clause in
`LICENSE` itself.
