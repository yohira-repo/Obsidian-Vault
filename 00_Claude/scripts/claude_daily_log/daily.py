"""Daily ノート（01_Daily/YYYY-MM-DD.md）の管理ブロック更新。"""
import os
from typing import Dict, List, Optional, Tuple

import atomicio
import sections as sections_module
import status as status_module

DAILY_DIR = "01_Daily"
SECTION_HEADING = "## Claude作業ログ"
START_MARKER = "<!-- claude-log:start -->"
END_MARKER = "<!-- claude-log:end -->"
NO_ENTRIES_LINE = "- （記録がありません）"

STATUS_SECTION_HEADING = "## プロジェクト状況"
STATUS_START_MARKER = "<!-- project-status:start -->"
STATUS_END_MARKER = "<!-- project-status:end -->"
STATUS_TABLE_HEADER = (
    "| プロジェクト | ブランチ | 未コミット | 最終コミット | メッセージ |",
    "|---|---|---|---|---|",
)
STATUS_GROUP_HEADINGS = ("### alpha", "### coop")
# 時刻行の先頭。中身が同じときに時刻だけで書き換えないための同値判定に使う。
STATUS_TIME_PREFIX = "（"  # 時刻行は "（YYYY-MM-DD HH:MM 時点）"。表の行は "|"、小見出しは "#" で始まるため衝突しない

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


def _status_row(item) -> str:
    """1 プロジェクト分の表の行。同居はリンクを付けない。

    セル内の `|` は必ず `\\|` にエスケープする。特に**ウィキリンクのエイリアス
    区切り**（`[[path|alias]]` の `|`）は見落としやすく、エスケープしないと
    Obsidian が列区切りとして解釈して 1 行が 6 列に割れ、データが右へずれる。
    message 列は status 側で既にエスケープ済みだが、name / branch はここで行う。
    """
    name = status_module.escape_cell(item.name)
    label = (
        "[[00_Claude/projects/%s\\|%s]]" % (item.name, name)
        if item.linked else name
    )
    return "| %s | %s | %s | %s | %s |" % (
        label, status_module.escape_cell(item.branch),
        item.dirty, item.when, item.message,
    )


def _umbrella_first(group_items: List, umbrella: Optional[str]) -> List:
    """傘プロジェクトだけを先頭へ移す。それ以外の順序は入力のまま保つ。

    並び順の要件は「各グループの先頭が傘（alphasystem / coop）であること」だけで、
    以降の順序は問わない（2026-10-21 のユーザー判断）。
    """
    if umbrella is None:
        return list(group_items)
    head = [item for item in group_items if item.name == umbrella]
    rest = [item for item in group_items if item.name != umbrella]
    return head + rest


def render_status_lines(statuses: List, now_text: str) -> List[str]:
    """`### alpha` / `### coop` の表 2 つと時刻行を描画する。

    各グループの先頭に傘プロジェクト（alphasystem / coop）を置き、以降は
    statuses の順序をそのまま使う。該当が 1 件も無いグループは丸ごと省略する。
    「その他」グループは状況一覧には出さない（仕様 3 章の表は alpha 系・coop 系の 2 つだけ）。

    now_text は末尾の時刻行にだけ使う。表の中身が前回と同じなら呼び出し側
    （_replace_block）がブロックごと据え置くため、時刻も更新されない。
    """
    buckets: Dict[int, List] = {0: [], 1: []}
    for item in statuses:
        index = _group_index(item.name)
        if index in buckets:
            buckets[index].append(item)

    lines: List[str] = []
    for group in (0, 1):
        group_items = _umbrella_first(buckets[group], _GROUP_UMBRELLAS[group])
        if not group_items:
            continue
        if lines:
            lines.append("")
        lines.append(STATUS_GROUP_HEADINGS[group])
        lines.append("")
        lines.extend(STATUS_TABLE_HEADER)
        lines.extend(_status_row(item) for item in group_items)

    if lines:
        lines.append("")
    lines.append("（%s 時点）" % now_text)
    return lines


def _same_ignoring_volatile(current, block, volatile_prefix):
    """時刻行のような毎回変わる行を除いて 2 つのブロックを比較する。

    volatile_prefix が None なら単純一致。指定時は、その文字列で始まる行を
    両者から取り除いてから比較する。表の中身が同じなら時刻だけのために
    ノートを書き換えないための判定（2026-10-21 のユーザー決定）。
    """
    if volatile_prefix is None:
        return current == block
    def strip(seq):
        return [line for line in seq if not line.startswith(volatile_prefix)]
    return strip(current) == strip(block)


