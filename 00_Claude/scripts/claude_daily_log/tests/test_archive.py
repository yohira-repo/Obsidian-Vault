import os
import tempfile
import unittest

import archive


class RecordingMover:
    """CLI を叩かずに移動要求だけ記録するテスト用 mover。"""

    def __init__(self, fail_on=None):
        self.calls = []
        self.fail_on = fail_on or set()

    def __call__(self, vault, src_relpath, dst_relpath):
        self.calls.append((src_relpath, dst_relpath))
        if src_relpath in self.fail_on:
            raise archive.MoveError("移動に失敗しました: %s" % src_relpath)
        # 実際の Obsidian CLI と同じく、ファイルシステム上も移動した状態にする
        src = os.path.join(vault, src_relpath)
        dst = os.path.join(vault, dst_relpath)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        os.replace(src, dst)


class ArchiveTestBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = self.tmp.name
        os.makedirs(os.path.join(self.vault, archive.DAILY_DIR), exist_ok=True)

    def tearDown(self):
        self.tmp.cleanup()

    def touch(self, relpath, text="x\n"):
        path = os.path.join(self.vault, relpath)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path

    def exists(self, relpath):
        return os.path.exists(os.path.join(self.vault, relpath))


class PlanArchiveTest(ArchiveTestBase):
    def test_moves_previous_months_and_keeps_current_month(self):
        for name in ("2026-08-01.md", "2026-08-31.md", "2026-09-01.md", "2026-09-28.md"):
            self.touch(os.path.join(archive.DAILY_DIR, name))

        plan = archive.plan_archive(self.vault, "2026-09-28")

        self.assertEqual(plan, [
            (os.path.join("01_Daily", "2026-08-01.md"), os.path.join("01_Daily", "202608", "2026-08-01.md")),
            (os.path.join("01_Daily", "2026-08-31.md"), os.path.join("01_Daily", "202608", "2026-08-31.md")),
        ])

    def test_covers_all_older_months_not_just_previous(self):
        for name in ("2026-06-30.md", "2026-07-15.md", "2026-08-02.md", "2026-09-28.md"):
            self.touch(os.path.join(archive.DAILY_DIR, name))

        plan = archive.plan_archive(self.vault, "2026-09-28")

        self.assertEqual(
            [dst for _src, dst in plan],
            [
                os.path.join("01_Daily", "202606", "2026-06-30.md"),
                os.path.join("01_Daily", "202607", "2026-07-15.md"),
                os.path.join("01_Daily", "202608", "2026-08-02.md"),
            ],
        )

    def test_ignores_subfolders_and_non_daily_files(self):
        self.touch(os.path.join(archive.DAILY_DIR, "202607", "2026-07-01.md"))
        self.touch(os.path.join(archive.DAILY_DIR, "memo.md"))
        self.touch(os.path.join(archive.DAILY_DIR, "2026-08-1.md"))
        self.touch(os.path.join(archive.DAILY_DIR, "2026-08-01.txt"))

        self.assertEqual(archive.plan_archive(self.vault, "2026-09-28"), [])

    def test_missing_daily_dir_yields_empty_plan(self):
        with tempfile.TemporaryDirectory() as empty:
            self.assertEqual(archive.plan_archive(empty, "2026-09-28"), [])


