import re
import unittest

from table_a11y.fixer import fix_html


def _attr(html, tag_text_snippet, attr):
    """Find the tag whose text content includes tag_text_snippet and return
    one of its attribute values (or None). Small test helper, not part of
    the library."""
    idx = html.find(tag_text_snippet)
    self_check = html.rfind("<", 0, idx)
    tag_end = html.find(">", self_check)
    tag_text = html[self_check : tag_end + 1]
    m = re.search(attr + r'="([^"]*)"', tag_text)
    return m.group(1) if m else None


class SimpleTableTests(unittest.TestCase):
    def test_row_and_column_headers_get_scope(self):
        html = (
            "<table>"
            "<tr><th></th><th>Age</th><th>Birthday</th></tr>"
            "<tr><th>Jackie</th><td>5</td><td>April 5</td></tr>"
            "<tr><th>Beth</th><td>8</td><td>January 14</td></tr>"
            "</table>"
        )
        fixed, report = fix_html(html)

        self.assertEqual(report["tables"][0]["mode"], "scope")
        self.assertEqual(report["tables"][0]["status"], "fixed")

        self.assertEqual(_attr(fixed, ">Age<", "scope"), "col")
        self.assertEqual(_attr(fixed, ">Birthday<", "scope"), "col")
        self.assertEqual(_attr(fixed, ">Jackie<", "scope"), "row")
        self.assertEqual(_attr(fixed, ">Beth<", "scope"), "row")
        # no id/headers noise added for a simple table
        self.assertNotIn("headers=", fixed)
        # the empty decorative corner cell is left alone, not given a
        # meaningless scope="col"
        self.assertIn("<th></th>", fixed)

    def test_idempotent_on_second_run(self):
        html = (
            "<table><tr><th>Name</th><th>Age</th></tr>"
            "<tr><td>Alice</td><td>5</td></tr></table>"
        )
        once, _ = fix_html(html)
        twice, report2 = fix_html(once)
        self.assertEqual(once, twice)
        self.assertEqual(report2["tables"][0]["status"], "unchanged")

    def test_respects_existing_scope_and_headers(self):
        html = (
            "<table>"
            '<tr><th scope="col">Name</th><th>Age</th></tr>'
            '<tr><td headers="custom-id">Alice</td><td>5</td></tr>'
            "</table>"
        )
        fixed, _ = fix_html(html)
        # Name already had scope="col" -- must not be duplicated on that tag.
        name_tag_end = fixed.find(">", fixed.find("<th"))
        name_tag = fixed[fixed.find("<th") : name_tag_end + 1]
        self.assertEqual(name_tag.count('scope="col"'), 1)
        # Age had no scope at all, so it's fair game and should gain one.
        self.assertEqual(_attr(fixed, ">Age<", "scope"), "col")
        # existing headers="custom-id" left completely alone
        self.assertIn('headers="custom-id"', fixed)

    def test_no_th_at_all_is_skipped_not_guessed(self):
        html = "<table><tr><td>a</td><td>b</td></tr></table>"
        fixed, report = fix_html(html)
        self.assertEqual(fixed, html)  # untouched
        self.assertEqual(report["tables"][0]["status"], "skipped")
        self.assertIn("no <th>", report["tables"][0]["reason"])


