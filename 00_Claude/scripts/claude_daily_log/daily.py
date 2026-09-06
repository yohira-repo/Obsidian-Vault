"""Daily ノート（01_Daily/YYYY-MM-DD.md）の管理ブロック更新。"""
import os
from typing import Dict, List, Optional

import atomicio
import sections as sections_module

DAILY_DIR = "01_Daily"
SECTION_HEADING = "## Claude作業ログ"
START_MARKER = "<!-- claude-log:start -->"
END_MARKER = "<!-- claude-log:end -->"
TODAY_HEADING = "### この日の作業"
LATEST_HEADING = "### 各プロジェクトの最新"
NO_TODAY_ENTRIES_LINE = "- （この日の記録はありません）"


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


def render_today_lines(entries: List) -> List[str]:
    """「この日の作業」サブセクションの本文。0件なら固定の1行を返す。"""
    if not entries:
        return [NO_TODAY_ENTRIES_LINE]
    return render_lines(entries)


def render_latest_lines(latest_entries: Dict[str, object], project_names: List[str]) -> List[str]:
    """「各プロジェクトの最新」サブセクションの本文。

    latest_entries は {source_id: Entry}（各ソースの最新1件）。project_names は
    CLAUDE.md 構成テーブル由来の全プロジェクト名（対象外リポジトリ含む）。
    順序: レコードあり（日付降順・同日はソース識別子昇順）が先、
    レコードなし（プロジェクト名昇順）が後。
    """
    items = sorted(latest_entries.items(), key=lambda kv: kv[0])
    items.sort(key=lambda kv: kv[1].date, reverse=True)

    record_lines = []
    for source_id, entry in items:
        note = source_id.replace("/", "-")
        title = sections_module.sanitize_title(entry.title)
        record_lines.append(
            "- **%s** — %s [[00_Claude/projects/%s#%s %s|%s]]"
            % (source_id, entry.date, note, entry.date, title, title)
        )

    covered = {source_id.split("/")[0] for source_id in latest_entries}
    no_record_lines = [
        "- **%s** — 記録なし" % name
        for name in sorted(name for name in project_names if name not in covered)
    ]
    return record_lines + no_record_lines


def update_daily(
    vault: str,
    date: str,
    today_entries: List,
    latest_entries: Optional[Dict[str, object]] = None,
    project_names: Optional[List[str]] = None,
) -> bool:
    """管理ブロックだけを再生成する。書き換えが発生したら True を返す。

    latest_entries が None の場合（過去日の --date 実行など）は「各プロジェクトの
    最新」サブセクションを一切出力しない（過去の Daily に未来の情報を持ち込まないため）。
    latest_entries を渡す場合（対象日＝実際の今日の場合のみ呼び出し側が渡す）は、
    today_entries が空でもファイルを作成する（最新サブセクションには常に意味のある
    内容があるため）。
    """
    path = os.path.join(vault, daily_relpath(date))
    exists = os.path.exists(path)
    if not exists and not today_entries and latest_entries is None:
        return False

    block_body = [TODAY_HEADING] + render_today_lines(today_entries)
    if latest_entries is not None:
        block_body += [""] + [LATEST_HEADING] + render_latest_lines(latest_entries, project_names or [])

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
        block = [START_MARKER] + block_body + [END_MARKER]
        new_lines = lines[:start_idx] + block + lines[end_idx + 1:]
    elif start_count == 0 and end_count == 0:
        # Zero markers: append block at end
        block = [START_MARKER] + block_body + [END_MARKER]
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
