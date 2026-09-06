#!/usr/bin/env python3
"""Claude Code の会話まとめを Obsidian の Daily ノートへ同期する。"""
import argparse
import datetime
import logging
import os
import sys
import time
from typing import Dict, List, Optional

try:
    import fcntl  # POSIX 専用。Windows には存在しない
except ImportError:  # pragma: no cover - このリポジトリの CI は POSIX のみ
    fcntl = None

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import daily as daily_module
import gitsync as gitsync_module
import mirror as mirror_module
import projects as projects_module
import sources as sources_module

DEFAULT_VAULT = os.path.expanduser("~/Documents/Obsidian-Vault")
DEFAULT_GIT_ROOT = os.path.expanduser("~/git")
LOCK_PATH = os.path.expanduser("~/.claude/cache/claude_daily_log.lock")
STAMP_PATH = os.path.expanduser("~/.claude/cache/claude_daily_log.fetch_stamp")
LOG_PATH = os.path.expanduser("~/.claude/logs/claude_daily_log.log")
LOG_MAX_BYTES = 1024 * 1024
FETCH_INTERVAL_SECONDS = 30 * 60
LOCK_RETRY_ATTEMPTS = 5
LOCK_RETRY_DELAY_SECONDS = 0.5  # 4 回分の待ち = 合計 約2秒
STALE_LOCK_SECONDS = 6 * 60 * 60  # フォールバックロックのみ: 6 時間以上前なら残留とみなす


def setup_logging() -> None:
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        if os.path.exists(LOG_PATH) and os.path.getsize(LOG_PATH) > LOG_MAX_BYTES:
            os.replace(LOG_PATH, LOG_PATH + ".1")
        logging.basicConfig(
            filename=LOG_PATH,
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(message)s",
        )
    except OSError:
        logging.basicConfig(level=logging.CRITICAL)


class _LockFsError(Exception):
    """ロックファイル自体の作成・オープンに失敗した（ディスクフル・権限不足等）。"""

    def __init__(self, original: BaseException):
        super().__init__(str(original))
        self.original = original


class _LockContended(Exception):
    """ロックは正常に取り扱えたが、他プロセスが保持している。"""

    def __init__(self, original: BaseException):
        super().__init__(str(original))
        self.original = original


class _PortableLockHandle:
    """fcntl が無い環境（Windows）向け: O_CREAT|O_EXCL によるロックファイル。

    close() でファイルディスクリプタを閉じたうえでロックファイル自体を
    削除する（次回実行が取得できるようにするため）。
    """

    def __init__(self, fd: int):
        self._fd = fd

    def close(self) -> None:
        try:
            os.close(self._fd)
        finally:
            try:
                os.remove(LOCK_PATH)
            except OSError:
                pass


def _acquire_posix_lock():
    """fcntl.flock によるロック取得。取得できなければ例外を送出する。"""
    try:
        os.makedirs(os.path.dirname(LOCK_PATH), exist_ok=True)
        handle = open(LOCK_PATH, "w")
    except OSError as error:
        raise _LockFsError(error)
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as error:
        handle.close()
        raise _LockContended(error)
    return handle


def _acquire_portable_lock():
    """fcntl が無い環境向けのフォールバック: O_CREAT|O_EXCL による排他。

    Windows では fcntl.flock が使えないため、代わりにロックファイルの
    排他的新規作成で同時実行を防ぐ。プロセスが異常終了してファイルが
    残った場合に永久にロックされたままにならないよう、
    STALE_LOCK_SECONDS より古いロックファイルは残留とみなして削除し、
    再取得を試みる。
    """
    try:
        os.makedirs(os.path.dirname(LOCK_PATH), exist_ok=True)
    except OSError as error:
        raise _LockFsError(error)

    def _create():
        return os.open(LOCK_PATH, os.O_CREAT | os.O_EXCL | os.O_WRONLY)

    try:
        fd = _create()
    except FileExistsError as error:
        try:
            age = time.time() - os.path.getmtime(LOCK_PATH)
        except OSError:
            age = None
        if age is not None and age > STALE_LOCK_SECONDS:
            try:
                os.remove(LOCK_PATH)
                fd = _create()
            except OSError as remove_error:
                raise _LockContended(remove_error)
        else:
            raise _LockContended(error)
    except OSError as error:
        raise _LockFsError(error)

    try:
        os.write(fd, str(os.getpid()).encode("utf-8"))
    except OSError:
        pass
    return _PortableLockHandle(fd)


