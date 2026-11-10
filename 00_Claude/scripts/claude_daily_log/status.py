"""各リポジトリの現在状況（ブランチ / 未コミット / 最終コミット）を収集する。

【整合ルール】判定条件と表記（列の並び、⚠upstream消失 / (未push) の判定、
未コミットの「N件」、相対時刻の日本語化、件名の40文字切り詰め、| のエスケープ）は
alphasystem の .claude/hooks/project-status.sh（セッション内表示用の bash 版）と
同一に保つ。**正本はこの Python 版**。どちらかを変えるときは必ずもう一方にも
同じ変更を入れること。
経緯: alphasystem docs/design/2026-10-21-Obsidianデイリーノート-プロジェクト状況一覧-仕様.md 6章
"""
import concurrent.futures
import json
import os
import re
import subprocess
from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

MSG_MAX = 40
GIT_TIMEOUT = 20
GH_TIMEOUT = 30
MAX_WORKERS = 8

NOT_CLONED = "未clone"
NOT_A_REPO = "（git管理外）"
NESTED_LABEL = "alphasystem内"
FAILED_LABEL = "（取得失敗）"
NO_PR_BRANCH = "PRなし"
DASH = "-"

# gh pr list に渡すリポジトリ名の接頭辞（clone URL と同じ組織）。
GH_REPO_TEMPLATE = "alphacmc/%s"

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
class PrRow:
    """open PR 1 件分の表示用データ。"""
    number: int
    head: str
    base: str
    is_draft: bool
    when: str      # origin/<head> の最終コミット相対時刻（日本語化済み）。取れなければ DASH
    message: str   # origin/<head> の最終コミット件名（40字切詰・| エスケープ済み）


@dataclass(frozen=True)
class ProjectStatus:
    name: str
    branch: str
    dirty: str
    when: str
    message: str
    linked: bool
    failed: bool
    # open PR がある場合のみ非空。空のときは branch/when/message の 1 行で描画する
    # （＝PRなし・未clone・gh 不可時のローカルフォールバックを包含）。
    prs: Tuple[PrRow, ...] = ()


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


def list_open_prs(name: str) -> Optional[List[dict]]:
    """GitHub の open PR 一覧を返す。gh 不可（未認証/オフライン/未導入/失敗）は None。

    None は「GitHub 基準で判定できない」を意味し、呼び出し側はローカル表示へ
    フォールバックする。空リスト `[]` は「open PR が無い」ことを意味する。
    """
    try:
        proc = subprocess.run(
            ["gh", "pr", "list", "--repo", GH_REPO_TEMPLATE % name, "--state", "open",
             "--json", "number,headRefName,baseRefName,isDraft"],
            capture_output=True, timeout=GH_TIMEOUT,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    try:
        data = json.loads(proc.stdout.decode("utf-8", "replace") or "[]")
    except ValueError:
        return None
    return data if isinstance(data, list) else None


def _dirty_count(path: str) -> str:
    porcelain = _git(path, "status", "--porcelain")
    if porcelain is None:
        return DASH
    count = len([line for line in porcelain.splitlines() if line.strip()])
    return "%d件" % count if count else DASH


def _ref_latest(path: str, ref: str) -> Tuple[str, str]:
    """ref の最終コミット (相対時刻, 件名) を返す。取れなければ (DASH, DASH)。"""
    raw_when = _git(path, "log", "-1", "--format=%cr", ref)
    when = japanize_relative(raw_when) if raw_when else DASH
    raw_message = _git(path, "log", "-1", "--format=%s", ref)
    message = escape_cell(truncate_subject(raw_message)) if raw_message else DASH
    return when, message


def _canonical_origin_ref(path: str) -> Optional[str]:
    """origin/staging があればそれ、無ければ origin/main。どちらも無ければ None。"""
    for branch in ("staging", "main"):
        ref = "refs/remotes/origin/%s" % branch
        if _git(path, "show-ref", "--verify", "--quiet", ref) is not None:
            return "origin/%s" % branch
    return None


def _local_status(name: str, path: str) -> ProjectStatus:
    """従来のローカル基準 1 行（gh 不可時のフォールバック）。"""
    branch = _branch_label(path)
    if branch == FAILED_LABEL:
        return _plain(name, FAILED_LABEL, failed=True)
    when, message = _ref_latest(path, "HEAD")
    return ProjectStatus(
        name=name, branch=branch, dirty=_dirty_count(path),
        when=when, message=message, linked=True, failed=False,
    )


def collect_status(
    project,
    pr_lister: Optional[Callable[[str], Optional[List[dict]]]] = None,
) -> ProjectStatus:
    """1 プロジェクト分の状況。例外は投げず、必ず ProjectStatus を返す。

    GitHub の open PR を基準に表示する:
    - open PR あり → PR ごとに行（`prs` に格納）。最終コミットは origin/<PRブランチ>。
    - open PR なし → `PRなし` 1 行。最終コミットは origin/staging（無ければ main）。
    - gh 不可（pr_lister が None を返す）→ 従来のローカル基準 1 行へフォールバック。

    `pr_lister` 省略時はモジュール関数 `list_open_prs` を**呼び出し時に**参照する
    （テストが `patch.object(status, "list_open_prs", ...)` で差し替えられるように）。
    """
    if pr_lister is None:
        pr_lister = list_open_prs
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
        prs_raw = pr_lister(name)
        if prs_raw is None:
            # GitHub 基準で判定できない → ローカル表示へフォールバック。
            return _local_status(name, path)

        dirty = _dirty_count(path)

        if not prs_raw:
            # open PR なし → 正系ブランチ（staging/main）の最新を出す。
            ref = _canonical_origin_ref(path)
            when, message = _ref_latest(path, ref) if ref else (DASH, DASH)
            return ProjectStatus(
                name=name, branch=NO_PR_BRANCH, dirty=dirty,
                when=when, message=message, linked=True, failed=False,
            )

        prs = []
        for pr in prs_raw:
            head = str(pr.get("headRefName", ""))
            when, message = _ref_latest(path, "origin/%s" % head) if head else (DASH, DASH)
            prs.append(PrRow(
                number=int(pr.get("number", 0)),
                head=head,
                base=str(pr.get("baseRefName", "")),
                is_draft=bool(pr.get("isDraft", False)),
                when=when, message=message,
            ))
        return ProjectStatus(
            name=name, branch="", dirty=dirty, when=DASH, message=DASH,
            linked=True, failed=False, prs=tuple(prs),
        )
    except Exception:
        # 1 リポジトリの失敗で表全体を止めない。
        return _plain(name, FAILED_LABEL, failed=True)


def collect_all(
    projects: List,
    pr_lister: Optional[Callable[[str], Optional[List[dict]]]] = None,
) -> List[ProjectStatus]:
    """与えられた順序を保ったまま全プロジェクトの状況を集める。

    gh への問い合わせがネットワーク待ちになるため、プロジェクト間は並列化する
    （順序は入力どおりに戻す）。
    """
    if not projects:
        return []
    results: List[Optional[ProjectStatus]] = [None] * len(projects)
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {
            pool.submit(collect_status, project, pr_lister): index
            for index, project in enumerate(projects)
        }
        for future in concurrent.futures.as_completed(futures):
            results[futures[future]] = future.result()
    return [item for item in results if item is not None]
