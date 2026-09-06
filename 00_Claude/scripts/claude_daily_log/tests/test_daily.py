import glob
import os
import tempfile
import unittest

import daily
import sources

HANDWRITTEN = """- [x] 定例：coopbatch

## 社内システム

・MFクラウド連携(着手)
"""


def entry(source_id="coopinf", title="まとめ", date="2026-09-06", order=0):
    return sources.Entry(
        source_id=source_id, date=date, title=title, body="本文。",
        origin="local", commit_date="", order=order,
    )


class RenderTest(unittest.TestCase):
    def test_line_links_to_mirror_heading(self):
        self.assertEqual(
            daily.render_lines([entry(source_id="alphasystem/alphabsmail", title="Track1 の見直し")]),
            ["- **alphasystem/alphabsmail** — "
             "[[00_Claude/projects/alphasystem-alphabsmail#2026-09-06 Track1 の見直し|Track1 の見直し]]"],
        )

    def test_title_is_sanitized(self):
        line = daily.render_lines([entry(title="A|B")])[0]
        self.assertNotIn("A|B", line)
        self.assertIn("A｜B", line)


class UpdateDailyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = self.tmp.name
        os.makedirs(os.path.join(self.vault, daily.DAILY_DIR))
        self.path = os.path.join(self.vault, daily.daily_relpath("2026-09-06"))

    def tearDown(self):
        self.tmp.cleanup()

    def read(self):
        with open(self.path, encoding="utf-8") as handle:
            return handle.read()

    def write(self, text):
        with open(self.path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)

    def test_creates_daily_when_missing(self):
        self.assertTrue(daily.update_daily(self.vault, "2026-09-06", [entry()]))
        self.assertEqual(
            self.read(),
            "## Claude作業ログ\n\n<!-- claude-log:start -->\n"
            "### この日の作業\n"
            "- **coopinf** — [[00_Claude/projects/coopinf#2026-09-06 まとめ|まとめ]]\n"
            "<!-- claude-log:end -->\n",
        )

    def test_does_not_create_empty_daily(self):
        self.assertFalse(daily.update_daily(self.vault, "2026-09-06", []))
        self.assertFalse(os.path.exists(self.path))

    def test_appends_block_to_existing_note_without_markers(self):
        self.write(HANDWRITTEN)
        daily.update_daily(self.vault, "2026-09-06", [entry()])
        text = self.read()
        self.assertTrue(text.startswith(HANDWRITTEN.rstrip("\n")))
        self.assertIn("## Claude作業ログ", text)
        self.assertIn("<!-- claude-log:end -->", text)

    def test_replaces_only_managed_block(self):
        self.write(HANDWRITTEN)
        daily.update_daily(self.vault, "2026-09-06", [entry(title="旧")])
        daily.update_daily(self.vault, "2026-09-06", [entry(title="新")])
        text = self.read()
        self.assertIn(HANDWRITTEN.rstrip("\n"), text)
        self.assertNotIn("旧", text)
        self.assertIn("新", text)
        self.assertEqual(text.count("<!-- claude-log:start -->"), 1)

    def test_empty_entries_clears_block_but_keeps_this_day_heading(self):
        self.write(HANDWRITTEN)
        daily.update_daily(self.vault, "2026-09-06", [entry()])
        daily.update_daily(self.vault, "2026-09-06", [])
        text = self.read()
        self.assertIn("## Claude作業ログ", text)
        self.assertIn(
            "<!-- claude-log:start -->\n### この日の作業\n"
            "- （この日の記録はありません）\n<!-- claude-log:end -->",
            text,
        )

    def test_second_run_with_same_entries_reports_no_change(self):
        daily.update_daily(self.vault, "2026-09-06", [entry()])
        before = self.read()
        self.assertFalse(daily.update_daily(self.vault, "2026-09-06", [entry()]))
        self.assertEqual(self.read(), before)