def acquire_lock() -> Optional[object]:
    """取得できたらロックオブジェクト、取得できなければ None を返す。

    - POSIX では fcntl.flock、Windows（fcntl が無い環境）では
      O_CREAT|O_EXCL ロックファイルにフォールバックする（D）。
    - 他プロセスが実行中で取得できない場合は、短い間隔で数回
      リトライしてから諦める（合計 約2秒。F）。
    - ファイルシステムエラー（ディスクフル・権限不足等）とロック競合
      を、ログ上で区別する（I）。
    """
    acquire_once = _acquire_posix_lock if fcntl is not None else _acquire_portable_lock
    for attempt in range(LOCK_RETRY_ATTEMPTS):
        try:
            return acquire_once()
        except _LockFsError as error:
            logging.warning("ロックファイルの操作に失敗しました（ファイルシステムエラー）: %s", error.original)
            return None
        except _LockContended as error:
            if attempt < LOCK_RETRY_ATTEMPTS - 1:
                time.sleep(LOCK_RETRY_DELAY_SECONDS)
                continue
            logging.info("他プロセスが実行中のため終了します（ロック競合）: %s", error.original)
            return None
    return None


def _fetch_due() -> bool:
    try:
        return (time.time() - os.path.getmtime(STAMP_PATH)) >= FETCH_INTERVAL_SECONDS
    except OSError:
        return True


