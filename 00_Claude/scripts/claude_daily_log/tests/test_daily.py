import os
import tempfile
import unittest

import daily
import sources
import status

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
        changed, _, _ = daily.update_daily(self.vault, "2026-09-06", latest(entry()), ["coopinf"])
        self.assertFalse(changed)
        self.assertFalse(os.path.exists(self.path))

    def test_appends_block_to_existing_note_without_markers(self):
        self.write("- [ ] 手書きタスク\n")
        changed, _, _ = daily.update_daily(self.vault, "2026-09-06", latest(entry()), ["coopinf"])
        self.assertTrue(changed)
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
        changed, _, _ = daily.update_daily(self.vault, "2026-09-06", latest(entry()), ["coopinf"])
        self.assertFalse(changed)
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


MULTI_SOURCE = """- [ ] 手書きタスク
- **coopinf** — outside の同名行（触ってはいけない）

## Claude作業ログ

<!-- claude-log:start -->
- **coopinf** — 2026-09-01 [[00_Claude/projects/coopinf#2026-09-01 旧|旧]]
- **alphasystem** — 2026-08-30 [[00_Claude/projects/alphasystem#2026-08-30 別件|別件]]
<!-- claude-log:end -->
"""


class UpdateDailySourcesTest(unittest.TestCase):
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

    def test_only_target_source_line_changes_others_untouched_exactly(self):
        self.write(MULTI_SOURCE)
        before_lines = MULTI_SOURCE.splitlines()
        changed, warnings = daily.update_daily_sources(
            self.vault, "2026-09-06", latest(entry(source_id="coopinf", title="新"))
        )
        self.assertTrue(changed)
        self.assertEqual(warnings, [])
        after_lines = self.read().splitlines()
        self.assertEqual(len(before_lines), len(after_lines))
        diff_indices = [i for i in range(len(before_lines)) if before_lines[i] != after_lines[i]]
        self.assertEqual(len(diff_indices), 1)
        self.assertTrue(after_lines[diff_indices[0]].startswith("- **coopinf** — "))
        self.assertIn(
            "- **alphasystem** — 2026-08-30 [[00_Claude/projects/alphasystem#2026-08-30 別件|別件]]",
            after_lines,
        )

    def test_missing_source_line_warns_and_does_not_change(self):
        self.write(MULTI_SOURCE)
        before = self.read()
        changed, warnings = daily.update_daily_sources(
            self.vault, "2026-09-06", latest(entry(source_id="coopcdeweb"))
        )
        self.assertFalse(changed)
        self.assertEqual(len(warnings), 1)
        self.assertIn("coopcdeweb", warnings[0])
        self.assertIn("該当行がありません", warnings[0])
        self.assertEqual(self.read(), before)

    def test_second_run_with_same_input_reports_no_change(self):
        self.write(MULTI_SOURCE)
        daily.update_daily_sources(self.vault, "2026-09-06", latest(entry(source_id="coopinf", title="新")))
        before = self.read()
        changed, warnings = daily.update_daily_sources(
            self.vault, "2026-09-06", latest(entry(source_id="coopinf", title="新"))
        )
        self.assertFalse(changed)
        self.assertEqual(warnings, [])
        self.assertEqual(self.read(), before)

    def test_line_with_same_prefix_outside_block_is_untouched(self):
        self.write(MULTI_SOURCE)
        daily.update_daily_sources(self.vault, "2026-09-06", latest(entry(source_id="coopinf", title="新")))
        text = self.read()
        self.assertIn("- **coopinf** — outside の同名行（触ってはいけない）", text)

    def test_malformed_markers_raise(self):
        self.write("手書き\n<!-- claude-log:end -->\n中身\n<!-- claude-log:start -->\n")
        before = open(self.path, "rb").read()
        with self.assertRaises(daily.DailyMarkerError):
            daily.update_daily_sources(self.vault, "2026-09-06", latest(entry(source_id="coopinf")))
        self.assertEqual(open(self.path, "rb").read(), before)

    def test_missing_daily_note_warns_and_reports_no_change(self):
        changed, warnings = daily.update_daily_sources(
            self.vault, "2026-09-07", latest(entry(source_id="coopinf"))
        )
        self.assertFalse(changed)
        self.assertEqual(len(warnings), 1)
        self.assertIn("が存在しません", warnings[0])
        self.assertFalse(os.path.exists(os.path.join(self.vault, daily.daily_relpath("2026-09-07"))))