class ComplexTableTests(unittest.TestCase):
    def setUp(self):
        self.html = (
            "<table>"
            "<tr><th></th><th colspan='2'>Mars</th><th colspan='2'>Venus</th></tr>"
            "<tr><th>Produced</th><th>Sold</th><th>Produced</th><th>Sold</th></tr>"
            "<tr><th>Teddy Bears</th><td>50000</td><td>30000</td><td>100000</td><td>80000</td></tr>"
            "<tr><th>Board Games</th><td>10000</td><td>5000</td><td>12000</td><td>9000</td></tr>"
            "</table>"
        )
        # note: row 0's corner is <th></th> (empty) and Produced/Sold sit in
        # row 1 at columns 1..4 (column 0 of row 1 is 'Teddy Bears'-style
        # row-header column, so row 1 must NOT repeat a corner cell there --
        # wait: this fixture has only 4 th's in row 1, meaning column 0 in
        # row1 is implicitly the row-header column starting at row 2. Let's
        # make row1 explicit instead to avoid ambiguity:
        self.html = (
            "<table>"
            "<tr><th rowspan='2'></th><th colspan='2'>Mars</th><th colspan='2'>Venus</th></tr>"
            "<tr><th>Produced</th><th>Sold</th><th>Produced</th><th>Sold</th></tr>"
            "<tr><th>Teddy Bears</th><td>50000</td><td>30000</td><td>100000</td><td>80000</td></tr>"
            "<tr><th>Board Games</th><td>10000</td><td>5000</td><td>12000</td><td>9000</td></tr>"
            "</table>"
        )

    def test_detects_complex_mode(self):
        fixed, report = fix_html(self.html)
        self.assertEqual(report["tables"][0]["mode"], "headers")
        self.assertEqual(report["tables"][0]["status"], "fixed")
        self.assertNotIn("scope=", fixed)

    def test_second_level_header_points_to_parent(self):
        fixed, _ = fix_html(self.html)
        mars_id = _attr(fixed, ">Mars<", "id")
        venus_id = _attr(fixed, ">Venus<", "id")
        self.assertIsNotNone(mars_id)
        self.assertIsNotNone(venus_id)

        produced_cells = [m.start() for m in re.finditer(">Produced<", fixed)]
        self.assertEqual(len(produced_cells), 2)

        first_produced_headers = _attr(fixed, ">Produced<", "headers")
        self.assertEqual(first_produced_headers, mars_id)

        second_produced_start = produced_cells[1]
        tag_start = fixed.rfind("<", 0, second_produced_start)
        tag_end = fixed.find(">", tag_start)
        second_tag = fixed[tag_start : tag_end + 1]
        m = re.search(r'headers="([^"]*)"', second_tag)
        self.assertEqual(m.group(1), venus_id)

    def test_data_cell_gets_both_column_and_row_headers(self):
        fixed, _ = fix_html(self.html)
        mars_id = _attr(fixed, ">Mars<", "id")
        produced_id = _attr(fixed, ">Produced<", "id")
        teddy_id = _attr(fixed, ">Teddy Bears<", "id")

        headers_50000 = _attr(fixed, ">50000<", "headers")
        self.assertIsNotNone(headers_50000)
        ids_present = headers_50000.split()
        self.assertIn(mars_id, ids_present)
        self.assertIn(produced_id, ids_present)
        self.assertIn(teddy_id, ids_present)

    def test_row_header_column_cells_get_plain_id_no_self_reference(self):
        fixed, _ = fix_html(self.html)
        teddy_headers = _attr(fixed, ">Teddy Bears<", "headers")
        self.assertIsNone(teddy_headers)  # it's the sole row header, nothing above it

    def test_generated_ids_do_not_collide_with_existing_ids(self):
        html = (
            "<table>"
            '<tr><th id="hdr-mars">Mars</th><th>Venus</th></tr>'
            "<tr><td>1</td><td>2</td></tr>"
            "</table>"
        )
        fixed, _ = fix_html(html)
        venus_id = _attr(fixed, ">Venus<", "id")
        self.assertNotEqual(venus_id, "hdr-mars")
        self.assertEqual(fixed.count('id="hdr-mars"'), 1)


class DocumentPreservationTests(unittest.TestCase):
    def test_only_table_tags_are_touched(self):
        html = (
            "<html><body>\n"
            "<p>Some <b>text</b> before.</p>\n"
            "<table><tr><th>Name</th><th>Age</th></tr>"
            "<tr><td>Alice</td><td>5</td></tr></table>\n"
            "<p>Some text after.</p>\n"
            "</body></html>"
        )
        fixed, _ = fix_html(html)
        self.assertIn("<p>Some <b>text</b> before.</p>", fixed)
        self.assertIn("<p>Some text after.</p>", fixed)
        self.assertTrue(fixed.startswith("<html><body>\n"))

    def test_multiple_independent_tables_in_one_document(self):
        html = (
            "<table><tr><th>Name</th><th>Age</th></tr><tr><td>Alice</td><td>5</td></tr></table>"
            "<table><tr><th>City</th><th>Pop</th></tr><tr><td>Foo</td><td>10</td></tr></table>"
        )
        fixed, report = fix_html(html)
        self.assertEqual(len(report["tables"]), 2)
        self.assertEqual(_attr(fixed, ">Age<", "scope"), "col")
        self.assertEqual(_attr(fixed, ">Pop<", "scope"), "col")


if __name__ == "__main__":
    unittest.main()
