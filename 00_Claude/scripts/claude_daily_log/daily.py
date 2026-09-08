"""Daily ノート（01_Daily/YYYY-MM-DD.md）の管理ブロック更新。"""
import os
from typing import Dict, List, Optional, Tuple

import atomicio
import sections as sections_module

DAILY_DIR = "01_Daily"
SECTION_HEADING = "## Claude作業ログ"
START_MARKER = "<!-- claude-log:start -->"
END_MARKER = "<!-- claude-log:end -->"
NO_ENTRIES_LINE = "- （記録がありません）"

# システム単位のグループ化: alpha* → coop* → その他、の順に並べ、グループ間は
# 空行1行で区切る。各グループの傘プロジェクト（umbrella）は、そのグループの
# 先頭に固定表示する（記録が無くても「記録なし」として表示する）。
ALPHA_UMBRELLA = "alphasystem"
COOP_UMBRELLA = "coop"
_GROUP_UMBRELLAS = (ALPHA_UMBRELLA, COOP_UMBRELLA, None)  # index: 0=alpha, 1=coop, 2=その他


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


def _group_index(name: str) -> int:
    """id/プロジェクト名の先頭要素から所属グループを判定する（0=alpha, 1=coop, 2=その他）。"""
    top = name.split("/")[0]
    if top.startswith("alpha"):
        return 0
    if top.startswith("coop"):
        return 1
    return 2


def _order_group_items(group_items: List[Dict], umbrella: Optional[str]) -> List[Dict]:
    """1グループ内の並び順を決める。

    1) 傘プロジェクト（name == umbrella）を常に先頭に置く（記録なしでも）。
    2) 傘プロジェクトのサブソース（name が "umbrella/" で始まる、記録ありのみ発生）を id 昇順で。
    3) 残りの記録ありエントリを日付降順、同日は id 昇順で。
    4) 記録なしエントリを名前昇順で。
    """
    tier0 = []
    tier1 = []
    tier2 = []
    tier3 = []
    for item in group_items:
        name = item["name"]
        has_record = item["has_record"]
        if umbrella is not None and name == umbrella:
            tier0.append(item)
        elif has_record and umbrella is not None and name.startswith(umbrella + "/"):
            tier1.append(item)
        elif has_record:
            tier2.append(item)
        else:
            tier3.append(item)
    tier1.sort(key=lambda item: item["name"])
    tier2.sort(key=lambda item: item["name"])
    tier2.sort(key=lambda item: item["date"], reverse=True)
    tier3.sort(key=lambda item: item["name"])
    return tier0 + tier1 + tier2 + tier3


def _grouped_lines(items: List[Dict]) -> List[str]:
    """items（各 {"name", "has_record", "date", "line"}）をグループ化して描画する。

    グループは alpha → coop → その他 の順。1件も無いグループは丸ごと省略し、
    グループ間には空行を1行だけ挟む（先頭・末尾には残さない）。
    """
    buckets: Dict[int, List[Dict]] = {0: [], 1: [], 2: []}
    for item in items:
        buckets[_group_index(item["name"])].append(item)

    groups_out = []
    for group in (0, 1, 2):
        group_items = buckets[group]
        if not group_items:
            continue
        ordered = _order_group_items(group_items, _GROUP_UMBRELLAS[group])
        groups_out.append([item["line"] for item in ordered])

    result: List[str] = []
    for index, group_lines in enumerate(groups_out):
        if index > 0:
            result.append("")
        result.extend(group_lines)
    return result


def render_project_lines(latest_entries: Dict[str, object], project_names: List[str]) -> List[str]:
    """管理ブロックの本文（プロジェクトごとに1行）。

    latest_entries は {source_id: Entry}（各ソースの最新1件）。project_names は
    CLAUDE.md 構成テーブル由来の全プロジェクト名（対象外リポジトリ含む）。

    システム単位（alpha* / coop* / その他）でグループ化し、グループ間には
    空行を1行挟む（1件も無いグループは丸ごと省略）。各グループ内の順序:
    1) 傘プロジェクト（alphasystem / coop）が常に先頭（記録が無くても「記録なし」で）。
    2) 傘プロジェクトのサブソース（id 昇順）。
    3) 残りの記録あり（日付降順・同日は id 昇順）。
    4) 記録なし（プロジェクト名昇順）。
    """
    items = []
    for source_id, entry in latest_entries.items():
        note = source_id.replace("/", "-")
        title = sections_module.sanitize_title(entry.title)
        line = (
            "- **%s** — %s [[00_Claude/projects/%s#%s %s|%s]]"
            % (source_id, entry.date, note, entry.date, title, title)
        )
        items.append({"name": source_id, "has_record": True, "date": entry.date, "line": line})

    covered = {source_id.split("/")[0] for source_id in latest_entries}
    for name in project_names:
        if name in covered:
            continue
        items.append({"name": name, "has_record": False, "date": "", "line": "- **%s** — 記録なし" % name})

    lines = _grouped_lines(items)
    return lines if lines else [NO_ENTRIES_LINE]


