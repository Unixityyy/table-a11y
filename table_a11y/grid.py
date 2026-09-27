# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Turns a Table's list of authored rows (each a list of Cell, exactly as
written in the source) into the *actual* 2D grid a browser would render,
by resolving rowspan/colspan the same way the HTML table model does.

grid[r][c] -> the Cell that occupies grid position (r, c). A single Cell
that spans multiple rows/columns appears at every (r, c) it covers, so
"who owns column 3 in row 5" is always a plain dict lookup.
"""


class GridError(Exception):
    """Raised when a table's markup can't be turned into a consistent grid
    (e.g. two cells whose spans genuinely overlap -- almost always a sign
    of hand-authoring error in the source table)."""


def build_grid(table):
    rows = table.rows
    num_input_rows = len(rows)
    grid = {}
    max_col = 0

    for r, row_cells in enumerate(rows):
        row_map = grid.setdefault(r, {})
        col = 0
        for cell in row_cells:
            while col in row_map:
                col += 1

            rowspan = cell.rowspan_raw
            if rowspan == 0:
                rowspan = max(1, num_input_rows - r)  # "until end of table"
            colspan = cell.colspan_raw

            cell.row_start = r
            cell.col_start = col
            cell.row_end = r + rowspan
            cell.col_end = col + colspan

            for rr in range(cell.row_start, cell.row_end):
                target_row_map = grid.setdefault(rr, {})
                for cc in range(cell.col_start, cell.col_end):
                    if cc in target_row_map:
                        raise GridError(
                            f"overlapping cells at row {rr}, column {cc} "
                            f"(check rowspan/colspan values)"
                        )
                    target_row_map[cc] = cell

            max_col = max(max_col, cell.col_end)
            col = cell.col_end

    num_rows = (max(grid.keys()) + 1) if grid else 0
    return grid, num_rows, max_col
