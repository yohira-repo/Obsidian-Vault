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
    def test_rows_are_returned_with_name_and_relative_path(self):
        self.assertEqual(
            projects.parse_project_table(TABLE),
            [
                ("alphasystem", "../alphasystem"),
                ("alphacdk", "../alphacdk"),
                ("alphabsmail", "./alphabsmail"),
            ],
        )

    def test_header_and_separator_rows_are_ignored(self):
        names = [name for name, _ in projects.parse_project_table(TABLE)]
        self.assertNotIn("プロジェクト名", names)

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
        """並びは従来どおり名前昇順。同居行（alphabsmail）が加わる点だけが変化。"""
        names = [p.name for p in projects.list_projects(self.root)]
        self.assertEqual(names, ["alphabsmail", "alphacdk", "alphasystem", "coopinf"])

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
        self.assertEqual(names, ["alphabsmail", "alphacdk", "alphasystem"])


class NestedProjectTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        os.makedirs(os.path.join(self.root, "alphasystem"))
        with open(os.path.join(self.root, "alphasystem", "CLAUDE.md"), "w", encoding="utf-8") as handle:
            handle.write(TABLE)

    def tearDown(self):
        self.tmp.cleanup()

    def test_nested_row_is_included_in_the_listing(self):
        names = [p.name for p in projects.list_projects(self.root, ("alphasystem/CLAUDE.md",))]
        self.assertEqual(names, ["alphabsmail", "alphacdk", "alphasystem"])

    def test_nested_path_resolves_under_owning_repo(self):
        found = {p.name: p for p in projects.list_projects(self.root, ("alphasystem/CLAUDE.md",))}
        self.assertEqual(
            found["alphabsmail"].path,
            os.path.join(self.root, "alphasystem", "alphabsmail"),
        )
        self.assertTrue(found["alphabsmail"].is_nested)
        self.assertFalse(found["alphasystem"].is_nested)

    def test_nested_exists_is_directory_based(self):
        found = {p.name: p for p in projects.list_projects(self.root, ("alphasystem/CLAUDE.md",))}
        self.assertFalse(found["alphabsmail"].exists)
        os.makedirs(os.path.join(self.root, "alphasystem", "alphabsmail"))
        found = {p.name: p for p in projects.list_projects(self.root, ("alphasystem/CLAUDE.md",))}
        self.assertTrue(found["alphabsmail"].exists)


if __name__ == "__main__":
    unittest.main()
