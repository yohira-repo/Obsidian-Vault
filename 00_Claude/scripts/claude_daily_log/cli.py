#!/usr/bin/env python3
"""Claude Code の会話まとめを Obsidian の Daily ノートへ同期する。"""
import argparse
import datetime
import fcntl
import logging
import os
import sys
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import daily as daily_module
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


def acquire_lock() -> Optional[object]:
    """取得できたらファイルオブジェクト、他プロセスが実行中なら None を返す。"""
    try:
        os.makedirs(os.path.dirname(LOCK_PATH), exist_ok=True)
        handle = open(LOCK_PATH, "w")
    except OSError:
        return None
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        return None
    return handle


def run_sync(vault: str, git_root: str, date: str) -> Dict:
    report = {
        "date": date,
        "sources": 0,
        "entries": 0,
        "mirror_added": 0,
        "mirror_replaced": 0,
        "daily_changed": False,
        "warnings": [],
    }
    if not os.path.isdir(vault):
        report["warnings"].append("Vault が見つかりません: %s" % vault)
        return report

    collected: List = []
    for project in projects_module.list_projects(git_root):
        if not project.exists:
            continue
        try:
            entries, warnings = sources_module.collect_entries(project.path, project.name, date)
        except Exception as error:  # git 失敗も含めてスキップする
            report["warnings"].append("%s: 収集に失敗しました (%s)" % (project.name, error))
            continue
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

    try:
        report["daily_changed"] = daily_module.update_daily(vault, date, entries)
    except daily_module.DailyMarkerError as error:
        report["warnings"].append("Daily の管理ブロックが壊れています: %s" % error)
    except OSError as error:
        report["warnings"].append("Daily 更新に失敗しました (%s)" % error)

    report["sources"] = len(by_source)
    report["entries"] = len(entries)
    logging.info(
        "sync date=%s sources=%d entries=%d added=%d replaced=%d daily_changed=%s warnings=%d",
        date, report["sources"], report["entries"], report["mirror_added"],
        report["mirror_replaced"], report["daily_changed"], len(report["warnings"]),
    )
    return report


def format_report(report: Dict) -> str:
    lines = [
        "対象日: %s" % report["date"],
        "プロジェクト %d 件 / エントリ %d 件" % (report["sources"], report["entries"]),
        "ミラー: 追加 %d / 置換 %d" % (report["mirror_added"], report["mirror_replaced"]),
        "Daily: %s" % ("更新しました" if report["daily_changed"] else "変更なし"),
    ]
    if report.get("fetched") is not None:
        lines.insert(1, "GitHub 同期: fetch %d / clone %d" % (report.get("fetched", 0), report.get("cloned", 0)))
    if report["warnings"]:
        lines.append("警告 %d 件:" % len(report["warnings"]))
        lines.extend("  - " + warning for warning in report["warnings"])
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Claude Code の会話まとめを Obsidian に同期する")
    parser.add_argument("command", choices=["sync"])
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
        logging.info("他プロセスが実行中のため終了します")
        if args.report:
            print("他プロセスが実行中のためスキップしました")
        return 0
    try:
        report = run_sync(args.vault, args.git_root, date)
        if args.report:
            print(format_report(report))
    finally:
        lock.close()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # hook からの起動でも必ず 0 で終わる
        logging.exception("予期しないエラー")
        sys.exit(0)
