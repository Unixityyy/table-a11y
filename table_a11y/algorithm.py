# SPDX-License-Identifier: AGPL-3.0-or-later
"""
The actual accessibility logic.

Given a table's grid, this figures out:

1. Which leading rows form a "column header block" and which leading
   columns form a "row header block" -- looking only at how the table was
   actually marked up (which cells are <th>), never at guesses about
   content.

2. Whether the table is "simple" (one header row and/or one header column,
   no nesting) -- in which case WCAG guidance says plain `scope="col"` /
   `scope="row"` is the right, minimal fix -- or "complex" (multi-level or
   otherwise spanning headers), where `scope` can't fully describe the
   relationships and explicit `id` / `headers` pairs (WCAG technique H43)
   are required.

3. For complex tables, which header cell(s) govern each data cell, AND
   which higher-level header cell(s) govern each lower-level header cell
   (so "Actual" under "Points" correctly points back at "Points").

Cells that already carry a `headers` or `scope` attribute are left alone --
this tool only fills in gaps, it never overrides an author's explicit markup.
"""

from dataclasses import dataclass, field


@dataclass
class TableReport:
    status: str = "skipped"  # 'fixed' | 'unchanged' | 'skipped'
    mode: str = None  # 'scope' | 'headers' | None
    reason: str = None
    header_cells_updated: int = 0
    data_cells_updated: int = 0
    header_ids_added: int = 0


def _row_is_header_like(row_cells):
    """A row counts as a column-header row if every cell in it is a <th>,
    tolerating a blank <td> corner placeholder (a very common real-world
    pattern for the empty top-left cell of a table that has both column
    and row headers)."""
    if not row_cells:
        return False
    for c in row_cells:
        if c.tag == "th":
            continue
        if c.tag == "td" and not c.text:
            continue
        return False
    return True


def detect_header_blocks(rows, grid, num_rows, num_cols):
    header_row_count = 0
    for row_cells in rows:
        if _row_is_header_like(row_cells):
            header_row_count += 1
        else:
            break

    header_col_count = 0
    col = 0
    while col < num_cols:
        found_any = False
        ok = True
        for r in range(header_row_count, num_rows):
            owner = grid.get(r, {}).get(col)
            if owner is None:
                continue
            found_any = True
            if owner.tag != "th":
                ok = False
                break
        if ok and found_any:
            header_col_count += 1
            col += 1
        else:
            break

    return header_row_count, header_col_count


def _collect_distinct(cells_iter, exclude=None, seen=None):
    seen = seen if seen is not None else set()
    result = []
    for cell in cells_iter:
        if cell is None or cell is exclude:
            continue
        if id(cell) in seen:
            continue
        seen.add(id(cell))
        result.append(cell)
    return result


