import datetime
import os
import tempfile
import unittest

import archive


def _touch(path, text="x"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


class ArchivePreviousMonthTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.vault = self._tmp.name
        self.daily = os.path.join(self.vault, "01_Daily")
        os.makedirs(self.daily, exist_ok=True)
        self.today = datetime.date(2026, 10, 1)  # 前月 = 2026-09

    def tearDown(self):
        self._tmp.cleanup()

    def _exists(self, *parts):
        return os.path.exists(os.path.join(self.daily, *parts))

    def test_moves_previous_month_files_into_yyyymm_folder(self):
        _touch(os.path.join(self.daily, "2026-09-01.md"))
        _touch(os.path.join(self.daily, "2026-09-30.md"))

        report = archive.archive_previous_month(self.vault, today=self.today)

        self.assertEqual(report["target"], "202609")
        self.assertEqual(sorted(report["moved"]), ["2026-09-01.md", "2026-09-30.md"])
        self.assertTrue(self._exists("202609", "2026-09-01.md"))
        self.assertTrue(self._exists("202609", "2026-09-30.md"))
        self.assertFalse(self._exists("2026-09-01.md"))
        self.assertFalse(self._exists("2026-09-30.md"))

    def test_keeps_current_month_in_root(self):
        _touch(os.path.join(self.daily, "2026-10-01.md"))

        report = archive.archive_previous_month(self.vault, today=self.today)

        self.assertEqual(report["moved"], [])
        self.assertTrue(self._exists("2026-10-01.md"))
        self.assertFalse(self._exists("202609"))

    def test_leaves_older_than_previous_month_untouched(self):
        # 2 か月以上前（あえて残している可能性のある重要ノート）は触らない。
        _touch(os.path.join(self.daily, "2026-08-31.md"))

        report = archive.archive_previous_month(self.vault, today=self.today)

        self.assertEqual(report["moved"], [])
        self.assertTrue(self._exists("2026-08-31.md"))

    def test_is_idempotent_when_no_targets(self):
        report = archive.archive_previous_month(self.vault, today=self.today)
        self.assertEqual(report["moved"], [])
        self.assertEqual(report["warnings"], [])

    def test_skips_and_warns_on_name_collision(self):
        _touch(os.path.join(self.daily, "2026-09-05.md"), text="new")
        _touch(os.path.join(self.daily, "202609", "2026-09-05.md"), text="existing")

        report = archive.archive_previous_month(self.vault, today=self.today)

        self.assertEqual(report["moved"], [])
        self.assertEqual(report["skipped"], ["2026-09-05.md"])
        self.assertEqual(len(report["warnings"]), 1)
        # 既存ファイルは上書きされない。
        with open(os.path.join(self.daily, "202609", "2026-09-05.md"), encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "existing")
        # 元ファイルも残る（取りこぼしに気づけるように）。
        self.assertTrue(self._exists("2026-09-05.md"))

    def test_ignores_non_daily_files(self):
        _touch(os.path.join(self.daily, "2026-09-notes.md"))
        _touch(os.path.join(self.daily, "random.md"))
        _touch(os.path.join(self.daily, "2026-09-01.txt"))

        report = archive.archive_previous_month(self.vault, today=self.today)

        self.assertEqual(report["moved"], [])
        self.assertTrue(self._exists("2026-09-notes.md"))
        self.assertTrue(self._exists("random.md"))
        self.assertTrue(self._exists("2026-09-01.txt"))

    def test_dry_run_reports_without_moving(self):
        _touch(os.path.join(self.daily, "2026-09-10.md"))

        report = archive.archive_previous_month(self.vault, today=self.today, dry_run=True)

        self.assertEqual(report["moved"], ["2026-09-10.md"])
        self.assertTrue(self._exists("2026-09-10.md"))      # 動かしていない
        self.assertFalse(self._exists("202609"))            # フォルダも作らない

    def test_year_boundary_january_targets_previous_december(self):
        _touch(os.path.join(self.daily, "2025-12-31.md"))

        report = archive.archive_previous_month(
            self.vault, today=datetime.date(2026, 1, 3),
        )

        self.assertEqual(report["target"], "202512")
        self.assertEqual(report["moved"], ["2025-12-31.md"])
        self.assertTrue(self._exists("202512", "2025-12-31.md"))

    def test_missing_daily_dir_warns_without_raising(self):
        empty_vault = tempfile.mkdtemp(dir=self.vault)
        report = archive.archive_previous_month(empty_vault, today=self.today)
        self.assertEqual(report["moved"], [])
        self.assertEqual(len(report["warnings"]), 1)


if __name__ == "__main__":
    unittest.main()
