import os
import tempfile
import unittest

import sources
from tests import helpers


CONV_ROOT = """# 会話ログ

## 2026-09-06 直下のまとめ

直下の本文。

## 2026-09-05 前日のまとめ

前日の本文。
"""

CONV_DOCS = """# 会話記録

## 2026-09-06 docs 配下のまとめ

docs の本文。
"""

CONV_SUB = """# conversations

## 2026-09-06 サブプロジェクトのまとめ

サブの本文。

## 日付なし見出し

無視される本文。
"""


class PathRuleTest(unittest.TestCase):
    def test_only_conversations_md_is_accepted(self):
        self.assertTrue(sources.is_conversations_path("conversations.md"))
        self.assertTrue(sources.is_conversations_path("docs/conversations.md"))
        self.assertFalse(sources.is_conversations_path("docs/conversation.md"))
        self.assertFalse(sources.is_conversations_path("README.md"))

    def test_excluded_directories_are_rejected(self):
        self.assertFalse(sources.is_conversations_path("node_modules/x/conversations.md"))
        self.assertFalse(sources.is_conversations_path("dist/conversations.md"))

    def test_source_id_drops_docs_segment(self):
        self.assertEqual(sources.source_id_from("coopinf", "conversations.md"), "coopinf")
        self.assertEqual(sources.source_id_from("alphasystem", "docs/conversations.md"), "alphasystem")
        self.assertEqual(
            sources.source_id_from("alphasystem", "alphabsmail/docs/conversations.md"),
            "alphasystem/alphabsmail",
        )


class CollectEntriesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.origin = helpers.init_repo(
            os.path.join(self.tmp.name, "origin"),
            {
                "conversations.md": CONV_ROOT,
                "docs/conversations.md": CONV_DOCS,
                "alphabsmail/docs/conversations.md": CONV_SUB,
                "node_modules/pkg/conversations.md": CONV_ROOT,
            },
        )
        self.repo = helpers.clone_repo(self.origin, os.path.join(self.tmp.name, "work"))

    def tearDown(self):
        self.tmp.cleanup()

    def test_finds_conversations_at_any_depth(self):
        entries, _ = sources.collect_entries(self.repo, "alphasystem", "2026-09-06")
        self.assertEqual(
            sorted({entry.source_id for entry in entries}),
            ["alphasystem", "alphasystem/alphabsmail"],
        )

    def test_target_date_filters_sections(self):
        entries, _ = sources.collect_entries(self.repo, "alphasystem", "2026-09-05")
        self.assertEqual([entry.title for entry in sources.dedupe(entries)], ["前日のまとめ"])

    def test_undated_heading_is_reported_once(self):
        _, warnings = sources.collect_entries(self.repo, "alphasystem", "2026-09-06")
        matched = [w for w in warnings if "日付なし見出し" in w]
        self.assertEqual(len(matched), 1)
        self.assertIn("alphabsmail/docs/conversations.md", matched[0])

    def test_remote_branch_content_is_collected(self):
        helpers.commit_on_branch(
            self.origin,
            "feature/new",
            {"conversations.md": CONV_ROOT + "\n## 2026-09-06 ブランチ限定のまとめ\n\nブランチ本文。\n"},
        )
        helpers.git(self.repo, "fetch", "--quiet", "origin")
        entries = sources.dedupe(sources.collect_entries(self.repo, "alphasystem", "2026-09-06")[0])
        self.assertIn("ブランチ限定のまとめ", [entry.title for entry in entries])

    def test_local_worktree_wins_over_remote(self):
        helpers.write(self.repo, "conversations.md",
                      "## 2026-09-06 直下のまとめ\n\nローカルで書き足した本文。\n")
        entries = sources.dedupe(sources.collect_entries(self.repo, "alphasystem", "2026-09-06")[0])
        found = [entry for entry in entries if entry.title == "直下のまとめ"]
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].body, "ローカルで書き足した本文。")

    def test_untracked_local_file_is_collected(self):
        helpers.write(self.repo, "sub/docs/conversations.md",
                      "## 2026-09-06 未追跡ファイルのまとめ\n\n未追跡の本文。\n")
        entries = sources.dedupe(sources.collect_entries(self.repo, "alphasystem", "2026-09-06")[0])
        self.assertIn("alphasystem/sub", [entry.source_id for entry in entries])

    def test_repository_without_conversations_returns_empty(self):
        plain = helpers.init_repo(os.path.join(self.tmp.name, "plain"), {"README.md": "x"})
        entries, warnings = sources.collect_entries(plain, "plain", "2026-09-06")
        self.assertEqual(entries, [])
        self.assertEqual(warnings, [])

    def test_broken_repository_raises_git_command_error(self):
        broken = os.path.join(self.tmp.name, "broken")
        os.makedirs(broken)
        with self.assertRaises(sources.GitCommandError):
            sources.collect_entries(broken, "broken", "2026-09-06")


if __name__ == "__main__":
    unittest.main()
