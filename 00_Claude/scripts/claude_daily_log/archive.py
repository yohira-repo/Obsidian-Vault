"""Daily ノートの月次アーカイブ（01_Daily/YYYY-MM-DD.md → 01_Daily/YYYYMM/）。

月が替わったら、01_Daily 直下に残っている過去月の Daily ノートを YYYYMM
フォルダへ移す。移動は必ず Obsidian CLI (`obsidian ... move`) 経由で行い、
リンク更新は Obsidian に任せる。os.rename へのフォールバックはしない
（フォールバックすると被リンク側が黙って壊れるため）。
"""
import datetime
import logging
import os
import re
import subprocess
from typing import Callable, Dict, List, Optional, Tuple

DAILY_DIR = "01_Daily"
_DAILY_NAME = re.compile(r"^(\d{4})-(\d{2})-(\d{2})\.md$")


class MoveError(Exception):
    """Obsidian CLI 経由の移動に失敗した。"""


def _month_key(date: str) -> str:
    return date[:4] + date[5:7]


def plan_archive(vault: str, date: str) -> List[Tuple[str, str]]:
    """01_Daily 直下にある「date の月より前」の Daily ノートの (移動元, 移動先) 一覧を返す。

    サブフォルダ配下（＝アーカイブ済み）と、YYYY-MM-DD.md 以外の名前は対象外。
    戻り値は日付昇順。パスは Vault 相対。
    """
    directory = os.path.join(vault, DAILY_DIR)
    if not os.path.isdir(directory):
        return []

    current = _month_key(date)
    plan = []
    for name in sorted(os.listdir(directory)):
        matched = _DAILY_NAME.match(name)
        if matched is None:
            continue
        if not os.path.isfile(os.path.join(directory, name)):
            continue
        month = matched.group(1) + matched.group(2)
        if month >= current:
            continue
        plan.append((
            os.path.join(DAILY_DIR, name),
            os.path.join(DAILY_DIR, month, name),
        ))
    return plan


def _run_obsidian(command: List[str]) -> Tuple[int, str]:
    completed = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return completed.returncode, (completed.stdout or "").strip()


def obsidian_move(
    vault: str,
    src_relpath: str,
    dst_relpath: str,
    runner: Optional[Callable[[List[str]], Tuple[int, str]]] = None,
) -> None:
    """Obsidian CLI に move を依頼する。失敗したら MoveError を送出する。"""
    runner = runner or _run_obsidian
    vault_name = os.path.basename(os.path.normpath(vault))
    command = [
        "obsidian",
        "vault=%s" % vault_name,
        "move",
        "path=%s" % src_relpath.replace(os.sep, "/"),
        "to=%s" % dst_relpath.replace(os.sep, "/"),
    ]
    try:
        code, output = runner(command)
    except FileNotFoundError as error:
        raise MoveError("obsidian コマンドが見つかりません (%s)" % error)
    except OSError as error:
        raise MoveError("obsidian コマンドの起動に失敗しました (%s)" % error)
    if code != 0:
        raise MoveError("obsidian move が失敗しました (exit=%d) %s" % (code, output))


def run_archive(
    vault: str,
    date: str,
    mover: Optional[Callable[[str, str, str], None]] = None,
) -> Dict:
    """過去月の Daily ノートを YYYYMM フォルダへ移す。

    1件ずつ移動し、失敗しても残りの処理は続ける。同期本体を止めないため、
    例外は送出せず warnings に積んで返す。
    """
    mover = mover or obsidian_move
    warnings: List[str] = []

    try:
        datetime.date.fromisoformat(date)
    except ValueError:
        return {"moved": 0, "warnings": ["アーカイブをスキップしました（不正な日付: %s）" % date]}

    moved = 0
    for src_relpath, dst_relpath in plan_archive(vault, date):
        dst = os.path.join(vault, dst_relpath)
        if os.path.exists(dst):
            warnings.append("移動先に同名ファイルがあるためスキップしました: %s" % dst_relpath)
            continue
        try:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
        except OSError as error:
            warnings.append("月次フォルダを作成できませんでした: %s (%s)" % (os.path.dirname(dst_relpath), error))
            continue
        try:
            mover(vault, src_relpath, dst_relpath)
        except MoveError as error:
            warnings.append("アーカイブに失敗しました: %s (%s)" % (src_relpath, error))
            continue
        except Exception as error:  # 想定外でも同期本体は止めない
            logging.exception("アーカイブ中の予期しないエラー: %s", src_relpath)
            warnings.append("アーカイブに失敗しました: %s (%s)" % (src_relpath, error))
            continue
        # Obsidian の CLI が無効な場合、`obsidian` は警告を出しつつ exit 0 を返す。
        # 終了コードを信用せず、実際に移動できたかをファイルシステムで確認する。
        if not os.path.exists(dst) or os.path.exists(os.path.join(vault, src_relpath)):
            warnings.append(
                "アーカイブが反映されませんでした: %s"
                "（Obsidian が起動しているか、設定 > 一般 > 詳細 で CLI が有効か確認してください）"
                % src_relpath
            )
            continue
        logging.info("archive %s -> %s", src_relpath, dst_relpath)
        moved += 1

    return {"moved": moved, "warnings": warnings}
