import unittest

from table_a11y.algorithm import detect_header_blocks
from table_a11y.grid import build_grid
from table_a11y.parser import parse_tables


def _detect(html):
    tables, _ = parse_tables(html)
    table = tables[0]
    grid, num_rows, num_cols = build_grid(table)
    return detect_header_blocks(table.rows, grid, num_rows, num_cols)


class DetectHeaderBlocksTests(unittest.TestCase):
    def test_no_headers_at_all(self):
        html = "<table><tr><td>a</td><td>b</td></tr></table>"
        self.assertEqual(_detect(html), (0, 0))

    def test_single_header_row_only(self):
        html = (
            "<table><tr><th>Name</th><th>Age</th></tr>"
            "<tr><td>Alice</td><td>5</td></tr></table>"
        )
        self.assertEqual(_detect(html), (1, 0))

    def test_single_header_column_only(self):
        html = (
            "<table><tr><th>Alice</th><td>5</td></tr>"
            "<tr><th>Bob</th><td>8</td></tr></table>"
        )
        self.assertEqual(_detect(html), (0, 1))

    def test_row_and_column_headers_with_empty_corner(self):
        html = (
            "<table>"
            "<tr><th></th><th>Age</th></tr>"
            "<tr><th>Alice</th><td>5</td></tr>"
            "</table>"
        )
        self.assertEqual(_detect(html), (1, 1))

    def test_multilevel_column_headers(self):
        html = (
            "<table>"
            "<tr><th></th><th colspan='2'>Mars</th><th colspan='2'>Venus</th></tr>"
            "<tr><th>Item</th><th>Produced</th><th>Sold</th><th>Produced</th><th>Sold</th></tr>"
            "<tr><td>Teddy Bears</td><td>50000</td><td>30000</td><td>100000</td><td>80000</td></tr>"
            "</table>"
        )
        # Two full header rows; the first data-role column (col 0, 'Item'/'Teddy
        # Bears') is <th> in the header rows but plain <td> in the body, so it
        # is NOT counted as a header *column*.
        self.assertEqual(_detect(html), (2, 0))

    def test_does_not_misdetect_ordinary_data_row_as_header(self):
        html = (
            "<table><tr><th>Name</th><th>Age</th></tr>"
            "<tr><td>Alice</td><td>5</td></tr>"
            "<tr><td>Bob</td><td>8</td></tr></table>"
        )
        header_rows, header_cols = _detect(html)
        self.assertEqual(header_rows, 1)


if __name__ == "__main__":
    unittest.main()