def _touch_stamp() -> None:
    try:
        os.makedirs(os.path.dirname(STAMP_PATH), exist_ok=True)
        with open(STAMP_PATH, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(datetime.datetime.now().isoformat())
    except OSError:
        pass


def run_sync(vault: str, git_root: str, date: str) -> Dict:
    report = {
        "date": date,
        "sources": 0,
        "entries": 0,
        "mirror_added": 0,
        "mirror_replaced": 0,
        "daily_changed": False,
        "daily_skipped": False,
        "warnings": [],
    }
    if not os.path.isdir(vault):
        report["warnings"].append("Vault が見つかりません: %s" % vault)
        return report

    all_projects = projects_module.list_projects(git_root)
    existing_projects = [project for project in all_projects if project.exists]

    collected: List = []
    scanned_ok = 0
    for project in existing_projects:
        try:
            entries, warnings = sources_module.collect_entries(project.path, project.name, date)
        except Exception as error:  # git 失敗も含めてスキップする
            report["warnings"].append("%s: 収集に失敗しました (%s)" % (project.name, error))
            continue
        scanned_ok += 1
        collected.extend(entries)
        report["warnings"].extend(warnings)

    entries = sources_module.dedupe(collected)
    by_source: Dict[str, List] = {}
    for entry in entries:
        by_source.setdefault(entry.source_id, []).append(entry)

    for source_id in sorted(by_source):
        try:
            added, replaced = mirror_module.update_mirror(vault, source_id, by_source[source_id])
        except OSError as error:
            report["warnings"].append("%s: ミラー更新に失敗しました (%s)" % (source_id, error))
            continue
        report["mirror_added"] += added
        report["mirror_replaced"] += replaced

    if not all_projects:
        report["daily_skipped"] = True
        report["warnings"].append(
            "対象プロジェクトが見つかりません（CLAUDE.md を読めません）。Daily は更新しません"
        )
    elif not existing_projects:
        report["daily_skipped"] = True
        report["warnings"].append(
            "clone 済みの対象プロジェクトが 1 件もありません。Daily は更新しません"
        )
    elif scanned_ok == 0:
        report["daily_skipped"] = True
        report["warnings"].append(
            "すべてのプロジェクトで収集に失敗しました。Daily は更新しません"
        )
    else:
        try:
            report["daily_changed"] = daily_module.update_daily(vault, date, entries)
        except daily_module.DailyMarkerError as error:
            report["warnings"].append("Daily の管理ブロックが壊れています: %s" % error)
        except OSError as error:
            report["warnings"].append("Daily 更新に失敗しました (%s)" % error)

    report["sources"] = len(by_source)
    report["entries"] = len(entries)
    logging.info(
        "sync date=%s sources=%d entries=%d added=%d replaced=%d daily_changed=%s daily_skipped=%s warnings=%d",
        date, report["sources"], report["entries"], report["mirror_added"],
        report["mirror_replaced"], report["daily_changed"], report["daily_skipped"], len(report["warnings"]),
    )
    return report


def format_report(report: Dict) -> str:
    lines = [
        "対象日: %s" % report["date"],
        "プロジェクト %d 件 / エントリ %d 件" % (report["sources"], report["entries"]),
        "ミラー: 追加 %d / 置換 %d" % (report["mirror_added"], report["mirror_replaced"]),
        "Daily: %s" % (
            "スキップしました（走査失敗のため）" if report.get("daily_skipped")
            else "更新しました" if report["daily_changed"] else "変更なし"
        ),
    ]
    if report.get("fetched") is not None:
        lines.insert(1, "GitHub 同期: fetch %d / clone %d" % (report.get("fetched", 0), report.get("cloned", 0)))
    if report["warnings"]:
        lines.append("警告 %d 件:" % len(report["warnings"]))
        lines.extend("  - " + warning for warning in report["warnings"])
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Claude Code の会話まとめを Obsidian に同期する")
    parser.add_argument("command", choices=["sync", "fetch", "auto"])
    parser.add_argument("--force-fetch", action="store_true", help="auto でも必ず fetch する")
    parser.add_argument("--date", default=None, help="対象日 (YYYY-MM-DD)。既定は今日")
    parser.add_argument("--vault", default=os.environ.get("CLAUDE_DAILY_LOG_VAULT", DEFAULT_VAULT))
    parser.add_argument("--git-root", default=os.environ.get("CLAUDE_DAILY_LOG_GIT_ROOT", DEFAULT_GIT_ROOT))
    parser.add_argument("--report", action="store_true", help="結果を標準出力に表示する")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    setup_logging()
    date = args.date or datetime.date.today().isoformat()

    lock = acquire_lock()
    if lock is None:
        # 具体的な理由（ロック競合 / ファイルシステムエラー）は acquire_lock() 側でログ済み。
        if args.report:
            print("他プロセスが実行中のためスキップしました")
        return 0
    try:
        fetch_report = None
        if args.command == "fetch" or (args.command == "auto" and (args.force_fetch or _fetch_due())):
            try:
                fetch_report = gitsync_module.run_fetch(args.git_root)
                _touch_stamp()
                logging.info(
                    "fetch fetched=%d cloned=%d warnings=%d",
                    fetch_report["fetched"], fetch_report["cloned"], len(fetch_report["warnings"]),
                )
            except Exception as error:  # fetch の失敗は該当分のみスキップし、sync は必ず実行する
                logging.exception("fetch 処理で予期しないエラー")
                fetch_report = {
                    "fetched": 0,
                    "cloned": 0,
                    "warnings": ["fetch 処理で予期しないエラー (%s)" % error],
                }
        report = run_sync(args.vault, args.git_root, date)
        if fetch_report is not None:
            report["fetched"] = fetch_report["fetched"]
            report["cloned"] = fetch_report["cloned"]
            report["warnings"] = fetch_report["warnings"] + report["warnings"]
        if args.report:
            print(format_report(report))
    except Exception:  # hook から呼ばれるため、想定外の例外でも 0 を返す
        logging.exception("予期しないエラー")
    finally:
        lock.close()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # hook からの起動でも必ず 0 で終わる
        logging.exception("予期しないエラー")
        sys.exit(0)
