import unittest

from table_a11y.grid import build_grid
from table_a11y.parser import parse_tables


def _one_table(html):
    tables, _ = parse_tables(html)
    assert len(tables) == 1
    return tables[0]


class GridTests(unittest.TestCase):
    def test_simple_2x2(self):
        html = "<table><tr><td>a</td><td>b</td></tr><tr><td>c</td><td>d</td></tr></table>"
        table = _one_table(html)
        grid, num_rows, num_cols = build_grid(table)
        self.assertEqual(num_rows, 2)
        self.assertEqual(num_cols, 2)
        self.assertEqual(grid[0][0].text, "a")
        self.assertEqual(grid[0][1].text, "b")
        self.assertEqual(grid[1][0].text, "c")
        self.assertEqual(grid[1][1].text, "d")

    def test_colspan(self):
        html = "<table><tr><td colspan='2'>wide</td></tr><tr><td>a</td><td>b</td></tr></table>"
        table = _one_table(html)
        grid, num_rows, num_cols = build_grid(table)
        self.assertEqual(num_cols, 2)
        self.assertIs(grid[0][0], grid[0][1])
        self.assertEqual(grid[0][0].col_start, 0)
        self.assertEqual(grid[0][0].col_end, 2)

    def test_rowspan(self):
        html = (
            "<table>"
            "<tr><td rowspan='2'>tall</td><td>a</td></tr>"
            "<tr><td>b</td></tr>"
            "</table>"
        )
        table = _one_table(html)
        grid, num_rows, num_cols = build_grid(table)
        self.assertEqual(num_rows, 2)
        self.assertEqual(num_cols, 2)
        self.assertIs(grid[0][0], grid[1][0])
        self.assertEqual(grid[0][1].text, "a")
        self.assertEqual(grid[1][1].text, "b")

    def test_rowspan_zero_spans_to_end(self):
        html = (
            "<table>"
            "<tr><td rowspan='0'>tall</td><td>a</td></tr>"
            "<tr><td>b</td></tr>"
            "<tr><td>c</td></tr>"
            "</table>"
        )
        table = _one_table(html)
        grid, num_rows, num_cols = build_grid(table)
        self.assertEqual(num_rows, 3)
        self.assertIs(grid[0][0], grid[1][0])
        self.assertIs(grid[0][0], grid[2][0])

    def test_conflicting_cell_is_shifted_not_overlapped(self):
        # The second row's first <td> would sit under the rowspan=2 cell
        # from row 0 if placed literally -- exactly like a real browser,
        # we shift it into the next free column instead of overlapping.
        html = (
            "<table>"
            "<tr><td rowspan='2'>tall</td><td>a</td></tr>"
            "<tr><td>oops</td><td>b</td></tr>"
            "</table>"
        )
        table = _one_table(html)
        grid, num_rows, num_cols = build_grid(table)
        self.assertEqual(grid[1][0].text, "tall")  # rowspan cell still owns (1,0)
        self.assertEqual(grid[1][1].text, "oops")  # shifted right, not overlapping
        self.assertEqual(grid[1][2].text, "b")

    def test_nested_table_handled_independently(self):
        html = (
            "<table id='outer'><tr><td>"
            "<table id='inner'><tr><td>x</td></tr></table>"
            "</td><td>y</td></tr></table>"
        )
        tables, _ = parse_tables(html)
        self.assertEqual(len(tables), 2)
        # sort by position: outer starts first
        tables.sort(key=lambda t: t.start_offset)
        outer, inner = tables
        self.assertEqual(len(outer.rows[0]), 2)  # the two outer <td>s
        self.assertEqual(len(inner.rows[0]), 1)  # the one inner <td>


if __name__ == "__main__":
    unittest.main()
