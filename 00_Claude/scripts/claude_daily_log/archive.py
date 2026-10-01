"""前月の Daily ノートを 01_Daily/YYYYMM/ へアーカイブ移動する。

月替わり時、前月の `01_Daily/YYYY-MM-DD.md` を `01_Daily/YYYYMM/` 配下へ
移動する。当月および前月以外の月（＝あえて残している可能性のある古いノート）
には一切触れない。冪等で、対象が無ければ何もしない。

リンクはファイル名ベース（`[[2026-09-30]]`）で解決されるため、サブフォルダへ
移動しても Obsidian 側のリンクは壊れない（フルパス参照は Vault 内に無いことを
確認済み）。Windows / macOS の双方で動くよう、パス操作は os.path に統一する。
"""
import datetime
import logging
import os
import re
import shutil
from typing import Dict, Optional, Tuple

DAILY_DIR = "01_Daily"
# 01_Daily 直下の日次ノートだけを対象にする（YYYY-MM-DD.md 厳密一致）。
_DAILY_FILE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})\.md$")


def _previous_month(today: datetime.date) -> Tuple[int, int]:
    """today の 1 つ前の月を (year, month) で返す。"""
    year, month = today.year, today.month - 1
    if month == 0:
        year, month = year - 1, 12
    return year, month


def archive_previous_month(
    vault: str,
    today: Optional[datetime.date] = None,
    dry_run: bool = False,
) -> Dict:
    """前月の日次ノートを `01_Daily/YYYYMM/` へ移動する。

    - 対象は「前月の `YYYY-MM-DD.md`」のみ。当月・それ以外の月は触らない。
    - 冪等。対象が無ければ何もしない。
    - 移動先に同名ファイルが既にあれば、上書きせずスキップして警告する。
    """
    report = {"moved": [], "skipped": [], "target": None, "warnings": []}
    if today is None:
        today = datetime.date.today()

    year, month = _previous_month(today)
    prefix = "%04d-%02d-" % (year, month)
    folder_name = "%04d%02d" % (year, month)
    report["target"] = folder_name

    daily_dir = os.path.join(vault, DAILY_DIR)
    if not os.path.isdir(daily_dir):
        report["warnings"].append("Daily フォルダが見つかりません: %s" % daily_dir)
        return report

    try:
        names = sorted(os.listdir(daily_dir))
    except OSError as error:
        report["warnings"].append("Daily フォルダを読めません (%s)" % error)
        return report

    targets = [
        name
        for name in names
        if _DAILY_FILE_RE.match(name)
        and name.startswith(prefix)
        and os.path.isfile(os.path.join(daily_dir, name))
    ]
    if not targets:
        return report

    dest_dir = os.path.join(daily_dir, folder_name)
    if not dry_run:
        try:
            os.makedirs(dest_dir, exist_ok=True)
        except OSError as error:
            report["warnings"].append(
                "アーカイブ先フォルダを作成できません: %s (%s)" % (dest_dir, error)
            )
            return report

    for name in targets:
        src = os.path.join(daily_dir, name)
        dest = os.path.join(dest_dir, name)
        if os.path.exists(dest):
            report["skipped"].append(name)
            report["warnings"].append(
                "移動先に同名ファイルが既にあります。スキップ: %s/%s" % (folder_name, name)
            )
            continue
        if dry_run:
            report["moved"].append(name)
            continue
        try:
            shutil.move(src, dest)
            report["moved"].append(name)
        except OSError as error:
            report["warnings"].append("移動に失敗しました: %s (%s)" % (name, error))

    logging.info(
        "archive target=%s moved=%d skipped=%d warnings=%d dry_run=%s",
        folder_name,
        len(report["moved"]),
        len(report["skipped"]),
        len(report["warnings"]),
        dry_run,
    )
    return report
