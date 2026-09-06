import os
import tempfile
import unittest

import projects


TABLE = """# alphaシステム

## 構成

  | プロジェクト名 | 相対フォルダー | 内容 |
  | -------------- | ------------- | ------ |
  | alphasystem | ../alphasystem | 設計ドキュメント |
  | alphacdk | ../alphacdk | CDK |
  | alphabsmail | ./alphabsmail | 当プロジェクト配下のディレクトリ |

本文の続き。
"""


class ParseProjectTableTest(unittest.TestCase):
    def test_only_parent_relative_rows_are_adopted(self):
        self.assertEqual(
            projects.parse_project_table(TABLE),
            ["alphasystem", "alphacdk"],
        )

    def test_header_and_separator_rows_are_ignored(self):
        self.assertNotIn("プロジェクト名", projects.parse_project_table(TABLE))

    def test_empty_text_returns_empty_list(self):
        self.assertEqual(projects.parse_project_table(""), [])


class ListProjectsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        os.makedirs(os.path.join(self.root, "alphasystem"))
        os.makedirs(os.path.join(self.root, "coop"))
        with open(os.path.join(self.root, "alphasystem", "CLAUDE.md"), "w", encoding="utf-8") as handle:
            handle.write(TABLE)
        with open(os.path.join(self.root, "coop", "CLAUDE.md"), "w", encoding="utf-8") as handle:
            handle.write("| coopinf | ../coopinf | インフラ |\n| alphacdk | ../alphacdk | 重複 |\n")

    def tearDown(self):
        self.tmp.cleanup()

    def test_projects_are_merged_deduped_and_sorted(self):
        names = [p.name for p in projects.list_projects(self.root)]
        self.assertEqual(names, ["alphacdk", "alphasystem", "coopinf"])

    def test_path_is_absolute_under_git_root(self):
        found = {p.name: p.path for p in projects.list_projects(self.root)}
        self.assertEqual(found["coopinf"], os.path.join(self.root, "coopinf"))

    def test_exists_is_false_without_git_directory(self):
        found = {p.name: p for p in projects.list_projects(self.root)}
        self.assertFalse(found["alphasystem"].exists)
        os.makedirs(os.path.join(self.root, "alphasystem", ".git"))
        found = {p.name: p for p in projects.list_projects(self.root)}
        self.assertTrue(found["alphasystem"].exists)

    def test_missing_config_file_is_skipped(self):
        os.remove(os.path.join(self.root, "coop", "CLAUDE.md"))
        names = [p.name for p in projects.list_projects(self.root)]
        self.assertEqual(names, ["alphacdk", "alphasystem"])


if __name__ == "__main__":
    unittest.main()
