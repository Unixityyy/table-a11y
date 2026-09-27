# SPDX-License-Identifier: AGPL-3.0-or-later
from .algorithm import plan_fixes
from .grid import GridError, build_grid
from .idgen import make_id_generator
from .parser import parse_tables


def _attrs_to_string(attrs):
    parts = []
    for key, value in attrs.items():
        escaped = str(value).replace("&", "&amp;").replace('"', "&quot;")
        parts.append(f'{key}="{escaped}"')
    return " " + " ".join(parts)


def fix_html(html_text):
    """Add missing scope/id/headers attributes to every <table> in html_text.

    Returns (fixed_html, report) where report is a JSON-serializable dict:
        {"tables": [{"table_index": 0, "status": "fixed", "mode": "scope", ...}, ...]}

    Only ever *adds* attributes to existing opening tags; never removes,
    reorders, or reformats anything else in the document.
    """
    tables, existing_ids = parse_tables(html_text)
    tables.sort(key=lambda t: t.start_offset)
    id_generator = make_id_generator(existing_ids)

    pending_insertions = []  # (offset, text_to_insert)
    table_reports = []

    for index, table in enumerate(tables):
        try:
            grid, num_rows, num_cols = build_grid(table)
        except GridError as exc:
            table_reports.append(
                {"table_index": index, "status": "skipped", "reason": str(exc)}
            )
            continue

        insertions, report = plan_fixes(table, grid, num_rows, num_cols, id_generator)
        for cell, attrs in insertions:
            pending_insertions.append((cell.insert_offset, _attrs_to_string(attrs)))

        table_reports.append(
            {
                "table_index": index,
                "status": report.status,
                "mode": report.mode,
                "reason": report.reason,
                "header_cells_updated": report.header_cells_updated,
                "data_cells_updated": report.data_cells_updated,
                "header_ids_added": report.header_ids_added,
            }
        )

    # Apply from the end of the document backwards so earlier offsets stay valid.
    pending_insertions.sort(key=lambda item: item[0], reverse=True)
    result = html_text
    for offset, text in pending_insertions:
        result = result[:offset] + text + result[offset:]

    return result, {"tables": table_reports}
