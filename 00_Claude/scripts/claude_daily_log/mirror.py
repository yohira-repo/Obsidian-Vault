"""Vault 内ミラーノート（00_Claude/projects/*.md）の更新。"""
import os
from typing import Dict, List, Tuple

import sections as sections_module

MIRROR_DIR = os.path.join("00_Claude", "projects")


def mirror_relpath(source_id: str) -> str:
    return os.path.join(MIRROR_DIR, source_id.replace("/", "-") + ".md")


def _index(lines: List[str]) -> Dict[Tuple[str, str], Tuple[int, int]]:
    """既存の日付付き見出しを {(日付, タイトル): (見出し行, 終端行)} に索引化する。"""
    heads = sections_module.scan_headings(lines)

    result = {}
    for position, (index, date, title) in enumerate(heads):
        end = heads[position + 1][0] if position + 1 < len(heads) else len(lines)
        if date is not None:
            result[(date, title)] = (index, end)
    return result


def update_mirror(vault: str, source_id: str, entries: List) -> Tuple[int, int]:
    """未収録セクションを追記し、本文が変化したセクションは置換する。

    Invariant: Each entry's body must not contain lines starting with '## '.
    This is guaranteed by sections.parse_sections, which always terminates
    a section's body before the next '## ' heading marker.
    """
    if not entries:
        return (0, 0)

    path = os.path.join(vault, mirror_relpath(source_id))
    if os.path.exists(path):
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
    else:
        text = "# %s 作業ログ\n" % source_id

    lines = text.splitlines()
    added = 0
    replaced = 0

    for entry in entries:
        title = sections_module.sanitize_title(entry.title)
        body_lines = entry.body.splitlines()
        index = _index(lines)
        key = (entry.date, title)
        if key in index:
            head_index, end_index = index[key]
            current = "\n".join(lines[head_index + 1:end_index]).strip("\n")
            if current == entry.body:
                continue
            lines[head_index + 1:end_index] = [""] + body_lines + [""]
            replaced += 1
        else:
            while lines and lines[-1].strip() == "":
                lines.pop()
            lines.extend(["", "## %s %s" % (entry.date, title), ""] + body_lines)
            added += 1

    if added == 0 and replaced == 0 and os.path.exists(path):
        return (0, 0)

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines).rstrip("\n") + "\n")
    return (added, replaced)
