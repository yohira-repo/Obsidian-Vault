import unittest

import sections


SAMPLE = """# 会話ログ

## 2026-07-22 CSVバッチ処理のログ出力見直し（提案）

空白区切りの本文。

## 2026-08-20: gas_bill 埋め戻し

コロン区切りの本文。
2行目。

## 2026-08-12 — 営業メールの可視化

em ダッシュ区切りの本文。

## 経営層向け説明資料の作成

日付なしの本文。

## 2026-09-06 まとめ

最後の本文。
"""


class ParseSectionsTest(unittest.TestCase):
    def test_three_heading_formats_are_parsed(self):
        parsed, _ = sections.parse_sections(SAMPLE)
        self.assertEqual(
            [(s.date, s.title) for s in parsed],
            [
                ("2026-07-22", "CSVバッチ処理のログ出力見直し（提案）"),
                ("2026-08-20", "gas_bill 埋め戻し"),
                ("2026-08-12", "営業メールの可視化"),
                ("2026-09-06", "まとめ"),
            ],
        )

    def test_undated_heading_is_counted_and_skipped(self):
        parsed, undated = sections.parse_sections(SAMPLE)
        self.assertEqual(undated, 1)
        self.assertNotIn("経営層向け説明資料の作成", [s.title for s in parsed])

    def test_body_stops_before_next_heading(self):
        parsed, _ = sections.parse_sections(SAMPLE)
        self.assertEqual(parsed[1].body, "コロン区切りの本文。\n2行目。")

    def test_last_body_reaches_end_of_text(self):
        parsed, _ = sections.parse_sections(SAMPLE)
        self.assertEqual(parsed[3].body, "最後の本文。")

    def test_order_is_assigned_to_dated_sections_only(self):
        parsed, _ = sections.parse_sections(SAMPLE)
        self.assertEqual([s.order for s in parsed], [0, 1, 2, 3])

    def test_no_heading_returns_empty(self):
        parsed, undated = sections.parse_sections("本文だけのファイル\n")
        self.assertEqual(parsed, [])
        self.assertEqual(undated, 0)


class ScanHeadingsTest(unittest.TestCase):
    def test_returns_line_numbers_with_date_and_title(self):
        lines = ["# タイトル", "## 2026-09-06 A", "本文", "## 日付なし", "本文"]
        self.assertEqual(
            sections.scan_headings(lines),
            [(1, "2026-09-06", "A"), (3, None, None)],
        )


class RangeHeadingTest(unittest.TestCase):
    def test_day_only_end_is_resolved_within_same_month(self):
        lines = ["## 2026-08-28〜31 ステージング環境の作り直しと、そこで見つかった10件の不具合"]
        self.assertEqual(
            sections.scan_headings(lines),
            [(0, "2026-08-31", "ステージング環境の作り直しと、そこで見つかった10件の不具合")],
        )

    def test_month_day_end_is_resolved_across_month_boundary(self):
        lines = ["## 2026-08-31〜09-01 現行システムからのデータ移行（ステージングで完走）"]
        self.assertEqual(
            sections.scan_headings(lines),
            [(0, "2026-09-01", "現行システムからのデータ移行（ステージングで完走）")],
        )

    def test_month_day_end_before_start_rolls_over_to_next_year(self):
        lines = ["## 2026-12-30〜01-02 年末年始の作業"]
        self.assertEqual(
            sections.scan_headings(lines),
            [(0, "2027-01-02", "年末年始の作業")],
        )

    def test_fully_specified_end_date_with_year_is_accepted(self):
        lines = ["## 2026-12-30〜2027-01-02 年末年始の作業"]
        self.assertEqual(
            sections.scan_headings(lines),
            [(0, "2027-01-02", "年末年始の作業")],
        )

    def test_invalid_end_date_falls_back_to_start_date(self):
        lines = ["## 2026-08-28〜99 タイトル"]
        self.assertEqual(
            sections.scan_headings(lines),
            [(0, "2026-08-28", "タイトル")],
        )

    def test_half_width_tilde_separator_is_accepted(self):
        lines = ["## 2026-08-28~31 タイトル"]
        self.assertEqual(
            sections.scan_headings(lines),
            [(0, "2026-08-31", "タイトル")],
        )

    def test_day_only_end_before_start_rolls_over_to_next_month(self):
        lines = ["## 2026-08-31〜01 タイトル"]
        self.assertEqual(
            sections.scan_headings(lines),
            [(0, "2026-09-01", "タイトル")],
        )

    def test_day_only_end_before_start_rolls_over_december_to_january(self):
        lines = ["## 2026-12-31〜02 タイトル"]
        self.assertEqual(
            sections.scan_headings(lines),
            [(0, "2027-01-02", "タイトル")],
        )

    def test_day_only_rolled_month_with_invalid_date_falls_back_to_start_date(self):
        lines = ["## 2026-01-31〜30 タイトル"]
        self.assertEqual(
            sections.scan_headings(lines),
            [(0, "2026-01-31", "タイトル")],
        )