def update_daily(
    vault: str,
    date: str,
    latest_entries: Dict[str, object],
    project_names: Optional[List[str]] = None,
) -> bool:
    """管理ブロックだけを再生成する。書き換えが発生したら True を返す。

    管理ブロックの中身はプロジェクトごとの1行リストだけ（`latest_entries` は
    {source_id: Entry}＝対象日以前で最新の1件）。日付は各行に入るため、朝に開けば
    前日以前の最新が並び、その日のセッションで記録ができればその行が当日日付に変わる。

    Daily ノートが存在しない場合は**何も作らない**（利用者が毎朝テンプレートから
    作成する運用を壊さないため）。呼び出し側は事前に存在を確認して報告すること。
    """
    path = os.path.join(vault, daily_relpath(date))
    if not os.path.exists(path):
        return False

    block_body = render_project_lines(latest_entries, project_names or [])

    with open(path, encoding="utf-8") as handle:
        original = handle.read()
    lines = original.splitlines()

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
        # Zero markers: append block at end（ファイルは必ず存在する）
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


def render_entry_line(source_id: str, entry) -> str:
    """Daily ブロックの1行を描画する。render_project_lines と同じ書式にすること。"""
    note = source_id.replace("/", "-")
    title = sections_module.sanitize_title(entry.title)
    return (
        "- **%s** — %s [[00_Claude/projects/%s#%s %s|%s]]"
        % (source_id, entry.date, note, entry.date, title, title)
    )


def update_daily_sources(
    vault: str,
    date: str,
    latest_entries: Dict[str, object],
) -> Tuple[bool, List[str]]:
    """指定ソースの行だけを差し替える。他の行には一切触れない。

    プロジェクト単位の同期用。ブロック全体を作り直すと、走査しなかった
    プロジェクトが「記録なし」に化けるため、行単位の置換にしている。

    該当行が無いソースは警告を返し、その行は作らない（挿入位置を決めるには
    グループ化と並び替えが必要になり、複雑さのわりに使う場面が限られるため）。
    戻り値は (書き換えが発生したか, 警告一覧)。
    """
    warnings: List[str] = []
    path = os.path.join(vault, daily_relpath(date))
    if not os.path.exists(path):
        return False, ["%s が存在しません" % daily_relpath(date)]

    with open(path, encoding="utf-8") as handle:
        original = handle.read()
    lines = original.splitlines()

    start_indices = _marker_indices(lines, START_MARKER)
    end_indices = _marker_indices(lines, END_MARKER)
    if len(start_indices) != 1 or len(end_indices) != 1 or end_indices[0] < start_indices[0]:
        raise DailyMarkerError(
            _marker_error_message(
                daily_relpath(date),
                len(start_indices),
                len(end_indices),
                order_wrong=bool(start_indices and end_indices and end_indices[0] < start_indices[0]),
            )
        )

    low = start_indices[0] + 1
    high = end_indices[0]

    for source_id in sorted(latest_entries):
        entry = latest_entries[source_id]
        prefix = "- **%s** — " % source_id
        target = None
        for index in range(low, high):
            if lines[index].startswith(prefix):
                target = index
                break
        if target is None:
            warnings.append(
                "%s: Daily に該当行がありません。先に一括の同期（/daily-sync）を実行してください"
                % source_id
            )
            continue
        lines[target] = render_entry_line(source_id, entry)

    new_text = "\n".join(lines).rstrip("\n") + "\n"
    if original == new_text:
        return False, warnings

    atomicio.write_text_atomic(path, new_text)
    return True, warnings
