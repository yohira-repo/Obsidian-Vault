"""Vault 内ミラーノート（00_Claude/projects/*.md）の更新。"""
import os
from typing import Dict, List, Tuple

import atomicio
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


def _insertion_index(lines: List[str], entry_date: str) -> int:
    """entry_date の見出しを挿入すべき行番号を返す（チェックロジカル順序を保つ）。

    entry_date より日付が新しい最初の見出しの行番号を返す。見つからなければ
    末尾（len(lines)）を返す（＝追記）。同日の既存見出しがあっても前進を止めない
    （＝同日の場合は既存の後ろに挿入される）。
    """
    heads = sections_module.scan_headings(lines)
    for index, date, _title in heads:
        if date is not None and date > entry_date:
            return index
    return len(lines)


def update_mirror(vault: str, source_id: str, entries: List) -> Tuple[int, int]:
    """未収録セクションを追記し、本文が変化したセクションは置換する。

    Invariant: an entry's body may contain a line starting with '## ' only
    when it sits inside a fenced code block (```` ``` ```` / ``~~~``) that
    opens and closes within that same body. sections.scan_headings is
    fence-aware, so such a line is never mistaken for a heading — neither
    when the body was first cut out of the source conversations.md, nor
    later when this mirror file is re-scanned by _index() after being
    written back out.
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
            insertion_index = _insertion_index(lines, entry.date)
            if insertion_index >= len(lines):
                while lines and lines[-1].strip() == "":
                    lines.pop()
                lines.extend(["", "## %s %s" % (entry.date, title), ""] + body_lines)
            else:
                block = ["## %s %s" % (entry.date, title), ""] + body_lines + [""]
                if insertion_index > 0 and lines[insertion_index - 1].strip() != "":
                    block = [""] + block
                lines[insertion_index:insertion_index] = block
            added += 1

    if added == 0 and replaced == 0 and os.path.exists(path):
        return (0, 0)

    os.makedirs(os.path.dirname(path), exist_ok=True)
    atomicio.write_text_atomic(path, "\n".join(lines).rstrip("\n") + "\n")
    return (added, replaced)