class FenceAwareScanHeadingsTest(unittest.TestCase):
    """item G: フェンスコードブロック内の `## ` はセクション見出しとして扱わない。"""

    def test_heading_like_line_inside_backtick_fence_is_ignored(self):
        lines = [
            "## 2026-09-06 タイトル",
            "",
            "```",
            "## これはコードの中の見出し風テキスト",
            "```",
            "",
            "本文の続き",
        ]
        self.assertEqual(
            sections.scan_headings(lines),
            [(0, "2026-09-06", "タイトル")],
        )

    def test_heading_like_line_inside_tilde_fence_is_ignored(self):
        lines = [
            "## 2026-09-06 タイトル",
            "~~~",
            "## フェンス内の見出し風",
            "~~~",
        ]
        self.assertEqual(
            sections.scan_headings(lines),
            [(0, "2026-09-06", "タイトル")],
        )

    def test_fence_with_info_string_is_recognized_as_opening(self):
        lines = [
            "## 2026-09-06 タイトル",
            "```python",
            "## コメント",
            "```",
        ]
        self.assertEqual(
            sections.scan_headings(lines),
            [(0, "2026-09-06", "タイトル")],
        )

    def test_shorter_inner_fence_does_not_close_longer_outer_fence(self):
        lines = [
            "## 2026-09-06 タイトル",
            "````",
            "```",
            "## まだフェンスの中",
            "```",
            "````",
            "## 2026-09-05 次の見出し",
        ]
        self.assertEqual(
            sections.scan_headings(lines),
            [(0, "2026-09-06", "タイトル"), (6, "2026-09-05", "次の見出し")],
        )

    def test_parse_sections_keeps_fenced_heading_like_line_in_body(self):
        text = (
            "## 2026-09-06 タイトル\n"
            "\n"
            "本文開始。\n"
            "\n"
            "```\n"
            "## フェンス内\n"
            "```\n"
            "\n"
            "本文終わり。\n"
        )
        parsed, undated = sections.parse_sections(text)
        self.assertEqual(undated, 0)
        self.assertEqual(len(parsed), 1)
        self.assertIn("## フェンス内", parsed[0].body)
        self.assertIn("本文終わり。", parsed[0].body)


class InvalidStartDateTest(unittest.TestCase):
    def test_plain_heading_with_invalid_calendar_date_is_treated_as_undated(self):
        lines = ["## 2026-13-45 タイトル"]
        self.assertEqual(
            sections.scan_headings(lines),
            [(0, None, None)],
        )

    def test_range_heading_with_invalid_start_date_is_treated_as_undated(self):
        lines = ["## 2026-02-30〜31 タイトル"]
        self.assertEqual(
            sections.scan_headings(lines),
            [(0, None, None)],
        )


class BodyInvariantTest(unittest.TestCase):
    def test_fenced_heading_like_line_stays_in_body_without_false_split(self):
        """Invariant (revised for item G): a section body may contain a line
        starting with '## ' when — and only when — it sits inside a fenced
        code block that opens and closes within that same body (scan_headings
        is fence-aware). This is what keeps mirror.py's scan_headings-based
        indexing consistent: re-scanning the body in isolation must find no
        heading at all, so the fenced line is never mistaken for a section
        boundary when the body is written back out."""
        text = """# ログ

## 2026-09-01 セッション1

最初のセクション。

## 未日付セクション

日付なしのセクション。

## 2026-09-02 セッション2

コードフェンスを含む：

```python
# これはコメント
## コメント行
def example():
    pass
```

セクションの本文。

## 2026-09-03 セッション3

最後のセクション。
"""
        parsed, undated = sections.parse_sections(text)
        session2 = next(section for section in parsed if section.title == "セッション2")
        # フェンス内の見出し風の行は本文にそのまま残る（打ち切られない）
        self.assertIn("## コメント行", session2.body)
        self.assertIn("セクションの本文。", session2.body)

        # ただし、その本文だけを単独で再スキャンしても見出しとしては検出されない
        # （mirror.py がこの本文をファイルへ書き戻した後、再度 scan_headings で
        # インデックスを作り直しても、フェンス内の行を見出しと誤認しない）。
        for section in parsed:
            heads_in_body = sections.scan_headings(section.body.split("\n"))
            self.assertEqual(
                heads_in_body, [],
                f"section '{section.title}' の本文を単独スキャンすると見出しが検出された: {heads_in_body}",
            )


class TitleTest(unittest.TestCase):
    def test_normalize_strips_spaces_and_trailing_colon(self):
        self.assertEqual(sections.normalize_title("  タイトル :  "), "タイトル")
        self.assertEqual(sections.normalize_title("タイトル："), "タイトル")

    def test_sanitize_replaces_link_breaking_characters(self):
        self.assertEqual(
            sections.sanitize_title("A#B|C[D]E"),
            "A＃B｜C［D］E",
        )


if __name__ == "__main__":
    unittest.main()