class LatestSectionTest(unittest.TestCase):
    """各プロジェクトの最新: today モード（latest_entries を渡した場合）のみ出力される。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = self.tmp.name
        os.makedirs(os.path.join(self.vault, daily.DAILY_DIR))
        self.path = os.path.join(self.vault, daily.daily_relpath("2026-09-06"))

    def tearDown(self):
        self.tmp.cleanup()

    def read(self):
        with open(self.path, encoding="utf-8") as handle:
            return handle.read()

    def test_omitted_when_latest_entries_not_passed(self):
        daily.update_daily(self.vault, "2026-09-06", [entry()])
        text = self.read()
        self.assertNotIn("各プロジェクトの最新", text)

    def test_created_even_with_zero_today_entries_when_latest_entries_given(self):
        created = daily.update_daily(
            self.vault, "2026-09-06", [],
            latest_entries={}, project_names=["coopinf"],
        )
        self.assertTrue(created)
        self.assertEqual(
            self.read(),
            "## Claude作業ログ\n\n<!-- claude-log:start -->\n"
            "### この日の作業\n"
            "- （この日の記録はありません）\n\n"
            "### 各プロジェクトの最新\n"
            "- **coopinf** — 記録なし\n"
            "<!-- claude-log:end -->\n",
        )

    def test_records_come_first_ordered_by_date_desc_then_source_id_asc(self):
        latest_entries = {
            "coopinf": entry(source_id="coopinf", title="コop最新", date="2026-09-06"),
            "coopbatch": entry(source_id="coopbatch", title="バッチ最新", date="2026-09-02"),
            "alphasystem": entry(source_id="alphasystem", title="アルファ最新", date="2026-09-06"),
        }
        daily.update_daily(
            self.vault, "2026-09-06", [],
            latest_entries=latest_entries,
            project_names=["coopinf", "coopbatch", "alphasystem", "coopcdeweb"],
        )
        text = self.read()
        lines = text.splitlines()
        start = lines.index("### 各プロジェクトの最新") + 1
        latest_lines = []
        for line in lines[start:]:
            if line.strip() == daily.END_MARKER:
                break
            latest_lines.append(line)
        self.assertEqual(
            latest_lines,
            [
                "- **alphasystem** — 2026-09-06 "
                "[[00_Claude/projects/alphasystem#2026-09-06 アルファ最新|アルファ最新]]",
                "- **coopinf** — 2026-09-06 [[00_Claude/projects/coopinf#2026-09-06 コop最新|コop最新]]",
                "- **coopbatch** — 2026-09-02 "
                "[[00_Claude/projects/coopbatch#2026-09-02 バッチ最新|バッチ最新]]",
                "- **coopcdeweb** — 記録なし",
            ],
        )

    def test_project_with_no_records_at_all_shows_no_record_line(self):
        daily.update_daily(
            self.vault, "2026-09-06", [],
            latest_entries={"coopinf": entry(source_id="coopinf")},
            project_names=["coopinf", "coopcdeweb"],
        )
        text = self.read()
        self.assertIn("- **coopcdeweb** — 記録なし", text)

    def test_project_with_a_source_under_it_is_not_marked_no_record(self):
        # alphasystem/alphabsmail という別ソースがあれば、alphasystem 自体は「記録なし」にならない
        daily.update_daily(
            self.vault, "2026-09-06", [],
            latest_entries={"alphasystem/alphabsmail": entry(source_id="alphasystem/alphabsmail")},
            project_names=["alphasystem"],
        )
        text = self.read()
        self.assertNotIn("alphasystem** — 記録なし", text)
        self.assertIn("**alphasystem/alphabsmail** —", text)


class AtomicWriteTest(unittest.TestCase):
    """ブロッカー B: 書き込み失敗時に既存ファイルを空・破損状態にしない。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = self.tmp.name
        os.makedirs(os.path.join(self.vault, daily.DAILY_DIR))
        self.path = os.path.join(self.vault, daily.daily_relpath("2026-09-06"))

    def tearDown(self):
        self.tmp.cleanup()

    def read(self):
        with open(self.path, encoding="utf-8") as handle:
            return handle.read()

    def test_replace_failure_leaves_existing_file_untouched(self):
        daily.update_daily(self.vault, "2026-09-06", [entry(title="旧")])
        before = self.read()
        self.assertTrue(before)  # 前提: 何か書かれている

        real_replace = os.replace

        def boom(src, dst):
            raise OSError("simulated crash during replace")

        os.replace = boom
        try:
            with self.assertRaises(OSError):
                daily.update_daily(self.vault, "2026-09-06", [entry(title="新")])
        finally:
            os.replace = real_replace

        # 既存の内容が失われていない（空になったり途中で切れたりしない）こと
        self.assertEqual(self.read(), before)

    def test_no_temp_file_left_behind_after_successful_write(self):
        daily.update_daily(self.vault, "2026-09-06", [entry()])
        leftovers = glob.glob(os.path.join(self.vault, daily.DAILY_DIR, ".tmp-*"))
        self.assertEqual(leftovers, [])


class MalformedMarkerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = self.tmp.name
        os.makedirs(os.path.join(self.vault, daily.DAILY_DIR))
        self.path = os.path.join(self.vault, daily.daily_relpath("2026-09-06"))

    def tearDown(self):
        self.tmp.cleanup()

    def read(self):
        with open(self.path, encoding="utf-8") as handle:
            return handle.read()

    def write(self, text):
        with open(self.path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)

    def test_end_before_start_raises_error_without_modifying_file(self):
        malformed = "some text\n<!-- claude-log:end -->\n<!-- claude-log:start -->\nmore text\n"
        self.write(malformed)
        before = self.read()
        with self.assertRaises(daily.DailyMarkerError) as ctx:
            daily.update_daily(self.vault, "2026-09-06", [entry()])
        self.assertEqual(self.read(), before)
        # item H: 「マーカーの個数」だけでは正常に見えてしまうため、順序が逆であることを明示する
        message = str(ctx.exception)
        self.assertIn("順序", message)
        self.assertNotIn("重複", message)

    def test_only_start_marker_raises_error_without_modifying_file(self):
        malformed = "some text\n<!-- claude-log:start -->\nmore text\n"
        self.write(malformed)
        before = self.read()
        with self.assertRaises(daily.DailyMarkerError) as ctx:
            daily.update_daily(self.vault, "2026-09-06", [entry()])
        self.assertEqual(self.read(), before)
        message = str(ctx.exception)
        self.assertIn("終了マーカーがありません", message)

    def test_only_end_marker_raises_error_without_modifying_file(self):
        malformed = "some text\n<!-- claude-log:end -->\nmore text\n"
        self.write(malformed)
        before = self.read()
        with self.assertRaises(daily.DailyMarkerError) as ctx:
            daily.update_daily(self.vault, "2026-09-06", [entry()])
        self.assertEqual(self.read(), before)
        message = str(ctx.exception)
        self.assertIn("開始マーカーがありません", message)

    def test_duplicated_start_marker_raises_error_without_modifying_file(self):
        malformed = "<!-- claude-log:start -->\ntext\n<!-- claude-log:start -->\n<!-- claude-log:end -->\n"
        self.write(malformed)
        before = self.read()
        with self.assertRaises(daily.DailyMarkerError) as ctx:
            daily.update_daily(self.vault, "2026-09-06", [entry()])
        self.assertEqual(self.read(), before)
        message = str(ctx.exception)
        self.assertIn("重複", message)


class MarkerWhitespaceTest(unittest.TestCase):
    """item K: 末尾に空白が付いたマーカーも正常なマーカーとして認識する。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = self.tmp.name
        os.makedirs(os.path.join(self.vault, daily.DAILY_DIR))
        self.path = os.path.join(self.vault, daily.daily_relpath("2026-09-06"))

    def tearDown(self):
        self.tmp.cleanup()

    def read(self):
        with open(self.path, encoding="utf-8") as handle:
            return handle.read()

    def write(self, text):
        with open(self.path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)

    def test_trailing_whitespace_markers_are_recognized_and_replaced_in_place(self):
        self.write(
            "## Claude作業ログ\n\n<!-- claude-log:start --> \n"
            "- 旧い行\n"
            "<!-- claude-log:end --> \n"
        )
        daily.update_daily(self.vault, "2026-09-06", [entry(title="新")])
        text = self.read()
        # 新しい 1 つのブロックだけが残り、重複ブロックが追記されていないこと
        self.assertEqual(text.count("claude-log:start"), 1)
        self.assertEqual(text.count("claude-log:end"), 1)
        self.assertEqual(text.count("## Claude作業ログ"), 1)
        self.assertNotIn("旧い行", text)
        self.assertIn("新", text)


if __name__ == "__main__":
    unittest.main()