def plan_fixes(table, grid, num_rows, num_cols, id_generator):
    """Returns (insertions, report).

    insertions: list of (Cell, {attr_name: value}) -- attributes to splice
                into that cell's opening tag.
    report:     TableReport describing what happened, for the CLI/JSON report.
    """
    rows = table.rows
    report = TableReport()

    if num_rows == 0 or num_cols == 0:
        report.reason = "empty table (no rows/cells)"
        return [], report

    header_row_count, header_col_count = detect_header_blocks(
        rows, grid, num_rows, num_cols
    )

    if header_row_count == 0 and header_col_count == 0:
        report.reason = (
            "no <th> elements found -- mark up the header cells "
            "(<th> instead of <td>) before running this tool"
        )
        return [], report

    simple = header_row_count <= 1 and header_col_count <= 1

    cell_attrs = {}  # id(cell) -> [cell, {attr: value}]
    assigned_ids = {}  # id(cell) -> generated id string

    def set_attr(cell, key, value):
        entry = cell_attrs.setdefault(id(cell), [cell, {}])
        entry[1][key] = value

    def ensure_id(cell):
        if cell.existing_id:
            return cell.existing_id
        if id(cell) in assigned_ids:
            return assigned_ids[id(cell)]
        new_id = id_generator(cell.text)
        assigned_ids[id(cell)] = new_id
        set_attr(cell, "id", new_id)
        return new_id

    if simple:
        report.mode = "scope"
        # An empty header cell (typically a decorative top-left "dead
        # corner" in a table with both row and column headers) labels
        # nothing, so we leave it untouched rather than attaching a
        # meaningless scope="col"/"row" to it.
        if header_row_count == 1:
            for cell in rows[0]:
                if (
                    cell.tag == "th"
                    and cell.text
                    and not cell.has_scope_attr
                    and not cell.has_headers_attr
                ):
                    set_attr(cell, "scope", "col")
                    report.header_cells_updated += 1
        if header_col_count == 1:
            for r in range(header_row_count, num_rows):
                cell = grid.get(r, {}).get(0)
                if (
                    cell
                    and cell.tag == "th"
                    and cell.text
                    and cell.col_start == 0
                    and cell.row_start == r
                    and not cell.has_scope_attr
                    and not cell.has_headers_attr
                ):
                    set_attr(cell, "scope", "row")
                    report.header_cells_updated += 1

    else:
        report.mode = "headers"

        # Column-header block: assign ids, and chain sub-headers to their
        # parent header(s) above them.
        for r in range(header_row_count):
            for cell in rows[r]:
                if cell.tag != "th":
                    continue
                if r > 0 and not cell.has_headers_attr:
                    parents = _collect_distinct(
                        (
                            grid.get(rr, {}).get(cc)
                            for rr in range(0, cell.row_start)
                            for cc in range(cell.col_start, cell.col_end)
                        ),
                        exclude=cell,
                    )
                    if parents:
                        set_attr(cell, "headers", " ".join(ensure_id(p) for p in parents))
                        report.header_cells_updated += 1
                if not cell.existing_id:
                    ensure_id(cell)

        # Row-header block: same idea, chaining leftward.
        for c in range(header_col_count):
            for r in range(header_row_count, num_rows):
                cell = grid.get(r, {}).get(c)
                if cell is None or cell.tag != "th":
                    continue
                if cell.row_start != r or cell.col_start != c:
                    continue  # only handle each cell once, at its own origin
                if c > 0 and not cell.has_headers_attr:
                    parents = _collect_distinct(
                        (
                            grid.get(rr, {}).get(cc)
                            for cc in range(0, cell.col_start)
                            for rr in range(cell.row_start, cell.row_end)
                        ),
                        exclude=cell,
                    )
                    if parents:
                        set_attr(cell, "headers", " ".join(ensure_id(p) for p in parents))
                        report.header_cells_updated += 1
                if not cell.existing_id:
                    ensure_id(cell)

        # Data cells: gather governing column header(s) then row header(s).
        for r in range(header_row_count, num_rows):
            for c in range(header_col_count, num_cols):
                cell = grid.get(r, {}).get(c)
                if cell is None or cell.row_start != r or cell.col_start != c:
                    continue
                if cell.has_headers_attr:
                    continue

                seen = set()
                col_headers = _collect_distinct(
                    (
                        grid.get(rr, {}).get(cc)
                        for cc in range(cell.col_start, cell.col_end)
                        for rr in range(0, header_row_count)
                    ),
                    seen=seen,
                )
                row_headers = _collect_distinct(
                    (
                        grid.get(rr, {}).get(cc)
                        for rr in range(cell.row_start, cell.row_end)
                        for cc in range(0, header_col_count)
                    ),
                    seen=seen,
                )
                governing = col_headers + row_headers
                if governing:
                    set_attr(
                        cell, "headers", " ".join(ensure_id(h) for h in governing)
                    )
                    report.data_cells_updated += 1

    report.header_ids_added = sum(1 for _, attrs in cell_attrs.values() if "id" in attrs)
    changed = len(cell_attrs) > 0
    report.status = "fixed" if changed else "unchanged"

    insertions = [(cell, attrs) for cell, attrs in cell_attrs.values()]
    return insertions, report
