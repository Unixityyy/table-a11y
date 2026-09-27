# SPDX-License-Identifier: AGPL-3.0-or-later
import argparse
import json
import sys

from .fixer import fix_html


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="table-a11y",
        description=(
            "Add missing scope/id/headers attributes to HTML <table> elements "
            "so screen readers can correctly announce header relationships, "
            "including tables with multi-level or spanning headers."
        ),
    )
    parser.add_argument("input", help="Path to an HTML file, or - for stdin")
    parser.add_argument(
        "-o", "--output", help="Where to write the fixed HTML (default: stdout)"
    )
    parser.add_argument(
        "--report", help="Write a JSON report of what changed/was skipped to this path"
    )
    args = parser.parse_args(argv)

    html_text = sys.stdin.read() if args.input == "-" else open(
        args.input, "r", encoding="utf-8"
    ).read()

    fixed_html, report = fix_html(html_text)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(fixed_html)
    else:
        sys.stdout.write(fixed_html)

    if args.report:
        with open(args.report, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
    elif args.output:
        for t in report["tables"]:
            line = f"table {t['table_index']}: {t['status']}"
            if t.get("mode"):
                line += f" ({t['mode']})"
            if t.get("reason"):
                line += f" -- {t['reason']}"
            sys.stderr.write(line + "\n")


if __name__ == "__main__":
    main()
