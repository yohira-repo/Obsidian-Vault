import glob
import os
import tempfile
import unittest

import mirror
import sources


def entry(source_id="coopinf", date="2026-09-06", title="まとめ", body="本文。", order=0):
    return sources.Entry(
        source_id=source_id, date=date, title=title, body=body,
        origin="local", commit_date="", order=order,
    )


class MirrorPathTest(unittest.TestCase):
    def test_slash_in_source_id_becomes_hyphen(self):
        self.assertEqual(
            mirror.mirror_relpath("alphasystem/alphabsmail"),
            os.path.join("00_Claude", "projects", "alphasystem-alphabsmail.md"),
        )


class UpdateMirrorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def read(self, source_id="coopinf"):
        with open(os.path.join(self.vault, mirror.mirror_relpath(source_id)), encoding="utf-8") as handle:
            return handle.read()

    def test_creates_file_with_header(self):
        added, replaced = mirror.update_mirror(self.vault, "coopinf", [entry()])
        self.assertEqual((added, replaced), (1, 0))
        self.assertEqual(
            self.read(),
            "# coopinf 作業ログ\n\n## 2026-09-06 まとめ\n\n本文。\n",
        )

    def test_second_run_is_idempotent(self):
        mirror.update_mirror(self.vault, "coopinf", [entry()])
        before = self.read()
        added, replaced = mirror.update_mirror(self.vault, "coopinf", [entry()])
        self.assertEqual((added, replaced), (0, 0))
        self.assertEqual(self.read(), before)

    def test_changed_body_replaces_only_that_section(self):
        mirror.update_mirror(self.vault, "coopinf", [entry(title="A", body="旧本文。"),
                                                     entry(title="B", body="Bの本文。", order=1)])
        added, replaced = mirror.update_mirror(self.vault, "coopinf", [entry(title="A", body="新本文。\n追記行。")])
        self.assertEqual((added, replaced), (0, 1))
        self.assertEqual(
            self.read(),
            "# coopinf 作業ログ\n\n## 2026-09-06 A\n\n新本文。\n追記行。\n\n## 2026-09-06 B\n\nBの本文。\n",
        )

    def test_handwritten_sections_are_preserved(self):
        path = os.path.join(self.vault, mirror.mirror_relpath("coopinf"))
        os.makedirs(os.path.dirname(path))
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("# coopinf 作業ログ\n\n手書きのメモ。\n\n## 2026-01-01 過去分\n\n過去の本文。\n")
        mirror.update_mirror(self.vault, "coopinf", [entry()])
        text = self.read()
        self.assertIn("手書きのメモ。", text)
        self.assertIn("## 2026-01-01 過去分", text)
        self.assertTrue(text.endswith("## 2026-09-06 まとめ\n\n本文。\n"))

    def test_title_is_sanitized_in_heading(self):
        mirror.update_mirror(self.vault, "coopinf", [entry(title="A#B|C[D]E")])
        self.assertIn("## 2026-09-06 A＃B｜C［D］E", self.read())

    def test_empty_entries_does_not_create_file(self):
        added, replaced = mirror.update_mirror(self.vault, "coopinf", [])
        self.assertEqual((added, replaced), (0, 0))
        self.assertFalse(os.path.exists(os.path.join(self.vault, mirror.mirror_relpath("coopinf"))))


