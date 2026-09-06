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

    def tearDown(self):
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

    def test_report_option_prints_summary(self):
        report = cli.run_sync(self.vault, self.git_root, "2026-09-06")
        text = cli.format_report(report)
        self.assertIn("2026-09-06", text)
        self.assertIn("1", text)


if __name__ == "__main__":
    unittest.main()
