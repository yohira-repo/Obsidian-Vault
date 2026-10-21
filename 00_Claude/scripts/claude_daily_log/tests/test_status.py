import os
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import projects
import status
from tests import helpers


class JapanizeRelativeTest(unittest.TestCase):
    def test_singular_and_plural_units(self):
        cases = [
            ("1 second ago", "1秒前"),
            ("30 seconds ago", "30秒前"),
            ("5 minutes ago", "5分前"),
            ("2 hours ago", "2時間前"),
            ("1 day ago", "1日前"),
            ("3 weeks ago", "3週間前"),
            ("4 months ago", "4か月前"),
            ("2 years ago", "2年前"),
        ]
        for source, expected in cases:
            with self.subTest(source=source):
                self.assertEqual(status.japanize_relative(source), expected)

    def test_compound_years_and_months(self):
        self.assertEqual(status.japanize_relative("2 years, 3 months ago"), "2年3か月前")

    def test_unknown_text_is_returned_unchanged(self):
        self.assertEqual(status.japanize_relative("right now"), "right now")

    def test_empty_becomes_dash(self):
        self.assertEqual(status.japanize_relative(""), "")


class TruncateAndEscapeTest(unittest.TestCase):
    def test_subject_at_limit_is_not_truncated(self):
        text = "あ" * 40
        self.assertEqual(status.truncate_subject(text), text)

    def test_subject_over_limit_gets_ellipsis(self):
        text = "あ" * 41
        result = status.truncate_subject(text)
        self.assertEqual(result, "あ" * 40 + "…")

    def test_pipe_is_escaped(self):
        self.assertEqual(status.escape_cell("feat: a|b"), r"feat: a\|b")


class CollectStatusTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def _project(self, name, kind=projects.KIND_REPO, path=None):
        return projects.Project(
            name=name,
            path=path if path is not None else os.path.join(self.root, name),
            kind=kind,
        )

    def test_missing_directory_is_reported_as_not_cloned(self):
        result = status.collect_status(self._project("nope"))
        self.assertEqual(result.branch, "未clone")
        self.assertEqual(result.dirty, "-")
        self.assertEqual(result.when, "-")
        self.assertEqual(result.message, "-")

    def test_non_git_directory_is_reported(self):
        os.makedirs(os.path.join(self.root, "plain"))
        result = status.collect_status(self._project("plain"))
        self.assertEqual(result.branch, "（git管理外）")

    def test_nested_project_is_reported_without_link(self):
        path = os.path.join(self.root, "alphasystem", "alphabsmail")
        os.makedirs(path)
        result = status.collect_status(self._project("alphabsmail", projects.KIND_NESTED, path))
        self.assertEqual(result.branch, "alphasystem内")
        self.assertFalse(result.linked)
        self.assertEqual(result.dirty, "-")

    def test_clean_repo_on_main(self):
        helpers.init_repo(os.path.join(self.root, "repo"), {"a.txt": "a"}, branch="main", message="init commit")
        result = status.collect_status(self._project("repo"))
        self.assertEqual(result.branch, "main")
        self.assertEqual(result.dirty, "-")
        self.assertEqual(result.message, "init commit")
        self.assertTrue(result.linked)
        self.assertFalse(result.failed)

    def test_dirty_count_is_rendered_with_suffix(self):
        repo = helpers.init_repo(os.path.join(self.root, "repo"), {"a.txt": "a"}, branch="main")
        helpers.write(repo, "b.txt", "b")
        helpers.write(repo, "c.txt", "c")
        result = status.collect_status(self._project("repo"))
        self.assertEqual(result.dirty, "2件")

    def test_feature_branch_without_upstream_is_marked_unpushed(self):
        repo = helpers.init_repo(os.path.join(self.root, "repo"), {"a.txt": "a"}, branch="main")
        helpers.git(repo, "checkout", "-q", "-b", "feature/x")
        result = status.collect_status(self._project("repo"))
        self.assertEqual(result.branch, "feature/x (未push)")

    def test_staging_without_upstream_is_not_marked(self):
        helpers.init_repo(os.path.join(self.root, "repo"), {"a.txt": "a"}, branch="staging")
        result = status.collect_status(self._project("repo"))
        self.assertEqual(result.branch, "staging")

    def test_deleted_upstream_is_flagged(self):
        origin = helpers.init_repo(os.path.join(self.root, "origin"), {"a.txt": "a"}, branch="main")
        helpers.git(origin, "checkout", "-q", "-b", "feature/gone")
        helpers.git(origin, "commit", "-q", "--allow-empty", "-m", "x")
        clone = helpers.clone_repo(origin, os.path.join(self.root, "repo"))
        # 注: ローカルパスからの clone は origin の「現在チェックアウト中のブランチ」を
        # そのまま初期チェックアウトし、同名ブランチで追跡設定も済ませる。
        # そのため origin の HEAD が feature/gone のこの時点では、
        # clone 側は既に feature/gone を origin/feature/gone 追跡でチェックアウト済みであり、
        # 同名での `git checkout -b` は「ブランチが既に存在する」エラーになるため不要。
        helpers.git(origin, "checkout", "-q", "main")
        helpers.git(origin, "branch", "-D", "feature/gone")
        helpers.git(clone, "fetch", "--quiet", "--prune", "origin")
        result = status.collect_status(self._project("repo", path=clone))
        self.assertEqual(result.branch, "feature/gone ⚠upstream消失")

    def test_detached_head_shows_short_hash(self):
        repo = helpers.init_repo(os.path.join(self.root, "repo"), {"a.txt": "a"}, branch="main")
        head = subprocess.run(
            ["git", "-C", repo, "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        helpers.git(repo, "checkout", "-q", "--detach")
        result = status.collect_status(self._project("repo"))
        self.assertEqual(result.branch, "(detached %s)" % head)

    def test_long_subject_is_truncated(self):
        subject = "あ" * 50
        helpers.init_repo(os.path.join(self.root, "repo"), {"a.txt": "a"}, branch="main", message=subject)
        result = status.collect_status(self._project("repo"))
        self.assertEqual(result.message, "あ" * 40 + "…")

    def test_pipe_in_subject_is_escaped(self):
        helpers.init_repo(os.path.join(self.root, "repo"), {"a.txt": "a"}, branch="main", message="feat: a|b")
        result = status.collect_status(self._project("repo"))
        self.assertEqual(result.message, r"feat: a\|b")

    def test_branch_label_failure_short_circuits_other_columns(self):
        helpers.init_repo(os.path.join(self.root, "repo"), {"a.txt": "a"}, branch="main")
        real_git = status._git

        def fake_git(path, *args):
            if args == ("branch", "--show-current"):
                return None
            return real_git(path, *args)

        with patch.object(status, "_git", side_effect=fake_git):
            result = status.collect_status(self._project("repo"))
        self.assertEqual(result.branch, status.FAILED_LABEL)
        self.assertEqual(result.dirty, "-")
        self.assertEqual(result.when, "-")
        self.assertEqual(result.message, "-")
        self.assertTrue(result.failed)


class CollectAllTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def test_order_is_preserved_and_failure_is_localized(self):
        helpers.init_repo(os.path.join(self.root, "ok"), {"a.txt": "a"}, branch="main", message="init")
        items = [
            projects.Project(name="ok", path=os.path.join(self.root, "ok")),
            projects.Project(name="gone", path=os.path.join(self.root, "gone")),
        ]
        results = status.collect_all(items)
        self.assertEqual([r.name for r in results], ["ok", "gone"])
        self.assertEqual(results[1].branch, "未clone")


if __name__ == "__main__":
    unittest.main()
