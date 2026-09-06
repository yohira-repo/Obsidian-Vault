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


def _marker_indices(lines: List[str], marker: str) -> List[int]:
    """前後の空白を無視してマーカー行を探す（item K: 末尾空白付きマーカーも認識する）。"""
    return [index for index, line in enumerate(lines) if line.strip() == marker]


def _marker_error_message(relpath: str, start_count: int, end_count: int, order_wrong: bool) -> str:
    """item H: マーカーの個数だけでなく、実際の状態（順序 / 欠落 / 重複）を名指しする。"""
    if order_wrong:
        detail = "開始マーカーより先に終了マーカーが出現しています（順序が逆です）"
    elif start_count > 1 or end_count > 1:
        detail = "マーカーが重複しています"
    elif start_count == 0 and end_count >= 1:
        detail = "開始マーカーがありません（終了マーカーのみ検出）"
    elif end_count == 0 and start_count >= 1:
        detail = "終了マーカーがありません（開始マーカーのみ検出）"
    else:
        detail = "マーカーの状態が不正です"
    return "%s: %s（開始マーカー %d 個 / 終了マーカー %d 個）" % (relpath, detail, start_count, end_count)


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

    # Validate marker state before modifying anything（末尾空白は無視して検出する: item K）
    start_indices = _marker_indices(lines, START_MARKER)
    end_indices = _marker_indices(lines, END_MARKER)
    start_count = len(start_indices)
    end_count = len(end_indices)

    if start_count == 1 and end_count == 1:
        # Exactly one of each: check that START comes before END
        start_idx = start_indices[0]
        end_idx = end_indices[0]
        if end_idx < start_idx:
            # END before START: malformed（item H: 順序が逆であることを明示する）
            raise DailyMarkerError(
                _marker_error_message(daily_relpath(date), start_count, end_count, order_wrong=True)
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
        # Malformed: any other combination（欠落 / 重複。item H: 状態を名指しする）
        raise DailyMarkerError(
            _marker_error_message(daily_relpath(date), start_count, end_count, order_wrong=False)
        )

    new_text = "\n".join(new_lines).rstrip("\n") + "\n"
    if original == new_text:
        return False

    os.makedirs(os.path.dirname(path), exist_ok=True)
    atomicio.write_text_atomic(path, new_text)
    return True