class ChronologicalInsertTest(unittest.TestCase):
    """全履歴ミラー: 過去日のセクションは既存の新しい日付のセクションより前に挿入する。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def read(self, source_id="coopinf"):
        with open(os.path.join(self.vault, mirror.mirror_relpath(source_id)), encoding="utf-8") as handle:
            return handle.read()

    def test_older_entry_is_inserted_before_existing_newer_section(self):
        # 実際の vault と同じ状況: 既存ファイルには 2026-09-06 だけがある
        mirror.update_mirror(self.vault, "coopinf", [entry(date="2026-09-06", title="新しい方")])
        added, replaced = mirror.update_mirror(
            self.vault, "coopinf", [entry(date="2026-08-01", title="古い方", body="古い本文。", order=0)]
        )
        self.assertEqual((added, replaced), (1, 0))
        self.assertEqual(
            self.read(),
            "# coopinf 作業ログ\n\n"
            "## 2026-08-01 古い方\n\n古い本文。\n\n"
            "## 2026-09-06 新しい方\n\n本文。\n",
        )

    def test_same_date_new_entry_is_inserted_after_existing_one(self):
        mirror.update_mirror(self.vault, "coopinf", [entry(date="2026-09-06", title="A", body="Aの本文。")])
        mirror.update_mirror(
            self.vault, "coopinf", [entry(date="2026-09-06", title="B", body="Bの本文。", order=1)]
        )
        self.assertEqual(
            self.read(),
            "# coopinf 作業ログ\n\n"
            "## 2026-09-06 A\n\nAの本文。\n\n"
            "## 2026-09-06 B\n\nBの本文。\n",
        )

    def test_out_of_order_backfill_entries_end_up_chronological(self):
        mirror.update_mirror(self.vault, "coopinf", [entry(date="2026-09-06", title="現在", body="現在の本文。")])
        # わざと新しい→古いの順で渡しても、結果はチェックロジカル順になること
        mirror.update_mirror(
            self.vault,
            "coopinf",
            [
                entry(date="2026-08-20", title="中間", body="中間の本文。", order=1),
                entry(date="2026-08-01", title="最古", body="最古の本文。", order=0),
            ],
        )
        self.assertEqual(
            self.read(),
            "# coopinf 作業ログ\n\n"
            "## 2026-08-01 最古\n\n最古の本文。\n\n"
            "## 2026-08-20 中間\n\n中間の本文。\n\n"
            "## 2026-09-06 現在\n\n現在の本文。\n",
        )

    def test_backfill_then_rerun_is_idempotent_and_byte_identical(self):
        mirror.update_mirror(self.vault, "coopinf", [entry(date="2026-09-06", title="現在", body="現在の本文。")])
        entries = [
            entry(date="2026-08-20", title="中間", body="中間の本文。", order=1),
            entry(date="2026-08-01", title="最古", body="最古の本文。", order=0),
        ]
        mirror.update_mirror(self.vault, "coopinf", entries)
        before = self.read()
        added, replaced = mirror.update_mirror(
            self.vault, "coopinf", [entry(date="2026-09-06", title="現在", body="現在の本文。")] + entries
        )
        self.assertEqual((added, replaced), (0, 0))
        self.assertEqual(self.read(), before)


class AtomicWriteTest(unittest.TestCase):
    """ブロッカー B: 書き込み失敗時に既存ミラーファイルを空・破損状態にしない。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def read(self, source_id="coopinf"):
        with open(os.path.join(self.vault, mirror.mirror_relpath(source_id)), encoding="utf-8") as handle:
            return handle.read()

    def test_replace_failure_leaves_existing_file_untouched(self):
        mirror.update_mirror(self.vault, "coopinf", [entry(title="A")])
        before = self.read()
        self.assertTrue(before)

        real_replace = os.replace

        def boom(src, dst):
            raise OSError("simulated crash during replace")

        os.replace = boom
        try:
            with self.assertRaises(OSError):
                mirror.update_mirror(self.vault, "coopinf", [entry(title="B", order=1)])
        finally:
            os.replace = real_replace

        self.assertEqual(self.read(), before)

    def test_no_temp_file_left_behind_after_successful_write(self):
        mirror.update_mirror(self.vault, "coopinf", [entry()])
        leftovers = glob.glob(os.path.join(self.vault, mirror.MIRROR_DIR, ".tmp-*"))
        self.assertEqual(leftovers, [])


if __name__ == "__main__":
    unittest.main()
