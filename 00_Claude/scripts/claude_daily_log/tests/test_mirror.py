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


if __name__ == "__main__":
    unittest.main()
