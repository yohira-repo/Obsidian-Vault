import os
import tempfile
import unittest

import daily
import sources

HANDWRITTEN = """- [ ] 手書きタスク

## Claude作業ログ

<!-- claude-log:start -->
- **coopinf** — 2026-09-01 [[00_Claude/projects/coopinf#2026-09-01 旧|旧]]
<!-- claude-log:end -->
"""


def entry(source_id="coopinf", title="まとめ", date="2026-09-06", order=0):
    return sources.Entry(
        source_id=source_id, date=date, title=title, body="本文。",
        origin="local", commit_date="", order=order,
    )


def latest(*entries):
    """{source_id: Entry} を作る。"""
    return {item.source_id: item for item in entries}


class RenderTest(unittest.TestCase):
    def test_line_carries_date_and_links_to_mirror_heading(self):
        lines = daily.render_project_lines(
            latest(entry(source_id="alphasystem/alphabsmail", title="Track1 の見直し", date="2026-08-12")),
            ["alphasystem"],
        )
        self.assertEqual(
            lines,
            ["- **alphasystem/alphabsmail** — 2026-08-12 "
             "[[00_Claude/projects/alphasystem-alphabsmail#2026-08-12 Track1 の見直し|Track1 の見直し]]"],
        )

    def test_title_is_sanitized(self):
        line = daily.render_project_lines(latest(entry(title="A|B")), [])[0]
        self.assertNotIn("A|B", line)
        self.assertIn("A｜B", line)

    def test_project_without_record_shows_no_record_line(self):
        lines = daily.render_project_lines({}, ["coopcdeweb"])
        self.assertEqual(lines, ["- **coopcdeweb** — 記録なし"])

    def test_project_is_not_marked_no_record_when_a_source_under_it_has_one(self):
        lines = daily.render_project_lines(
            latest(entry(source_id="alphasystem/alphabsmail", date="2026-08-12")),
            ["alphasystem"],
        )
        self.assertEqual(len(lines), 1)
        self.assertNotIn("記録なし", lines[0])

    def test_no_projects_and_no_records_yields_placeholder(self):
        self.assertEqual(daily.render_project_lines({}, []), [daily.NO_ENTRIES_LINE])


class GroupingTest(unittest.TestCase):
    """alpha グループ → 空行 → coop グループ → 空行 → その他。傘は各グループ先頭。"""

    def test_alpha_group_pins_umbrella_then_subsource_then_rest_then_no_record(self):
        lines = daily.render_project_lines(
            latest(
                entry(source_id="alphacdk", date="2026-08-01"),
                entry(source_id="alphasystem/alphabsmail", date="2026-08-12"),
                entry(source_id="alphasystem", date="2026-09-03"),
            ),
            ["alphacdk", "alphadb", "alphasystem"],
        )
        names = [line.split("**")[1] for line in lines]
        self.assertEqual(names, ["alphasystem", "alphasystem/alphabsmail", "alphacdk", "alphadb"])
        self.assertIn("記録なし", lines[-1])

    def test_coop_group_pins_umbrella_even_without_record(self):
        lines = daily.render_project_lines(
            latest(entry(source_id="coopinf", date="2026-09-06")),
            ["coop", "coopinf"],
        )
        names = [line.split("**")[1] for line in lines]
        self.assertEqual(names, ["coop", "coopinf"])
        self.assertIn("記録なし", lines[0])

    def test_blank_line_separates_alpha_and_coop_groups(self):
        lines = daily.render_project_lines(
            latest(entry(source_id="alphacdk", date="2026-08-01"), entry(source_id="coopinf")),
            ["alphacdk", "coopinf"],
        )
        self.assertEqual(lines[1], "")
        self.assertIn("alphacdk", lines[0])
        self.assertIn("coopinf", lines[2])

    def test_empty_group_leaves_no_stray_blank_line(self):
        lines = daily.render_project_lines(latest(entry(source_id="coopinf")), ["coopinf"])
        self.assertEqual(lines, [line for line in lines if line != ""])

    def test_third_group_follows_a_second_blank_line(self):
        lines = daily.render_project_lines(
            latest(
                entry(source_id="alphacdk", date="2026-08-01"),
                entry(source_id="coopinf"),
                entry(source_id="zebra", date="2026-07-01"),
            ),
            ["alphacdk", "coopinf", "zebra"],
        )
        self.assertEqual(lines.count(""), 2)
        self.assertIn("zebra", lines[-1])


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

    def test_does_not_create_daily_when_missing(self):
        self.assertFalse(daily.update_daily(self.vault, "2026-09-06", latest(entry()), ["coopinf"]))
        self.assertFalse(os.path.exists(self.path))

    def test_appends_block_to_existing_note_without_markers(self):
        self.write("- [ ] 手書きタスク\n")
        self.assertTrue(daily.update_daily(self.vault, "2026-09-06", latest(entry()), ["coopinf"]))
        text = self.read()
        self.assertTrue(text.startswith("- [ ] 手書きタスク"))
        self.assertIn(daily.SECTION_HEADING, text)
        self.assertIn("<!-- claude-log:end -->", text)

    def test_replaces_only_managed_block(self):
        self.write(HANDWRITTEN)
        daily.update_daily(self.vault, "2026-09-06", latest(entry(title="新")), ["coopinf"])
        text = self.read()
        self.assertIn("- [ ] 手書きタスク", text)
        self.assertNotIn("2026-09-01 旧", text)
        self.assertIn("新", text)
        self.assertEqual(text.count("<!-- claude-log:start -->"), 1)

    def test_second_run_with_same_input_reports_no_change(self):
        self.write(HANDWRITTEN)
        daily.update_daily(self.vault, "2026-09-06", latest(entry()), ["coopinf"])
        before = self.read()
        self.assertFalse(daily.update_daily(self.vault, "2026-09-06", latest(entry()), ["coopinf"]))
        self.assertEqual(self.read(), before)

    def test_no_records_at_all_renders_placeholder_line(self):
        self.write(HANDWRITTEN)
        daily.update_daily(self.vault, "2026-09-06", {}, [])
        self.assertIn(daily.NO_ENTRIES_LINE, self.read())


class AtomicWriteTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = self.tmp.name
        os.makedirs(os.path.join(self.vault, daily.DAILY_DIR))
        self.path = os.path.join(self.vault, daily.daily_relpath("2026-09-06"))
        with open(self.path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(HANDWRITTEN)

    def tearDown(self):
        self.tmp.cleanup()

    def test_replace_failure_leaves_existing_file_untouched(self):
        before = open(self.path, "rb").read()
        original_replace = os.replace

        def boom(*args, **kwargs):
            raise OSError("boom")

        os.replace = boom
        try:
            with self.assertRaises(OSError):
                daily.update_daily(self.vault, "2026-09-06", latest(entry(title="新")), ["coopinf"])
        finally:
            os.replace = original_replace
        self.assertEqual(open(self.path, "rb").read(), before)
        leftovers = [
            name for name in os.listdir(os.path.join(self.vault, daily.DAILY_DIR))
            if name != "2026-09-06.md"
        ]
        self.assertEqual(leftovers, [])

    def test_no_temp_file_left_behind_after_successful_write(self):
        daily.update_daily(self.vault, "2026-09-06", latest(entry(title="新")), ["coopinf"])
        names = os.listdir(os.path.join(self.vault, daily.DAILY_DIR))
        self.assertEqual(names, ["2026-09-06.md"])


class MalformedMarkerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = self.tmp.name
        os.makedirs(os.path.join(self.vault, daily.DAILY_DIR))
        self.path = os.path.join(self.vault, daily.daily_relpath("2026-09-06"))

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, text):
        with open(self.path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)

    def assert_raises_and_keeps_file(self, text, expected_in_message):
        self.write(text)
        before = open(self.path, "rb").read()
        with self.assertRaises(daily.DailyMarkerError) as context:
            daily.update_daily(self.vault, "2026-09-06", latest(entry()), ["coopinf"])
        self.assertIn(expected_in_message, str(context.exception))
        self.assertEqual(open(self.path, "rb").read(), before)

    def test_end_before_start(self):
        self.assert_raises_and_keeps_file(
            "手書き\n<!-- claude-log:end -->\n中身\n<!-- claude-log:start -->\n", "順序が逆")

    def test_only_start_marker(self):
        self.assert_raises_and_keeps_file(
            "手書き\n<!-- claude-log:start -->\n中身\n", "終了マーカーがありません")

    def test_only_end_marker(self):
        self.assert_raises_and_keeps_file(
            "手書き\n<!-- claude-log:end -->\n中身\n", "開始マーカーがありません")

    def test_duplicated_start_marker(self):
        self.assert_raises_and_keeps_file(
            "<!-- claude-log:start -->\n<!-- claude-log:start -->\n<!-- claude-log:end -->\n", "重複")


class MarkerWhitespaceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = self.tmp.name
        os.makedirs(os.path.join(self.vault, daily.DAILY_DIR))
        self.path = os.path.join(self.vault, daily.daily_relpath("2026-09-06"))

    def tearDown(self):
        self.tmp.cleanup()

    def test_trailing_whitespace_markers_are_recognized_and_replaced_in_place(self):
        with open(self.path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("手書き\n\n## Claude作業ログ\n\n<!-- claude-log:start --> \n<!-- claude-log:end --> \n")
        daily.update_daily(self.vault, "2026-09-06", latest(entry()), ["coopinf"])
        with open(self.path, encoding="utf-8") as handle:
            text = handle.read()
        self.assertEqual(text.count(daily.SECTION_HEADING), 1)
        self.assertIn("coopinf", text)


if __name__ == "__main__":
    unittest.main()
