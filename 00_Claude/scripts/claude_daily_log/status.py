"""各リポジトリの現在状況（ブランチ / 未コミット / 最終コミット）を収集する。

【整合ルール】判定条件と表記（列の並び、⚠upstream消失 / (未push) の判定、
未コミットの「N件」、相対時刻の日本語化、件名の40文字切り詰め、| のエスケープ）は
alphasystem の .claude/hooks/project-status.sh（セッション内表示用の bash 版）と
同一に保つ。**正本はこの Python 版**。どちらかを変えるときは必ずもう一方にも
同じ変更を入れること。
経緯: alphasystem docs/design/2026-10-21-Obsidianデイリーノート-プロジェクト状況一覧-仕様.md 6章
"""
import os
import re
import subprocess
from dataclasses import dataclass
from typing import List, Optional

MSG_MAX = 40
GIT_TIMEOUT = 20

NOT_CLONED = "未clone"
NOT_A_REPO = "（git管理外）"
NESTED_LABEL = "alphasystem内"
FAILED_LABEL = "（取得失敗）"
DASH = "-"

# bash 版の sed と同じ順序・同じ置換。順序を変えると複合表記が崩れる。
_RELATIVE_RULES = (
    (re.compile(r" seconds? ago"), "秒前"),
    (re.compile(r" minutes? ago"), "分前"),
    (re.compile(r" hours? ago"), "時間前"),
    (re.compile(r" days? ago"), "日前"),
    (re.compile(r" weeks? ago"), "週間前"),
    (re.compile(r" months? ago"), "か月前"),
    (re.compile(r" years? ago"), "年前"),
    (re.compile(r" years?,"), "年"),
    (re.compile(r" months?$"), "か月"),
    (re.compile(r", "), "・"),
    (re.compile(r"年 "), "年"),
)


@dataclass(frozen=True)
class ProjectStatus:
    name: str
    branch: str
    dirty: str
    when: str
    message: str
    linked: bool
    failed: bool


def japanize_relative(text: str) -> str:
    """git の `%cr`（英語）を日本語表記にする。未知の表記はそのまま返す。"""
    result = text
    for pattern, replacement in _RELATIVE_RULES:
        result = pattern.sub(replacement, result)
    return result


def truncate_subject(text: str, limit: int = MSG_MAX) -> str:
    """件名を limit 文字で切り詰め、超過時は末尾に `…` を付ける。"""
    if len(text) > limit:
        return text[:limit] + "…"
    return text


def escape_cell(text: str) -> str:
    """表のセルに入れるため `|` をエスケープする。"""
    return text.replace("|", r"\|")


def _git(path: str, *args: str) -> Optional[str]:
    """git を実行して標準出力を返す。失敗・異常終了は None。"""
    try:
        proc = subprocess.run(
            ["git", "-C", path] + list(args),
            capture_output=True, timeout=GIT_TIMEOUT,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.decode("utf-8", "replace").strip()


def _plain(name: str, branch: str, linked: bool = True, failed: bool = False) -> ProjectStatus:
    """ブランチ列だけに状態を出し、残りを `-` で埋めた行。"""
    return ProjectStatus(
        name=name, branch=branch, dirty=DASH, when=DASH, message=DASH,
        linked=linked, failed=failed,
    )


def _branch_label(path: str) -> str:
    """ブランチ名に `⚠upstream消失` / `(未push)` のフラグを付けた表示。"""
    branch = _git(path, "branch", "--show-current")
    if branch is None:
        return FAILED_LABEL
    if not branch:
        short = _git(path, "rev-parse", "--short", "HEAD") or "?"
        return "(detached %s)" % short

    remote = _git(path, "config", "branch.%s.remote" % branch) or ""
    merge = _git(path, "config", "branch.%s.merge" % branch) or ""
    if remote and merge:
        ref = "refs/remotes/%s/%s" % (remote, merge[len("refs/heads/"):] if merge.startswith("refs/heads/") else merge)
        if _git(path, "show-ref", "--verify", "--quiet", ref) is None:
            return branch + " ⚠upstream消失"
    elif branch not in ("main", "staging"):
        return branch + " (未push)"
    return branch


def collect_status(project) -> ProjectStatus:
    """1 プロジェクト分の状況。例外は投げず、必ず ProjectStatus を返す。"""
    name = project.name
    path = project.path

    if project.is_nested:
        # 同居ディレクトリ: 独立リポジトリではないのでリンクも git 情報も出さない。
        return _plain(name, NESTED_LABEL, linked=False)

    if not os.path.isdir(path):
        return _plain(name, NOT_CLONED)

    if _git(path, "rev-parse", "--is-inside-work-tree") is None:
        return _plain(name, NOT_A_REPO)

    try:
        branch = _branch_label(path)
        if branch == FAILED_LABEL:
            return _plain(name, FAILED_LABEL, failed=True)

        porcelain = _git(path, "status", "--porcelain")
        if porcelain is None:
            dirty = DASH
        else:
            count = len([line for line in porcelain.splitlines() if line.strip()])
            dirty = "%d件" % count if count else DASH

        raw_when = _git(path, "log", "-1", "--format=%cr")
        when = japanize_relative(raw_when) if raw_when else DASH

        raw_message = _git(path, "log", "-1", "--format=%s")
        message = escape_cell(truncate_subject(raw_message)) if raw_message else DASH
    except Exception:
        # 1 リポジトリの失敗で表全体を止めない。
        return _plain(name, FAILED_LABEL, failed=True)

    return ProjectStatus(
        name=name, branch=branch, dirty=dirty, when=when, message=message,
        linked=True, failed=False,
    )


def collect_all(projects: List) -> List[ProjectStatus]:
    """与えられた順序を保ったまま全プロジェクトの状況を集める。"""
    return [collect_status(project) for project in projects]
