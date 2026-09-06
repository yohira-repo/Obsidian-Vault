import glob
import os
import tempfile
import unittest

import atomicio


class WriteTextAtomicTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "note.md")

    def tearDown(self):
        self.tmp.cleanup()

    def test_writes_full_content_with_lf(self):
        atomicio.write_text_atomic(self.path, "line1\nline2\n")
        with open(self.path, encoding="utf-8", newline="") as handle:
            self.assertEqual(handle.read(), "line1\nline2\n")

    def test_no_temp_file_left_behind_on_success(self):
        atomicio.write_text_atomic(self.path, "content\n")
        leftovers = glob.glob(os.path.join(self.tmp.name, ".tmp-*"))
        self.assertEqual(leftovers, [])

    def test_original_file_untouched_if_replace_fails(self):
        original = "original content that must survive\n"
        with open(self.path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(original)

        real_replace = os.replace

        def boom(src, dst):
            raise OSError("simulated crash during replace")

        os.replace = boom
        try:
            with self.assertRaises(OSError):
                atomicio.write_text_atomic(self.path, "new content that must NOT appear\n")
        finally:
            os.replace = real_replace

        with open(self.path, encoding="utf-8") as handle:
            self.assertEqual(handle.read(), original)
        # 一時ファイルも残らない
        leftovers = glob.glob(os.path.join(self.tmp.name, ".tmp-*"))
        self.assertEqual(leftovers, [])

    def test_creates_new_file_when_missing(self):
        self.assertFalse(os.path.exists(self.path))
        atomicio.write_text_atomic(self.path, "fresh\n")
        with open(self.path, encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "fresh\n")


if __name__ == "__main__":
    unittest.main()