def _status(name, branch, dirty="-", when="-", message="-", linked=True):
    return status.ProjectStatus(
        name=name, branch=branch, dirty=dirty, when=when,
        message=message, linked=linked, failed=False,
    )


class RenderStatusLinesTest(unittest.TestCase):
    def test_two_tables_with_links_and_timestamp(self):
        statuses = [
            _status("alphasystem", "staging", when="2日前", message="Merge pull request #91"),
            _status("alphabsmail", "alphasystem内", linked=False),
            _status("coop", "main", dirty="3件", when="1日前", message="docs: 更新"),
        ]
        lines = daily.render_status_lines(statuses, "2026-10-21 08:55")
        text = "\n".join(lines)

        self.assertIn("### alpha", text)
        self.assertIn("### coop", text)
        self.assertIn("| プロジェクト | ブランチ | 未コミット | 最終コミット | メッセージ |", text)
        self.assertIn("| [[00_Claude/projects/alphasystem|alphasystem]] | staging | - | 2日前 | Merge pull request #91 |", text)
        self.assertIn("| alphabsmail | alphasystem内 | - | - | - |", text)
        self.assertIn("| [[00_Claude/projects/coop|coop]] | main | 3件 | 1日前 | docs: 更新 |", text)
        self.assertIn("（2026-10-21 08:55 時点）", text)

    def test_alpha_table_comes_before_coop(self):
        statuses = [_status("coop", "main"), _status("alphasystem", "staging")]
        text = "\n".join(daily.render_status_lines(statuses, "2026-10-21 08:55"))
        self.assertLess(text.index("### alpha"), text.index("### coop"))

    def test_umbrella_is_moved_to_the_head_of_its_group(self):
        """傘（alphasystem / coop）だけが先頭固定。以降の順序は入力のまま。"""
        statuses = [
            _status("alphacdk", "main"),
            _status("alphasystem", "staging"),
            _status("alphasyscdk", "main"),
        ]
        text = "\n".join(daily.render_status_lines(statuses, "2026-10-21 08:55"))
        self.assertLess(text.index("|alphasystem]]"), text.index("|alphacdk]]"))
        self.assertLess(text.index("|alphacdk]]"), text.index("|alphasyscdk]]"))

    def test_coop_umbrella_is_moved_to_the_head(self):
        statuses = [_status("coopbatch", "main"), _status("coop", "main")]
        text = "\n".join(daily.render_status_lines(statuses, "2026-10-21 08:55"))
        self.assertLess(text.index("|coop]]"), text.index("|coopbatch]]"))

    def test_empty_group_is_omitted(self):
        text = "\n".join(daily.render_status_lines([_status("coop", "main")], "2026-10-21 08:55"))
        self.assertNotIn("### alpha", text)


class StatusBlockPlacementTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = self.tmp.name
        os.makedirs(os.path.join(self.vault, "01_Daily"))

    def tearDown(self):
        self.tmp.cleanup()

    def _write(self, text):
        path = os.path.join(self.vault, "01_Daily", "2026-10-21.md")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path

    def _read(self):
        with open(os.path.join(self.vault, "01_Daily", "2026-10-21.md"), encoding="utf-8") as handle:
            return handle.read()

    def test_inserted_immediately_before_worklog_heading(self):
        self._write("# メモ\n\n## Claude作業ログ\n\n<!-- claude-log:start -->\n- **x** — 記録なし\n<!-- claude-log:end -->\n")
        daily.update_daily(
            self.vault, "2026-10-21", {}, project_names=["x"],
            status_lines=["### alpha", "（2026-10-21 08:55 時点）"],
        )
        text = self._read()
        self.assertLess(text.index("## プロジェクト状況"), text.index("## Claude作業ログ"))
        self.assertIn("<!-- project-status:start -->", text)

    def test_appended_at_end_when_no_worklog_heading(self):
        # 作業ログ見出しが元から無い場合、0 個マーカーの作業ログ側は従来どおり
        # 末尾に新規作成される（この挙動自体は変えない）。状況ブロックは
        # 「作業ログ見出しの直前」に挿入する同じルールを、既存の見出しか・
        # この呼び出しで新規作成された見出しかを問わず一貫して適用するため、
        # 新規作成された見出しの直前（＝実質ファイル末尾付近）に入る。
        self._write("# メモ\n")
        daily.update_daily(
            self.vault, "2026-10-21", {}, project_names=[],
            status_lines=["### alpha"],
        )
        text = self._read()
        self.assertIn("## プロジェクト状況", text)
        self.assertIn("<!-- project-status:start -->", text)
        self.assertLess(text.index("## プロジェクト状況"), text.index("## Claude作業ログ"))

    def test_second_run_replaces_only_between_markers(self):
        self._write("# メモ\n\n## プロジェクト状況\n\n<!-- project-status:start -->\n古い内容\n<!-- project-status:end -->\n\n## あとがき\n")
        daily.update_daily(
            self.vault, "2026-10-21", {}, project_names=[],
            status_lines=["新しい内容"],
        )
        text = self._read()
        self.assertIn("新しい内容", text)
        self.assertNotIn("古い内容", text)
        self.assertIn("## あとがき", text)
        self.assertEqual(text.count("<!-- project-status:start -->"), 1)

    def test_no_change_reports_false(self):
        self._write("# メモ\n\n## プロジェクト状況\n\n<!-- project-status:start -->\n同じ内容\n<!-- project-status:end -->\n")
        _, status_changed, warnings = daily.update_daily(
            self.vault, "2026-10-21", {}, project_names=[], status_lines=["同じ内容"],
        )
        self.assertFalse(status_changed)
        self.assertEqual(warnings, [])

    def test_broken_status_markers_warn_without_touching_file(self):
        # この fixture には作業ログ側のマーカーが一切無いため、作業ログ側は
        # 既存仕様どおり（このタスクで変えない）末尾に新規作成される。
        # 「状況ブロックに触れない」とは、壊れている状況ブロックの区間自体
        # （マーカーとその中身）が一字一句変化しないことを指し、無関係な
        # 作業ログ側の新規作成まで止める意味ではない
        # （_replace_block の docstring: 「他方のブロックの更新は止めない」）。
        broken_status_block = (
            "<!-- project-status:start -->\nA\n<!-- project-status:start -->\nB\n<!-- project-status:end -->"
        )
        original = "# メモ\n\n%s\n" % broken_status_block
        self._write(original)
        _, status_changed, warnings = daily.update_daily(
            self.vault, "2026-10-21", {}, project_names=[], status_lines=["新"],
        )
        self.assertFalse(status_changed)
        self.assertEqual(len(warnings), 1)
        self.assertIn("プロジェクト状況", warnings[0])
        self.assertIn(broken_status_block, self._read())
        self.assertNotIn("新", self._read())

    def test_timestamp_alone_does_not_rewrite_the_block(self):
        """表の中身が同じなら、時刻行が違ってもブロックを書き換えない。"""
        original = (
            "# メモ\n\n## プロジェクト状況\n\n<!-- project-status:start -->\n"
            "### alpha\n\n| a | b | c | d | e |\n（2026-10-21 08:55 時点）\n"
            "<!-- project-status:end -->\n"
        )
        self._write(original)
        _, status_changed, warnings = daily.update_daily(
            self.vault, "2026-10-21", {}, project_names=[],
            status_lines=["### alpha", "", "| a | b | c | d | e |", "（2026-10-21 09:30 時点）"],
        )
        self.assertFalse(status_changed)
        self.assertIn("08:55", self._read())

    def test_content_change_updates_the_timestamp_too(self):
        original = (
            "# メモ\n\n## プロジェクト状況\n\n<!-- project-status:start -->\n"
            "### alpha\n\n| a | b | c | d | e |\n（2026-10-21 08:55 時点）\n"
            "<!-- project-status:end -->\n"
        )
        self._write(original)
        _, status_changed, _ = daily.update_daily(
            self.vault, "2026-10-21", {}, project_names=[],
            status_lines=["### alpha", "", "| a | X | c | d | e |", "（2026-10-21 09:30 時点）"],
        )
        self.assertTrue(status_changed)
        text = self._read()
        self.assertIn("09:30", text)
        self.assertNotIn("08:55", text)

    def test_status_is_not_touched_when_status_lines_is_none(self):
        original = "# メモ\n\n## Claude作業ログ\n\n<!-- claude-log:start -->\n- **x** — 記録なし\n<!-- claude-log:end -->\n"
        self._write(original)
        daily.update_daily(self.vault, "2026-10-21", {}, project_names=["x"], status_lines=None)
        self.assertNotIn("project-status", self._read())


if __name__ == "__main__":
    unittest.main()
