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

    def test_daily_files_are_accepted(self):
        self.assertTrue(sources.is_conversations_path("docs/conversations/2026-10-20.md"))
        self.assertTrue(sources.is_conversations_path("conversations/2026-10-20.md"))
        self.assertTrue(sources.is_conversations_path("alphabsmail/docs/conversations/2026-10-20.md"))

    def test_non_daily_files_in_conversations_dir_are_rejected(self):
        self.assertFalse(sources.is_conversations_path("docs/conversations/README.md"))
        self.assertFalse(sources.is_conversations_path("docs/conversations/2026-10-20.txt"))
        self.assertFalse(sources.is_conversations_path("docs/conversations/2026-10-20-memo.md"))
        self.assertFalse(sources.is_conversations_path("docs/other/2026-10-20.md"))
        self.assertFalse(sources.is_conversations_path("node_modules/x/conversations/2026-10-20.md"))

    def test_source_id_for_daily_files_drops_conversations_dir(self):
        self.assertEqual(
            sources.source_id_from("alphasystem", "docs/conversations/2026-10-20.md"), "alphasystem"
        )
        self.assertEqual(
            sources.source_id_from("alphadb", "conversations/2026-10-20.md"), "alphadb"
        )
        self.assertEqual(
            sources.source_id_from("alphasystem", "alphabsmail/docs/conversations/2026-10-20.md"),
            "alphasystem/alphabsmail",
        )


class DailyFilesCollectTest(unittest.TestCase):
    """日付別ファイルと旧 conversations.md の併存を収集できる。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        origin = helpers.init_repo(
            os.path.join(self.tmp.name, "origin"),
            {
                "docs/conversations.md": "# 履歴\n\n## 2026-10-19 旧方式のまとめ\n\n旧の本文。\n",
                "docs/conversations/2026-10-20.md": (
                    "## 2026-10-20 新方式の1件目\n\n本文1。\n\n## 2026-10-20 新方式の2件目\n\n本文2。\n"
                ),
                "docs/conversations/2026-10-21.md": "## 2026-10-21 翌日のまとめ\n\n本文3。\n",
                "alphabsmail/docs/conversations/2026-10-20.md": "## 2026-10-20 サブのまとめ\n\nサブ本文。\n",
            },
        )
        self.repo = helpers.clone_repo(origin, os.path.join(self.tmp.name, "work"))

    def tearDown(self):
        self.tmp.cleanup()

    def test_collects_old_and_daily_files_together(self):
        entries, _ = sources.collect_entries(self.repo, "alphasystem")
        found = sorted((e.source_id, e.date, e.title) for e in sources.dedupe(entries))
        self.assertEqual(
            found,
            [
                ("alphasystem", "2026-10-19", "旧方式のまとめ"),
                ("alphasystem", "2026-10-20", "新方式の1件目"),
                ("alphasystem", "2026-10-20", "新方式の2件目"),
                ("alphasystem", "2026-10-21", "翌日のまとめ"),
                ("alphasystem/alphabsmail", "2026-10-20", "サブのまとめ"),
            ],
        )

    def test_target_date_selects_that_days_file(self):
        entries, _ = sources.collect_entries(self.repo, "alphasystem", "2026-10-20")
        titles = sorted(e.title for e in sources.dedupe(entries))
        self.assertEqual(titles, ["サブのまとめ", "新方式の1件目", "新方式の2件目"])


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

    def test_none_target_date_returns_every_dated_entry(self):
        entries, _ = sources.collect_entries(self.repo, "alphasystem", target_date=None)
        titles = sorted(entry.title for entry in sources.dedupe(entries))
        self.assertEqual(
            titles,
            sorted(["docs 配下のまとめ", "前日のまとめ", "直下のまとめ", "サブプロジェクトのまとめ"]),
        )

    def test_default_target_date_is_none(self):
        # 引数省略時も全期間を返す（target_date のデフォルトは None）
        entries_default, _ = sources.collect_entries(self.repo, "alphasystem")
        entries_explicit, _ = sources.collect_entries(self.repo, "alphasystem", None)
        self.assertEqual(
            sorted(e.title for e in entries_default),
            sorted(e.title for e in entries_explicit),
        )

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


def _local_entry(title, body, order):
    return sources.Entry(
        source_id="coopinf", date="2026-09-06", title=title, body=body,
        origin="local", commit_date="", order=order,
    )


class DedupeTieBreakTest(unittest.TestCase):
    """item J: rank が同点の場合、ファイル内で後に出現した方（order が大きい方）を残す。"""

    def test_tie_on_rank_prefers_later_order_not_silently_dropping_it(self):
        entries = [
            _local_entry("T", "先に出てくる本文", order=0),
            _local_entry("T", "後から出てくる本文", order=1),
        ]
        result = sources.dedupe(entries)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].body, "後から出てくる本文")

    def test_tie_is_order_independent_of_input_list_order(self):
        # 入力の並びを逆にしても、常に order の大きい方（ファイル内で後）が勝つ
        entries = [
            _local_entry("T", "後から出てくる本文", order=1),
            _local_entry("T", "先に出てくる本文", order=0),
        ]
        result = sources.dedupe(entries)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].body, "後から出てくる本文")


class DedupeSanitizedTitleKeyTest(unittest.TestCase):
    """item M: サニタイズ後のタイトルで重複排除する（表記ゆれの取りこぼしを防ぐ）。"""

    def test_titles_that_sanitize_to_same_string_are_deduped(self):
        entries = [
            _local_entry("A#B", "旧本文", order=0),
            _local_entry("A＃B", "新本文", order=1),
        ]
        result = sources.dedupe(entries)
        self.assertEqual(len(result), 1, "サニタイズ後に同じ文字列になるタイトルは重複排除されるべき")
        # J のタイブレークにより、同点なら order の大きい方（後の方）が残る
        self.assertEqual(result[0].body, "新本文")


if __name__ == "__main__":
    unittest.main()
