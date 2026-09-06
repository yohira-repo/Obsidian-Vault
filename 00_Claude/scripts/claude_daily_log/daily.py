"""Daily ノート（01_Daily/YYYY-MM-DD.md）の管理ブロック更新。"""
import os
from typing import List

import atomicio
import sections as sections_module

DAILY_DIR = "01_Daily"
SECTION_HEADING = "## Claude作業ログ"
START_MARKER = "<!-- claude-log:start -->"
END_MARKER = "<!-- claude-log:end -->"


class DailyMarkerError(RuntimeError):
    """Daily note has malformed markers."""
    pass


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

    # Validate marker state before modifying anything
    start_count = lines.count(START_MARKER)
    end_count = lines.count(END_MARKER)

    if start_count == 1 and end_count == 1:
        # Exactly one of each: check that START comes before END
        start_idx = lines.index(START_MARKER)
        end_idx = lines.index(END_MARKER)
        if end_idx < start_idx:
            # END before START: malformed
            relpath = daily_relpath(date)
            raise DailyMarkerError(
                "%s: 開始マーカー %d 個 / 終了マーカー %d 個" % (relpath, start_count, end_count)
            )
        # Valid: replace block between markers
        block = [START_MARKER] + render_lines(entries) + [END_MARKER]
        new_lines = lines[:start_idx] + block + lines[end_idx + 1:]
    elif start_count == 0 and end_count == 0:
        # Zero markers: append block at end
        block = [START_MARKER] + render_lines(entries) + [END_MARKER]
        while lines and lines[-1].strip() == "":
            lines.pop()
        prefix = lines + [""] if lines else []
        new_lines = prefix + [SECTION_HEADING, ""] + block
    else:
        # Malformed: any other combination
        relpath = daily_relpath(date)
        raise DailyMarkerError(
            "%s: 開始マーカー %d 個 / 終了マーカー %d 個" % (relpath, start_count, end_count)
        )

    new_text = "\n".join(new_lines).rstrip("\n") + "\n"
    if original == new_text:
        return False

    os.makedirs(os.path.dirname(path), exist_ok=True)
    atomicio.write_text_atomic(path, new_text)
    return True
