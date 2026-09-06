import os
import tempfile
import time
import unittest

import cli
import gitsync
import projects
from tests import helpers


class RunFetchTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.origin = helpers.init_repo(os.path.join(self.tmp.name, "origin"), {"conversations.md": "# x\n"})
        self.work = helpers.clone_repo(self.origin, os.path.join(self.tmp.name, "work"))

    def tearDown(self):
        self.tmp.cleanup()

    def test_fetches_existing_clone(self):
        report = gitsync.run_fetch(self.tmp.name, [projects.Project(name="work", path=self.work)])
        self.assertEqual(report["fetched"], 1)
        self.assertEqual(report["warnings"], [])

    def test_new_remote_branch_becomes_visible_after_fetch(self):
        helpers.commit_on_branch(self.origin, "feature/x", {"conversations.md": "# y\n"})
        gitsync.run_fetch(self.tmp.name, [projects.Project(name="work", path=self.work)])
        refs = helpers.subprocess.run(
            ["git", "-C", self.work, "for-each-ref", "--format=%(refname:short)", "refs/remotes/origin"],
            capture_output=True, text=True, check=True,
        ).stdout
        self.assertIn("origin/feature/x", refs)

    def test_missing_project_is_cloned(self):
        # ネットワークに出ないよう、clone 元をローカルパスに差し替える
        original = gitsync.CLONE_URL_TEMPLATE
        gitsync.CLONE_URL_TEMPLATE = os.path.join(self.tmp.name, "%s")
        try:
            target = projects.Project(name="origin", path=os.path.join(self.tmp.name, "cloned"))
            report = gitsync.run_fetch(self.tmp.name, [target])
        finally:
            gitsync.CLONE_URL_TEMPLATE = original
        self.assertEqual(report["cloned"], 1)
        self.assertTrue(os.path.isdir(os.path.join(self.tmp.name, "cloned", ".git")))

    def test_clone_failure_is_reported_as_warning(self):
        original = gitsync.CLONE_URL_TEMPLATE
        gitsync.CLONE_URL_TEMPLATE = os.path.join(self.tmp.name, "no_such_%s")
        try:
            missing = projects.Project(name="ghost", path=os.path.join(self.tmp.name, "missing"))
            report = gitsync.run_fetch(self.tmp.name, [missing])
        finally:
            gitsync.CLONE_URL_TEMPLATE = original
        self.assertEqual(report["cloned"], 0)
        self.assertEqual(len(report["warnings"]), 1)
        self.assertIn("ghost", report["warnings"][0])


class FetchIsolationTest(unittest.TestCase):
    """ブロッカー C: fetch が例外を投げても sync はスキップされない。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.git_root = os.path.join(self.tmp.name, "git")
        self.vault = os.path.join(self.tmp.name, "vault")
        os.makedirs(os.path.join(self.git_root, "alphasystem"))
        os.makedirs(self.vault)
        with open(os.path.join(self.git_root, "alphasystem", "CLAUDE.md"), "w", encoding="utf-8") as handle:
            handle.write("| repo_a | ../repo_a | test |\n")
        origin = helpers.init_repo(
            os.path.join(self.tmp.name, "origin_a"),
            {"conversations.md": "## 2026-09-06 まとめ\n\n本文。\n"},
        )
        helpers.clone_repo(origin, os.path.join(self.git_root, "repo_a"))

        self._orig_lock = cli.LOCK_PATH
        self._orig_log = cli.LOG_PATH
        self._orig_stamp = cli.STAMP_PATH
        cli.LOCK_PATH = os.path.join(self.tmp.name, "cache", "claude_daily_log.lock")
        cli.LOG_PATH = os.path.join(self.tmp.name, "logs", "claude_daily_log.log")
        cli.STAMP_PATH = os.path.join(self.tmp.name, "cache", "claude_daily_log.fetch_stamp")

    def tearDown(self):
        cli.LOCK_PATH = self._orig_lock
        cli.LOG_PATH = self._orig_log
        cli.STAMP_PATH = self._orig_stamp
        self.tmp.cleanup()

    def test_fetch_exception_does_not_block_sync(self):
        original_fetch = cli.gitsync_module.run_fetch

        def explode(*args, **kwargs):
            raise RuntimeError("network exploded")

        cli.gitsync_module.run_fetch = explode
        try:
            code = cli.main([
                "auto", "--force-fetch",
                "--vault", self.vault, "--git-root", self.git_root,
                "--date", "2026-09-06", "--report",
            ])
        finally:
            cli.gitsync_module.run_fetch = original_fetch

        self.assertEqual(code, 0)
        daily_path = os.path.join(self.vault, "01_Daily", "2026-09-06.md")
        self.assertTrue(os.path.exists(daily_path), "fetch が例外を投げると sync が実行されていない")
        with open(daily_path, encoding="utf-8") as handle:
            self.assertIn("まとめ", handle.read())

    def test_fetch_exception_is_reported_as_warning(self):
        original_fetch = cli.gitsync_module.run_fetch

        def explode(*args, **kwargs):
            raise RuntimeError("network exploded")

        cli.gitsync_module.run_fetch = explode
        try:
            report = None
            import io
            import contextlib
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                cli.main([
                    "auto", "--force-fetch",
                    "--vault", self.vault, "--git-root", self.git_root,
                    "--date", "2026-09-06", "--report",
                ])
        finally:
            cli.gitsync_module.run_fetch = original_fetch
        self.assertIn("network exploded", buf.getvalue())


class MainAlwaysReturnsZeroTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._orig_lock = cli.LOCK_PATH
        self._orig_log = cli.LOG_PATH
        self._orig_stamp = cli.STAMP_PATH
        cli.LOCK_PATH = os.path.join(self.tmp.name, "cache", "claude_daily_log.lock")
        cli.LOG_PATH = os.path.join(self.tmp.name, "logs", "claude_daily_log.log")
        cli.STAMP_PATH = os.path.join(self.tmp.name, "cache", "claude_daily_log.fetch_stamp")

    def tearDown(self):
        cli.LOCK_PATH = self._orig_lock
        cli.LOG_PATH = self._orig_log
        cli.STAMP_PATH = self._orig_stamp
        self.tmp.cleanup()

    def test_unexpected_error_still_returns_zero(self):
        original = cli.run_sync

        def explode(*args, **kwargs):
            raise ValueError("boom")

        cli.run_sync = explode
        try:
            with tempfile.TemporaryDirectory() as tmp:
                self.assertEqual(cli.main(["sync", "--vault", tmp, "--git-root", tmp]), 0)
        finally:
            cli.run_sync = original


class FetchDueTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.stamp = os.path.join(self.tmp.name, "stamp")
        self._original = cli.STAMP_PATH
        cli.STAMP_PATH = self.stamp

    def tearDown(self):
        cli.STAMP_PATH = self._original
        self.tmp.cleanup()

    def test_due_when_stamp_missing(self):
        self.assertTrue(cli._fetch_due())

    def test_not_due_right_after_touch(self):
        cli._touch_stamp()
        self.assertFalse(cli._fetch_due())

    def test_due_when_stamp_is_old(self):
        cli._touch_stamp()
        old = time.time() - cli.FETCH_INTERVAL_SECONDS - 1
        os.utime(self.stamp, (old, old))
        self.assertTrue(cli._fetch_due())


if __name__ == "__main__":
    unittest.main()
