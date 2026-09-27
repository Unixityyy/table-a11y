# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Parses <table> elements out of an HTML document using only the standard
library's html.parser, while tracking the *exact* byte offset of every
<th>/<td> opening tag in the original source.

We deliberately don't build a full DOM. We only care about table / tr / th /
td boundaries; everything else (inline formatting tags, text, nested
elements) is left completely untouched in the output. This keeps the tool
safe to run on real, messy, hand-authored or CMS-generated HTML: we never
reformat or rewrite anything except inserting a handful of new attributes
into existing opening tags.

Nested <table> elements (a table inside a cell of another table) are
supported: each <table> is parsed as its own independent record, using a
stack, so an inner table's rows are never mixed into the outer table's grid.
"""

from dataclasses import dataclass, field
from html.parser import HTMLParser


@dataclass
class Cell:
    tag: str  # 'th' or 'td'
    attrs: dict
    start_offset: int  # offset of the '<' that starts this opening tag
    starttag_text: str  # exact source text of the opening tag, e.g. '<td class="x">'
    text_parts: list = field(default_factory=list)

    # Filled in later by grid.build_grid():
    row_start: int = -1
    col_start: int = -1
    row_end: int = -1
    col_end: int = -1

    @property
    def rowspan_raw(self):
        try:
            return int(self.attrs.get("rowspan", 1))
        except (TypeError, ValueError):
            return 1

    @property
    def colspan_raw(self):
        try:
            n = int(self.attrs.get("colspan", 1))
        except (TypeError, ValueError):
            return 1
        return n if n >= 1 else 1

    @property
    def insert_offset(self):
        """Offset at which to splice in new attribute text: just before the
        tag's closing '>' (or before the '/>' of a self-closed tag)."""
        text = self.starttag_text
        if text.endswith("/>"):
            return self.start_offset + len(text) - 2
        return self.start_offset + len(text) - 1

    @property
    def text(self):
        return "".join(self.text_parts).strip()

    @property
    def existing_id(self):
        return self.attrs.get("id") or None

    @property
    def has_headers_attr(self):
        return "headers" in self.attrs

    @property
    def has_scope_attr(self):
        return "scope" in self.attrs


@dataclass
class Table:
    start_offset: int
    rows: list = field(default_factory=list)  # list[list[Cell]]


class _TableHTMLParser(HTMLParser):
    def __init__(self, line_offsets):
        super().__init__(convert_charrefs=True)
        self.line_offsets = line_offsets
        self.table_stack = []
        self.completed_tables = []
        self.current_cell = None
        self.existing_ids = set()

    def _abs_offset(self):
        line, col = self.getpos()
        return self.line_offsets[line - 1] + col

    def _note_id(self, attrs_dict):
        cid = attrs_dict.get("id")
        if cid:
            self.existing_ids.add(cid)

    def handle_starttag(self, tag, attrs):
        attrs_dict = {k: (v if v is not None else "") for k, v in attrs}
        self._note_id(attrs_dict)

        if tag == "table":
            self.table_stack.append(Table(start_offset=self._abs_offset()))
            self.current_cell = None
            return

        if not self.table_stack:
            return

        current_table = self.table_stack[-1]

        if tag == "tr":
            current_table.rows.append([])
            return

        if tag in ("th", "td"):
            if not current_table.rows:
                return  # stray cell outside any <tr>; ignore
            cell = Cell(
                tag=tag,
                attrs=attrs_dict,
                start_offset=self._abs_offset(),
                starttag_text=self.get_starttag_text(),
            )
            current_table.rows[-1].append(cell)
            self.current_cell = cell
            return

    def handle_startendtag(self, tag, attrs):
        # Handles self-closed tags like <br/> or an (unusual) self-closed td/th.
        self.handle_starttag(tag, attrs)
        if tag in ("th", "td"):
            self.current_cell = None

    def handle_endtag(self, tag):
        if tag in ("th", "td"):
            self.current_cell = None
        elif tag == "table":
            if self.table_stack:
                self.completed_tables.append(self.table_stack.pop())
            self.current_cell = None

    def handle_data(self, data):
        if self.current_cell is not None:
            self.current_cell.text_parts.append(data)


def _line_offsets(text):
    offsets = [0]
    idx = 0
    for line in text.splitlines(keepends=True):
        idx += len(line)
        offsets.append(idx)
    return offsets


def parse_tables(html_text):
    """Parse every <table> in html_text.

    Returns (tables, existing_ids):
      tables       -- list[Table], NOT necessarily in document order
                       (call sort_by_position() or sort by .start_offset)
      existing_ids -- set of every id="" value found anywhere in the document,
                       so generated ids never collide with authored ones.

    A <table> left unclosed at end of input is discarded rather than guessed at.
    """
    parser = _TableHTMLParser(_line_offsets(html_text))
    parser.feed(html_text)
    parser.close()
    return parser.completed_tables, parser.existing_ids