class RunArchiveTest(ArchiveTestBase):
    def test_moves_files_and_reports_count(self):
        self.touch(os.path.join(archive.DAILY_DIR, "2026-08-01.md"))
        self.touch(os.path.join(archive.DAILY_DIR, "2026-09-28.md"))
        mover = RecordingMover()

        report = archive.run_archive(self.vault, "2026-09-28", mover=mover)

        self.assertEqual(report["moved"], 1)
        self.assertEqual(report["warnings"], [])
        self.assertFalse(self.exists(os.path.join(archive.DAILY_DIR, "2026-08-01.md")))
        self.assertTrue(self.exists(os.path.join(archive.DAILY_DIR, "202608", "2026-08-01.md")))
        self.assertTrue(self.exists(os.path.join(archive.DAILY_DIR, "2026-09-28.md")))

    def test_creates_month_folder_before_moving(self):
        self.touch(os.path.join(archive.DAILY_DIR, "2026-08-01.md"))
        seen = []

        def mover(vault, src, dst):
            seen.append(os.path.isdir(os.path.join(vault, os.path.dirname(dst))))
            os.replace(os.path.join(vault, src), os.path.join(vault, dst))

        archive.run_archive(self.vault, "2026-09-28", mover=mover)

        self.assertEqual(seen, [True])

    def test_existing_destination_is_skipped_with_warning(self):
        self.touch(os.path.join(archive.DAILY_DIR, "2026-08-01.md"))
        self.touch(os.path.join(archive.DAILY_DIR, "202608", "2026-08-01.md"))
        mover = RecordingMover()

        report = archive.run_archive(self.vault, "2026-09-28", mover=mover)

        self.assertEqual(mover.calls, [])
        self.assertEqual(report["moved"], 0)
        self.assertEqual(len(report["warnings"]), 1)
        self.assertIn("2026-08-01.md", report["warnings"][0])
        self.assertTrue(self.exists(os.path.join(archive.DAILY_DIR, "2026-08-01.md")))

    def test_move_failure_warns_and_continues_with_remaining_files(self):
        self.touch(os.path.join(archive.DAILY_DIR, "2026-07-01.md"))
        self.touch(os.path.join(archive.DAILY_DIR, "2026-08-01.md"))
        mover = RecordingMover(fail_on={os.path.join(archive.DAILY_DIR, "2026-07-01.md")})

        report = archive.run_archive(self.vault, "2026-09-28", mover=mover)

        self.assertEqual(report["moved"], 1)
        self.assertEqual(len(report["warnings"]), 1)
        self.assertIn("2026-07-01.md", report["warnings"][0])
        self.assertTrue(self.exists(os.path.join(archive.DAILY_DIR, "2026-07-01.md")))
        self.assertTrue(self.exists(os.path.join(archive.DAILY_DIR, "202608", "2026-08-01.md")))

    def test_silent_noop_mover_is_treated_as_failure(self):
        # Obsidian の CLI が無効なとき、`obsidian` は何もせず exit 0 を返す。
        # 終了コードだけを信じて「移動した」と報告してはいけない。
        self.touch(os.path.join(archive.DAILY_DIR, "2026-08-01.md"))

        def noop_mover(vault, src, dst):
            return None

        report = archive.run_archive(self.vault, "2026-09-28", mover=noop_mover)

        self.assertEqual(report["moved"], 0)
        self.assertEqual(len(report["warnings"]), 1)
        self.assertIn("2026-08-01.md", report["warnings"][0])
        self.assertTrue(self.exists(os.path.join(archive.DAILY_DIR, "2026-08-01.md")))

    def test_nothing_to_do_is_quiet(self):
        self.touch(os.path.join(archive.DAILY_DIR, "2026-09-28.md"))
        mover = RecordingMover()

        report = archive.run_archive(self.vault, "2026-09-28", mover=mover)

        self.assertEqual(report, {"moved": 0, "warnings": []})
        self.assertEqual(mover.calls, [])

    def test_invalid_date_is_reported_as_warning(self):
        self.touch(os.path.join(archive.DAILY_DIR, "2026-08-01.md"))
        mover = RecordingMover()

        report = archive.run_archive(self.vault, "not-a-date", mover=mover)

        self.assertEqual(report["moved"], 0)
        self.assertEqual(len(report["warnings"]), 1)
        self.assertEqual(mover.calls, [])


class ObsidianMoverTest(ArchiveTestBase):
    def test_builds_obsidian_cli_command(self):
        recorded = {}

        def runner(command):
            recorded["command"] = command
            return 0, ""

        archive.obsidian_move(
            os.path.join("C:\\", "vault", "Obsidian-Vault"),
            os.path.join("01_Daily", "2026-08-01.md"),
            os.path.join("01_Daily", "202608", "2026-08-01.md"),
            runner=runner,
        )

        self.assertEqual(recorded["command"], [
            "obsidian",
            "vault=Obsidian-Vault",
            "move",
            "path=01_Daily/2026-08-01.md",
            "to=01_Daily/202608/2026-08-01.md",
        ])

    def test_nonzero_exit_raises_move_error(self):
        def runner(command):
            return 1, "vault not running"

        with self.assertRaises(archive.MoveError) as caught:
            archive.obsidian_move(self.vault, "01_Daily/a.md", "01_Daily/202608/a.md", runner=runner)

        self.assertIn("vault not running", str(caught.exception))

    def test_missing_cli_raises_move_error(self):
        def runner(command):
            raise FileNotFoundError("obsidian")

        with self.assertRaises(archive.MoveError):
            archive.obsidian_move(self.vault, "01_Daily/a.md", "01_Daily/202608/a.md", runner=runner)


if __name__ == "__main__":
    unittest.main()
