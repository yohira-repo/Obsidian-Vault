import os
import tempfile
import unittest

import cli
from tests import helpers

CONV = """# 会話ログ

## 2026-09-06 当日のまとめ

当日の本文。

## 2026-09-05 前日のまとめ

前日の本文。
"""

TABLE = """| プロジェクト名 | 相対フォルダー | 内容 |
| - | - | - |
| repo_a | ../repo_a | テスト用 |
| repo_b | ../repo_b | 未 clone |
"""


class RunSyncTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.git_root = os.path.join(self.tmp.name, "git")
        self.vault = os.path.join(self.tmp.name, "vault")
        os.makedirs(os.path.join(self.git_root, "alphasystem"))
        os.makedirs(self.vault)
        with open(os.path.join(self.git_root, "alphasystem", "CLAUDE.md"), "w", encoding="utf-8") as handle:
            handle.write(TABLE)
        origin = helpers.init_repo(os.path.join(self.tmp.name, "origin_a"), {"conversations.md": CONV})
        helpers.clone_repo(origin, os.path.join(self.git_root, "repo_a"))

        # ブロッカー E: cli.main() が実ユーザーの ~/.claude を触らないよう、
        # ロック・ログ・スタンプのパスを一時ディレクトリへ差し替える。
        self._orig_lock_path = cli.LOCK_PATH
        self._orig_log_path = cli.LOG_PATH
        self._orig_stamp_path = cli.STAMP_PATH
        cli.LOCK_PATH = os.path.join(self.tmp.name, "cache", "claude_daily_log.lock")
        cli.LOG_PATH = os.path.join(self.tmp.name, "logs", "claude_daily_log.log")
        cli.STAMP_PATH = os.path.join(self.tmp.name, "cache", "claude_daily_log.fetch_stamp")

    def tearDown(self):
        cli.LOCK_PATH = self._orig_lock_path
        cli.LOG_PATH = self._orig_log_path
        cli.STAMP_PATH = self._orig_stamp_path
        self.tmp.cleanup()

    def read_daily(self, date="2026-09-06"):
        path = os.path.join(self.vault, "01_Daily", date + ".md")
        with open(path, encoding="utf-8") as handle:
            return handle.read()

    def test_sync_writes_daily_and_mirror(self):
        report = cli.run_sync(self.vault, self.git_root, "2026-09-06")
        self.assertEqual(report["entries"], 1)
        self.assertTrue(report["daily_changed"])
        self.assertIn("当日のまとめ", self.read_daily())
        mirror_path = os.path.join(self.vault, "00_Claude", "projects", "repo_a.md")
        self.assertTrue(os.path.exists(mirror_path))

    def test_second_run_produces_no_diff(self):
        cli.run_sync(self.vault, self.git_root, "2026-09-06")
        before = self.read_daily()
        report = cli.run_sync(self.vault, self.git_root, "2026-09-06")
        self.assertEqual((report["mirror_added"], report["mirror_replaced"]), (0, 0))
        self.assertFalse(report["daily_changed"])
        self.assertEqual(self.read_daily(), before)

    def test_date_option_regenerates_past_day(self):
        cli.run_sync(self.vault, self.git_root, "2026-09-05")
        self.assertIn("前日のまとめ", self.read_daily("2026-09-05"))

    def test_uncloned_project_is_skipped_without_error(self):
        report = cli.run_sync(self.vault, self.git_root, "2026-09-06")
        self.assertEqual(report["warnings"], [])

    def test_missing_vault_is_reported_and_does_not_raise(self):
        report = cli.run_sync(os.path.join(self.tmp.name, "no_vault"), self.git_root, "2026-09-06")
        self.assertTrue(any("Vault" in warning for warning in report["warnings"]))

    def test_main_returns_zero(self):
        code = cli.main(["sync", "--date", "2026-09-06", "--vault", self.vault, "--git-root", self.git_root])
        self.assertEqual(code, 0)
        self.assertIn("当日のまとめ", self.read_daily())

    def test_main_uses_patched_lock_and_log_paths_not_real_home(self):
        # ブロッカー E: 実ユーザーの ~/.claude/cache や ~/.claude/logs を触っていないことの確認。
        real_default_lock = os.path.expanduser("~/.claude/cache/claude_daily_log.lock")
        self.assertNotEqual(cli.LOCK_PATH, real_default_lock)
        cli.main(["sync", "--date", "2026-09-06", "--vault", self.vault, "--git-root", self.git_root])
        self.assertTrue(os.path.exists(cli.LOCK_PATH))
        self.assertTrue(cli.LOCK_PATH.startswith(self.tmp.name))
        self.assertTrue(cli.LOG_PATH.startswith(self.tmp.name))

    def test_report_option_prints_summary(self):
        report = cli.run_sync(self.vault, self.git_root, "2026-09-06")
        text = cli.format_report(report)
        self.assertIn("2026-09-06", text)
        self.assertIn("1", text)


