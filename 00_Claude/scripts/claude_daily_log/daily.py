"""Daily ノート（01_Daily/YYYY-MM-DD.md）の管理ブロック更新。"""
import os
from typing import List

import sections as sections_module

DAILY_DIR = "01_Daily"
SECTION_HEADING = "## Claude作業ログ"
START_MARKER = "<!-- claude-log:start -->"
END_MARKER = "<!-- claude-log:end -->"


def daily_relpath(date: str) -> str:
    return os.path.join(DAILY_DIR, date + ".md")


def render_lines(entries: List) -> List[str]:
    rendered = []
    for entry in entries:
        note = entry.source_id.replace("/", "-")
        title = sections_module.sanitize_title(entry.title)
        rendered.append(
            "- **%s** — [[00_Claude/projects/%s#%s %s|%s]]"
            % (entry.source_id, note, entry.date, title, title)
        )
    return rendered


def update_daily(vault: str, date: str, entries: List) -> bool:
    """管理ブロックだけを再生成する。書き換えが発生したら True を返す。"""
    path = os.path.join(vault, daily_relpath(date))
    exists = os.path.exists(path)
    if not exists and not entries:
        return False

    if exists:
        with open(path, encoding="utf-8") as handle:
            original = handle.read()
        lines = original.splitlines()
    else:
        original = None
        lines = []

    block = [START_MARKER] + render_lines(entries) + [END_MARKER]
    if START_MARKER in lines and END_MARKER in lines:
        start = lines.index(START_MARKER)
        end = lines.index(END_MARKER, start)
        new_lines = lines[:start] + block + lines[end + 1:]
    else:
        while lines and lines[-1].strip() == "":
            lines.pop()
        prefix = lines + [""] if lines else []
        new_lines = prefix + [SECTION_HEADING, ""] + block

    new_text = "\n".join(new_lines).rstrip("\n") + "\n"
    if original == new_text:
        return False

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(new_text)
    return True
