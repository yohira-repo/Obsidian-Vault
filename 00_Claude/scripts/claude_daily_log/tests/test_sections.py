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
    def test_body_never_contains_line_starting_with_heading_marker(self):
        """Invariant: parse_sections never returns a Section whose body contains
        a line starting with '## '. This is critical for mirror.py's idempotency."""
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
        # Verify that no section body contains a line starting with '## '
        for section in parsed:
            for line in section.body.split("\n"):
                self.assertFalse(
                    line.startswith("## "),
                    f"Found '## ' line in body of section '{section.title}': {line}",
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