def _replace_block(lines, start_marker, end_marker, body, heading, anchor_heading, label,
                   volatile_prefix=None):
    """マーカー区間を body で置き換える。無ければ挿入する。

    戻り値は (新しい行リスト, 変化したか, 警告 or None)。マーカーが壊れている
    場合は何も変更せず警告を返す（他方のブロックの更新は止めない）。
    volatile_prefix を渡すと、その行を無視して同値判定する（時刻行用）。
    """
    start_indices = _marker_indices(lines, start_marker)
    end_indices = _marker_indices(lines, end_marker)
    start_count = len(start_indices)
    end_count = len(end_indices)

    block = [start_marker] + body + [end_marker]

    if start_count == 1 and end_count == 1:
        start_idx = start_indices[0]
        end_idx = end_indices[0]
        if end_idx < start_idx:
            return lines, False, _marker_error_message(label, start_count, end_count, order_wrong=True)
        current = lines[start_idx:end_idx + 1]
        if _same_ignoring_volatile(current, block, volatile_prefix):
            # 中身が同じなら時刻行も据え置く（毎分の書き換えと git 差分を避ける）。
            return lines, False, None
        return lines[:start_idx] + block + lines[end_idx + 1:], True, None

    if start_count == 0 and end_count == 0:
        if anchor_heading is not None:
            for index, line in enumerate(lines):
                if line.strip() == anchor_heading:
                    inserted = [heading, ""] + block + [""]
                    return lines[:index] + inserted + lines[index:], True, None
        trimmed = list(lines)
        while trimmed and trimmed[-1].strip() == "":
            trimmed.pop()
        prefix = trimmed + [""] if trimmed else []
        return prefix + [heading, ""] + block, True, None

    return lines, False, _marker_error_message(label, start_count, end_count, order_wrong=False)


def update_daily(
    vault: str,
    date: str,
    latest_entries: Dict[str, object],
    project_names: Optional[List[str]] = None,
    status_lines: Optional[List[str]] = None,
) -> Tuple[bool, bool, List[str]]:
    """管理ブロック（作業ログ / プロジェクト状況）を再生成する。

    戻り値は (作業ログが変わったか, 状況一覧が変わったか, 警告一覧)。
    `status_lines` が None のときは状況一覧に一切触れない。

    Daily ノートが存在しない場合は**何も作らない**（利用者が毎朝テンプレートから
    作成する運用を壊さないため）。呼び出し側は事前に存在を確認して報告すること。
    """
    warnings: List[str] = []
    path = os.path.join(vault, daily_relpath(date))
    if not os.path.exists(path):
        return False, False, warnings

    with open(path, encoding="utf-8") as handle:
        original = handle.read()
    lines = original.splitlines()
    relpath = daily_relpath(date)

    # 作業ログ: マーカー破損は従来どおり例外にする（呼び出し側が警告へ変換する）。
    start_indices = _marker_indices(lines, START_MARKER)
    end_indices = _marker_indices(lines, END_MARKER)
    start_count = len(start_indices)
    end_count = len(end_indices)
    if start_count == 1 and end_count == 1 and end_indices[0] < start_indices[0]:
        raise DailyMarkerError(_marker_error_message(relpath, start_count, end_count, order_wrong=True))
    if (start_count, end_count) not in ((1, 1), (0, 0)):
        raise DailyMarkerError(_marker_error_message(relpath, start_count, end_count, order_wrong=False))

    block_body = render_project_lines(latest_entries, project_names or [])
    lines, log_changed, _ = _replace_block(
        lines, START_MARKER, END_MARKER, block_body,
        SECTION_HEADING, None, relpath,
    )

    status_changed = False
    if status_lines is not None:
        lines, status_changed, warning = _replace_block(
            lines, STATUS_START_MARKER, STATUS_END_MARKER, status_lines,
            STATUS_SECTION_HEADING, SECTION_HEADING,
            "%s のプロジェクト状況ブロック" % relpath,
            volatile_prefix=STATUS_TIME_PREFIX,
        )
        if warning:
            warnings.append(warning)

    new_text = "\n".join(lines).rstrip("\n") + "\n"
    if original == new_text:
        return False, False, warnings

    os.makedirs(os.path.dirname(path), exist_ok=True)
    atomicio.write_text_atomic(path, new_text)
    return log_changed, status_changed, warnings


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
    start_count = len(start_indices)
    end_count = len(end_indices)
    # order_wrong は「開始・終了ともにちょうど1個」のときだけ判定する。
    # update_daily と同じ条件にしないと、マーカー重複時に
    # 「順序が逆」と「重複している」で異なるメッセージが出る。
    if start_count != 1 or end_count != 1:
        raise DailyMarkerError(
            _marker_error_message(daily_relpath(date), start_count, end_count, order_wrong=False)
        )
    if end_indices[0] < start_indices[0]:
        raise DailyMarkerError(
            _marker_error_message(daily_relpath(date), start_count, end_count, order_wrong=True)
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