class DiscoveryFailureTest(unittest.TestCase):
    """スキャン自体が失敗した場合は Daily を一切書き換えない（ブロッカー A）。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = os.path.join(self.tmp.name, "vault")
        os.makedirs(os.path.join(self.vault, "01_Daily"))
        self.daily_path = os.path.join(self.vault, "01_Daily", "2026-09-06.md")
        self.handwritten = (
            "## Claude作業ログ\n\n<!-- claude-log:start -->\n"
            "- **coopinf** — [[00_Claude/projects/coopinf#2026-09-06 まとめ|まとめ]]\n"
            "<!-- claude-log:end -->\n"
        )
        with open(self.daily_path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(self.handwritten)

    def tearDown(self):
        self.tmp.cleanup()

    def read_daily(self):
        with open(self.daily_path, encoding="utf-8") as handle:
            return handle.read()

    def test_no_claude_md_at_all_skips_daily_untouched(self):
        # git_root に CLAUDE.md が一つも無い（対象プロジェクトが 0 件）
        empty_git_root = os.path.join(self.tmp.name, "git_no_claude_md")
        os.makedirs(empty_git_root)
        report = cli.run_sync(self.vault, empty_git_root, "2026-09-06")
        self.assertTrue(report["daily_skipped"])
        self.assertFalse(report["daily_changed"])
        self.assertEqual(self.read_daily(), self.handwritten)
        self.assertTrue(report["warnings"])

    def test_no_cloned_project_skips_daily_untouched(self):
        # CLAUDE.md はあるが、対象プロジェクトが 1 つも clone されていない
        git_root = os.path.join(self.tmp.name, "git_uncloned")
        os.makedirs(os.path.join(git_root, "alphasystem"))
        with open(os.path.join(git_root, "alphasystem", "CLAUDE.md"), "w", encoding="utf-8") as handle:
            handle.write(TABLE)
        report = cli.run_sync(self.vault, git_root, "2026-09-06")
        self.assertTrue(report["daily_skipped"])
        self.assertFalse(report["daily_changed"])
        self.assertEqual(self.read_daily(), self.handwritten)
        self.assertTrue(report["warnings"])

    def test_every_existing_project_raising_skips_daily_untouched(self):
        # プロジェクトは clone 済み（.git は存在する）が、収集が必ず失敗する壊れたリポジトリ
        git_root = os.path.join(self.tmp.name, "git_broken")
        os.makedirs(os.path.join(git_root, "alphasystem"))
        with open(os.path.join(git_root, "alphasystem", "CLAUDE.md"), "w", encoding="utf-8") as handle:
            handle.write(TABLE)
        broken = os.path.join(git_root, "repo_a")
        os.makedirs(os.path.join(broken, ".git"))  # .git はディレクトリだが git リポジトリとして壊れている
        report = cli.run_sync(self.vault, git_root, "2026-09-06")
        self.assertTrue(report["daily_skipped"])
        self.assertFalse(report["daily_changed"])
        self.assertEqual(self.read_daily(), self.handwritten)
        self.assertTrue(any("収集に失敗" in warning for warning in report["warnings"]))

    def test_successful_scan_with_zero_entries_still_clears_block(self):
        # 少なくとも 1 件は正常にスキャンできたが、対象日の該当が 0 件 → 従来通り空にする（回帰させない）
        git_root = os.path.join(self.tmp.name, "git_ok")
        os.makedirs(os.path.join(git_root, "alphasystem"))
        with open(os.path.join(git_root, "alphasystem", "CLAUDE.md"), "w", encoding="utf-8") as handle:
            handle.write(TABLE)
        origin = helpers.init_repo(
            os.path.join(self.tmp.name, "origin_ok"),
            {"conversations.md": "## 2026-01-01 昔のまとめ\n\n昔の本文。\n"},
        )
        helpers.clone_repo(origin, os.path.join(git_root, "repo_a"))
        report = cli.run_sync(self.vault, git_root, "2026-09-06")
        self.assertFalse(report["daily_skipped"])
        self.assertTrue(report["daily_changed"])
        text = self.read_daily()
        self.assertIn("<!-- claude-log:start -->\n<!-- claude-log:end -->", text)

    def test_format_report_surfaces_daily_skipped(self):
        empty_git_root = os.path.join(self.tmp.name, "git_no_claude_md2")
        os.makedirs(empty_git_root)
        report = cli.run_sync(self.vault, empty_git_root, "2026-09-06")
        text = cli.format_report(report)
        self.assertIn("スキップ", text)


class DateValidationTest(unittest.TestCase):
    """item L: --date は datetime.date.fromisoformat で検証し、不正なら何も書かず exit 0。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.git_root = os.path.join(self.tmp.name, "git")
        self.vault = os.path.join(self.tmp.name, "vault")
        os.makedirs(os.path.join(self.git_root, "alphasystem"))
        os.makedirs(self.vault)
        with open(os.path.join(self.git_root, "alphasystem", "CLAUDE.md"), "w", encoding="utf-8") as handle:
            handle.write(TABLE)
        origin = helpers.init_repo(os.path.join(self.tmp.name, "origin_a"), {"conversations.md": CONV})
        helpers.clone_repo(origin, os.path.join(self.git_root, "repo_a"))

        self._orig_lock_path = cli.LOCK_PATH
        self._orig_log_path = cli.LOG_PATH
        self._orig_stamp_path = cli.STAMP_PATH
        cli.LOCK_PATH = os.path.join(self.tmp.name, "cache", "claude_daily_log.lock")
        cli.LOG_PATH = os.path.join(self.tmp.name, "logs", "claude_daily_log.log")
        cli.STAMP_PATH = os.path.join(self.tmp.name, "cache", "claude_daily_log.fetch_stamp")

    def tearDown(self):
        cli.LOCK_PATH = self._orig_lock_path
        cli.LOG_PATH = self._orig_log_path
        cli.STAMP_PATH = self._orig_stamp_path
        self.tmp.cleanup()

    def test_non_date_string_is_rejected_without_writing_anything(self):
        code = cli.main([
            "sync", "--date", "not-a-date",
            "--vault", self.vault, "--git-root", self.git_root,
        ])
        self.assertEqual(code, 0)
        self.assertFalse(
            os.path.exists(os.path.join(self.vault, "01_Daily", "not-a-date.md")),
        )
        # Vault 配下に一切ファイルが作られていないこと（01_Daily ディレクトリすら作られない）
        self.assertFalse(os.path.exists(os.path.join(self.vault, "01_Daily")))

    def test_path_traversal_like_date_is_rejected(self):
        code = cli.main([
            "sync", "--date", "../../foo",
            "--vault", self.vault, "--git-root", self.git_root,
        ])
        self.assertEqual(code, 0)
        escaped = os.path.normpath(os.path.join(self.vault, "01_Daily", "../../foo.md"))
        self.assertFalse(os.path.exists(escaped))

    def test_invalid_date_is_reported_when_report_flag_set(self):
        import contextlib
        import io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cli.main([
                "sync", "--date", "not-a-date",
                "--vault", self.vault, "--git-root", self.git_root, "--report",
            ])
        self.assertIn("--date", buf.getvalue())

    def test_valid_date_still_works(self):
        code = cli.main([
            "sync", "--date", "2026-09-06",
            "--vault", self.vault, "--git-root", self.git_root,
        ])
        self.assertEqual(code, 0)
        self.assertIn("当日のまとめ", self.read_daily())

    def read_daily(self, date="2026-09-06"):
        path = os.path.join(self.vault, "01_Daily", date + ".md")
        with open(path, encoding="utf-8") as handle:
            return handle.read()


if __name__ == "__main__":
    unittest.main()
