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

STATUS_SECTION_HEADING = "## プロジェクト状況"
STATUS_START_MARKER = "<!-- project-status:start -->"
STATUS_END_MARKER = "<!-- project-status:end -->"
STATUS_TABLE_HEADER = (
    "| プロジェクト | ブランチ | 未コミット | 最終コミット | 最新の記録 |",
    "|---|---|---|---|---|",
)
NO_RECORD_CELL = "-"
STATUS_GROUP_HEADINGS = ("### alpha", "### coop", "### その他")
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








def render_record_cell(source_id: str, entry) -> str:
    """「最新の記録」列のセル。日付＋その日の記録セクションへのリンク。

    記録が無ければ `-`。タイトルは sanitize_title が `|` を全角に変換するため、
    ここでエスケープが必要なのはエイリアス区切りの `|` だけ。
    """
    if entry is None:
        return NO_RECORD_CELL
    note = source_id.replace("/", "-")
    title = sections_module.sanitize_title(entry.title)
    return "%s [[00_Claude/projects/%s#%s %s\\|%s]]" % (
        entry.date, note, entry.date, title, title,
    )


def _status_row(item, record_cell: str = NO_RECORD_CELL) -> str:
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
        item.dirty, item.when, record_cell,
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


def render_status_lines(statuses: List, now_text: str,
                        latest_entries: Optional[Dict[str, object]] = None) -> List[str]:
    """`### alpha` / `### coop` の表 2 つと時刻行を描画する。

    各グループの先頭に傘プロジェクト（alphasystem / coop）を置き、以降は
    statuses の順序をそのまま使う。該当が 1 件も無いグループは丸ごと省略する。
    alpha / coop のどちらにも属さないプロジェクトは「### その他」の表に出す。
    作業ログ（全プロジェクトを列挙していた）を本表に統合した以上、名前で
    振り分けられないプロジェクトが黙って消えてはいけないため。該当が無ければ
    この表ごと省略されるので、通常の構成では出力は変わらない。

    now_text は末尾の時刻行にだけ使う。表の中身が前回と同じなら呼び出し側
    （_replace_block）がブロックごと据え置くため、時刻も更新されない。
    """
    buckets: Dict[int, List] = {0: [], 1: [], 2: []}
    for item in statuses:
        buckets[_group_index(item.name)].append(item)

    lines: List[str] = []
    for group in (0, 1, 2):
        group_items = _umbrella_first(buckets[group], _GROUP_UMBRELLAS[group])
        if not group_items:
            continue
        if lines:
            lines.append("")
        lines.append(STATUS_GROUP_HEADINGS[group])
        lines.append("")
        lines.extend(STATUS_TABLE_HEADER)
        entries = latest_entries or {}
        lines.extend(
            _status_row(item, render_record_cell(item.name, entries.get(item.name)))
            for item in group_items
        )

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


def _remove_worklog(lines, relpath):
    """旧「Claude作業ログ」の見出しとマーカー区間を削除する。

    作業ログは「プロジェクト状況」表の『最新の記録』列に統合されたため廃止した
    （2026-10-21 のユーザー決定）。過去のデイリーノートも、同期のたびに
    自動で片付くようにする。

    戻り値は (新しい行リスト, 削除したか, 警告 or None)。マーカーが壊れている
    場合は触らずに警告を返す（手書き内容を巻き込まないため）。
    """
    start_indices = _marker_indices(lines, START_MARKER)
    end_indices = _marker_indices(lines, END_MARKER)
    start_count = len(start_indices)
    end_count = len(end_indices)

    if (start_count, end_count) == (0, 0):
        head = [i for i, line in enumerate(lines) if line.strip() == SECTION_HEADING]
        if not head:
            return lines, False, None
        # 見出しだけが残っている場合も片付ける。
        result = [line for i, line in enumerate(lines) if i not in set(head)]
        return result, True, None

    if start_count != 1 or end_count != 1:
        return lines, False, _marker_error_message(relpath, start_count, end_count, order_wrong=False)
    start_idx, end_idx = start_indices[0], end_indices[0]
    if end_idx < start_idx:
        return lines, False, _marker_error_message(relpath, start_count, end_count, order_wrong=True)

    low = start_idx
    # 直前の見出し（と間の空行）も一緒に消す。
    probe = start_idx - 1
    while probe >= 0 and lines[probe].strip() == "":
        probe -= 1
    if probe >= 0 and lines[probe].strip() == SECTION_HEADING:
        low = probe
    result = lines[:low] + lines[end_idx + 1:]
    while result and result[-1].strip() == "":
        result.pop()
    return result, True, None


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
    """「プロジェクト状況」ブロックを再生成し、旧「作業ログ」ブロックを削除する。

    戻り値は (作業ログを削除したか, 状況一覧が変わったか, 警告一覧)。
    `status_lines` が None のときは状況一覧に一切触れない。

    作業ログは状況表の『最新の記録』列へ統合されたため生成しない
    （2026-10-21 のユーザー決定）。`latest_entries` はその列の描画に使う。

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

    # 状況一覧を先に置く。作業ログ見出しを消す前にアンカーとして使うため。
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

    # 廃止した作業ログを片付ける。
    lines, log_removed, warning = _remove_worklog(lines, relpath)
    if warning:
        warnings.append("%s（作業ログの削除を見送りました）" % warning)

    new_text = "\n".join(lines).rstrip("\n") + "\n"
    if original == new_text:
        return False, False, warnings

    os.makedirs(os.path.dirname(path), exist_ok=True)
    atomicio.write_text_atomic(path, new_text)
    return log_removed, status_changed, warnings




