# SPDX-License-Identifier: AGPL-3.0-or-later
import re

_slug_re = re.compile(r"[^a-z0-9]+")


def make_id_generator(existing_ids):
    """Returns a function text -> unique id string, that never collides with
    any id already present in the document (existing_ids) or any id it has
    already handed out."""
    used = set(existing_ids)

    def generate(text):
        base = _slug_re.sub("-", text.strip().lower()).strip("-")
        candidate = f"hdr-{base}" if base else "hdr"
        original = candidate
        n = 2
        while candidate in used:
            candidate = f"{original}-{n}"
            n += 1
        used.add(candidate)
        return candidate

    return generate
