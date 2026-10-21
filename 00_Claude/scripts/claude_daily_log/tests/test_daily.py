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


def _status(name, branch, dirty="-", when="-", message="-", linked=True):
    return status.ProjectStatus(
        name=name, branch=branch, dirty=dirty, when=when,
        message=message, linked=linked, failed=False,
    )






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

    def test_does_not_create_worklog_block_when_absent(self):
        # 作業ログはもう「生成」しない（状況表の『最新の記録』列へ統合済み）。
        # 見出し・マーカーが元から無ければ何も作らず、ファイルも書き換わらない。
        self.write("- [ ] 手書きタスク\n")
        changed, status_changed, warnings = daily.update_daily(
            self.vault, "2026-09-06", latest(entry()), ["coopinf"])
        self.assertFalse(changed)
        self.assertFalse(status_changed)
        self.assertEqual(warnings, [])
        text = self.read()
        self.assertEqual(text, "- [ ] 手書きタスク\n")
        self.assertNotIn(daily.SECTION_HEADING, text)

    def test_removes_worklog_block_but_keeps_handwritten_content(self):
        # 作業ログは置き換えではなく削除。latest_entries の内容（新しいタイトル等）が
        # 書き込まれることはない（record 情報は状況表側でのみ描画される）。
        self.write(HANDWRITTEN)
        log_removed, _, warnings = daily.update_daily(
            self.vault, "2026-09-06", latest(entry(title="新")), ["coopinf"])
        self.assertTrue(log_removed)
        self.assertEqual(warnings, [])
        text = self.read()
        self.assertIn("- [ ] 手書きタスク", text)
        self.assertNotIn("2026-09-01 旧", text)
        self.assertNotIn(daily.SECTION_HEADING, text)
        self.assertEqual(text.count("<!-- claude-log:start -->"), 0)

    def test_second_run_with_same_input_reports_no_change(self):
        self.write(HANDWRITTEN)
        daily.update_daily(self.vault, "2026-09-06", latest(entry()), ["coopinf"])
        before = self.read()
        changed, _, _ = daily.update_daily(self.vault, "2026-09-06", latest(entry()), ["coopinf"])
        self.assertFalse(changed)
        self.assertEqual(self.read(), before)

    def test_no_records_at_all_still_removes_worklog(self):
        # NO_ENTRIES_LINE（プレースホルダー行）はもう存在しない。記録が無くても
        # 作業ログは単に削除されるだけで、何も生成されない。
        self.write(HANDWRITTEN)
        log_removed, _, warnings = daily.update_daily(self.vault, "2026-09-06", {}, [])
        self.assertTrue(log_removed)
        self.assertEqual(warnings, [])
        text = self.read()
        self.assertNotIn(daily.SECTION_HEADING, text)
        self.assertIn("- [ ] 手書きタスク", text)


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
    """マーカーが壊れている場合、新仕様では例外を投げず警告を返し、

    手書き内容を巻き込まないためブロックには一切触れない（ファイルは一字一句
    変化しない）。旧実装は DailyMarkerError を投げていたが、これは廃止された。
    """

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

    def assert_warns_and_keeps_file(self, text, expected_in_message):
        self.write(text)
        before = open(self.path, "rb").read()
        log_removed, _, warnings = daily.update_daily(
            self.vault, "2026-09-06", latest(entry()), ["coopinf"])
        self.assertFalse(log_removed)
        self.assertEqual(len(warnings), 1)
        self.assertIn(expected_in_message, warnings[0])
        self.assertEqual(open(self.path, "rb").read(), before)

    def test_end_before_start(self):
        self.assert_warns_and_keeps_file(
            "手書き\n<!-- claude-log:end -->\n中身\n<!-- claude-log:start -->\n", "順序が逆")

    def test_only_start_marker(self):
        self.assert_warns_and_keeps_file(
            "手書き\n<!-- claude-log:start -->\n中身\n", "終了マーカーがありません")

    def test_only_end_marker(self):
        self.assert_warns_and_keeps_file(
            "手書き\n<!-- claude-log:end -->\n中身\n", "開始マーカーがありません")

    def test_duplicated_start_marker(self):
        self.assert_warns_and_keeps_file(
            "<!-- claude-log:start -->\n<!-- claude-log:start -->\n<!-- claude-log:end -->\n", "重複")


class MarkerWhitespaceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = self.tmp.name
        os.makedirs(os.path.join(self.vault, daily.DAILY_DIR))
        self.path = os.path.join(self.vault, daily.daily_relpath("2026-09-06"))

    def tearDown(self):
        self.tmp.cleanup()

    def test_trailing_whitespace_markers_are_recognized_and_removed(self):
        with open(self.path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("手書き\n\n## Claude作業ログ\n\n<!-- claude-log:start --> \n<!-- claude-log:end --> \n")
        log_removed, _, warnings = daily.update_daily(
            self.vault, "2026-09-06", latest(entry()), ["coopinf"])
        self.assertTrue(log_removed)
        self.assertEqual(warnings, [])
        with open(self.path, encoding="utf-8") as handle:
            text = handle.read()
        # 末尾空白付きのマーカーも認識され、見出しごと削除される。
        self.assertEqual(text.count(daily.SECTION_HEADING), 0)
        self.assertNotIn("<!-- claude-log:start -->", text)
        self.assertIn("手書き", text)


MULTI_SOURCE = """- [ ] 手書きタスク
- **coopinf** — outside の同名行（触ってはいけない）

## Claude作業ログ

<!-- claude-log:start -->
- **coopinf** — 2026-09-01 [[00_Claude/projects/coopinf#2026-09-01 旧|旧]]
- **alphasystem** — 2026-08-30 [[00_Claude/projects/alphasystem#2026-08-30 別件|別件]]
<!-- claude-log:end -->
"""




class RenderStatusLinesTest(unittest.TestCase):
    def test_two_tables_with_links_and_timestamp(self):
        statuses = [
            _status("alphasystem", "staging", when="2日前"),
            _status("alphabsmail", "alphasystem内", linked=False),
            _status("coop", "main", dirty="3件", when="1日前"),
        ]
        latest_entries = latest(
            entry(source_id="alphasystem", date="2026-10-20", title="Merge pull request #91"),
            entry(source_id="coop", date="2026-10-19", title="docs: 更新"),
        )
        lines = daily.render_status_lines(statuses, "2026-10-21 08:55", latest_entries=latest_entries)
        text = "\n".join(lines)

        self.assertIn("### alpha", text)
        self.assertIn("### coop", text)
        # 「メッセージ」列は廃止され「最新の記録」列に置き換わった。
        self.assertIn("| プロジェクト | ブランチ | 未コミット | 最終コミット | 最新の記録 |", text)
        self.assertIn(
            r"| [[00_Claude/projects/alphasystem\|alphasystem]] | staging | - | 2日前 | "
            r"2026-10-20 [[00_Claude/projects/alphasystem#2026-10-20 Merge pull request ＃91\|Merge pull request ＃91]] |",
            text,
        )
        # 記録が無いプロジェクトは「最新の記録」列が `-`。
        self.assertIn("| alphabsmail | alphasystem内 | - | - | - |", text)
        self.assertIn(
            r"| [[00_Claude/projects/coop\|coop]] | main | 3件 | 1日前 | "
            r"2026-10-19 [[00_Claude/projects/coop#2026-10-19 docs: 更新\|docs: 更新]] |",
            text,
        )
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


class StatusRowPipeEscapeTest(unittest.TestCase):
    """表のセル内の `|` は必ずエスケープする。

    Obsidian の表では、ウィキリンクのエイリアス区切り `[[path|alias]]` の `|` が
    列区切りとして解釈され、1 行が 6 列に割れてデータが右へずれる。
    """

    def _cells(self, line):
        """エスケープ済みの `\|` を除いて、表の行を列に割る。"""
        return line.replace(r"\|", "\x00").split("|")[1:-1]

    def test_wikilink_alias_pipe_is_escaped(self):
        row = daily._status_row(_status("alphasystem", "staging", when="2日前", message="x"))
        self.assertIn(r"[[00_Claude/projects/alphasystem\|alphasystem]]", row)
        self.assertNotIn("alphasystem|alphasystem", row)

    def test_linked_row_has_exactly_five_cells(self):
        row = daily._status_row(_status("alphasystem", "staging", when="2日前", message="x"))
        self.assertEqual(len(self._cells(row)), 5)

    def test_unlinked_row_has_exactly_five_cells(self):
        row = daily._status_row(_status("alphabsmail", "alphasystem内", linked=False))
        self.assertEqual(len(self._cells(row)), 5)

    def test_pipe_in_branch_name_is_escaped(self):
        row = daily._status_row(_status("x", "feature/a|b", when="1日前", message="m"))
        self.assertEqual(len(self._cells(row)), 5)
        self.assertIn(r"feature/a\|b", row)

    def test_every_rendered_row_has_five_cells(self):
        statuses = [
            _status("alphasystem", "staging", when="2日前", message="Merge pull request #91"),
            _status("alphabsmail", "alphasystem内", linked=False),
            # message は status.collect_status が escape_cell 済みの値を入れる。
            # ここでも実際のパイプラインと同じ形（エスケープ済み）を渡す。
            _status("coop", "main", dirty="3件", when="1日前",
                    message=status.escape_cell("docs: a|b")),
        ]
        for line in daily.render_status_lines(statuses, "2026-10-21 08:55"):
            if line.startswith("|") and not line.startswith("|---"):
                with self.subTest(line=line):
                    self.assertEqual(len(self._cells(line)), 5)


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

    def test_old_worklog_block_is_removed_and_status_remains(self):
        """旧作業ログは見出しごと削除され、状況ブロックだけが残る。"""
        self._write(
            "# メモ\n\n## Claude作業ログ\n\n<!-- claude-log:start -->\n"
            "- **x** — 記録なし\n<!-- claude-log:end -->\n"
        )
        removed, _, warnings = daily.update_daily(
            self.vault, "2026-10-21", {}, project_names=["x"],
            status_lines=["### alpha", "（2026-10-21 08:55 時点）"],
        )
        text = self._read()
        self.assertTrue(removed)
        self.assertEqual(warnings, [])
        self.assertNotIn("## Claude作業ログ", text)
        self.assertNotIn("claude-log:", text)
        self.assertIn("## プロジェクト状況", text)
        self.assertIn("<!-- project-status:start -->", text)
        self.assertIn("# メモ", text)

    def test_handwritten_content_survives_worklog_removal(self):
        self._write(
            "# メモ\n\n- [ ] 手書きタスク\n\n## Claude作業ログ\n\n"
            "<!-- claude-log:start -->\n- **x** — 記録なし\n<!-- claude-log:end -->\n\n"
            "## あとがき\n\n本文。\n"
        )
        daily.update_daily(
            self.vault, "2026-10-21", {}, project_names=["x"],
            status_lines=["### alpha"],
        )
        text = self._read()
        self.assertIn("- [ ] 手書きタスク", text)
        self.assertIn("## あとがき", text)
        self.assertIn("本文。", text)
        self.assertNotIn("## Claude作業ログ", text)

    def test_broken_worklog_markers_warn_and_leave_block_alone(self):
        """作業ログのマーカーが壊れていたら触らず警告のみ（例外は投げない）。"""
        self._write(
            "# メモ\n\n## Claude作業ログ\n\n<!-- claude-log:start -->\nA\n"
            "<!-- claude-log:start -->\nB\n<!-- claude-log:end -->\n"
        )
        removed, _, warnings = daily.update_daily(
            self.vault, "2026-10-21", {}, project_names=[],
            status_lines=["### alpha"],
        )
        text = self._read()
        self.assertFalse(removed)
        self.assertEqual(len(warnings), 1)
        self.assertIn("作業ログの削除を見送りました", warnings[0])
        self.assertIn("<!-- claude-log:start -->", text)
        self.assertIn("A", text)
        self.assertIn("B", text)

    def test_worklog_heading_without_markers_is_also_removed(self):
        self._write("# メモ\n\n## Claude作業ログ\n\n## あとがき\n")
        removed, _, _ = daily.update_daily(
            self.vault, "2026-10-21", {}, project_names=[],
            status_lines=["### alpha"],
        )
        text = self._read()
        self.assertTrue(removed)
        self.assertNotIn("## Claude作業ログ", text)
        self.assertIn("## あとがき", text)

    def test_appended_at_end_when_note_has_no_managed_blocks(self):
        self._write("# メモ\n")
        daily.update_daily(
            self.vault, "2026-10-21", {}, project_names=[],
            status_lines=["### alpha"],
        )
        text = self._read()
        self.assertIn("## プロジェクト状況", text)
        self.assertIn("<!-- project-status:start -->", text)
        self.assertTrue(text.rstrip().endswith("<!-- project-status:end -->"))

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
