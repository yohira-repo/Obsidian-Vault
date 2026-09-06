# Claude Code 会話まとめの Daily ページ反映 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 複数リポジトリの `conversations.md` から当日分の会話まとめを収集し、Obsidian Vault のミラーノートと Daily ノートへ自動反映する CLI と、その自動起動（SessionEnd hook）を用意する。

**Architecture:** Vault 内 `00_Claude/scripts/claude_daily_log/` にフラットな Python モジュール群を置く。`cli.py` がエントリで、`projects.py`（対象プロジェクト一覧）→ `sources.py`（git 走査と収集）→ `sections.py`（見出し解析）→ `mirror.py` / `daily.py`（Vault への書き出し）の順に処理する。`gitsync.py` は GitHub との同期（clone / fetch）のみを担当する。Daily の管理ブロックは毎回全再生成するため、どのセッションから起動されても結果は同じになる。

**Tech Stack:** Python 3.9.6（macOS 標準 `/usr/bin/python3`）、標準ライブラリのみ（`unittest`, `subprocess`, `fcntl`, `concurrent.futures`, `argparse`, `logging`）、git CLI

**設計書:** `00_Claude/specs/2026-09-06-daily-claude-log-sync-design.md`

## Global Constraints

- Python は 3.9.6。`X | Y` 形式の型注釈、`dataclass(slots=True)`、`match` 文は使えない。型注釈は `typing.List` などを使う。
- 標準ライブラリのみ。pip インストールは行わない。
- ファイル入出力はすべて `encoding="utf-8"`、書き込みは `newline="\n"` を明示する（Claudian の Write は UTF-16 になるため、生成・追記は必ず本スクリプト経由）。
- CLI は常に終了コード 0 を返す。失敗は警告としてログと report に残す。
- 対象 Vault の既定は `~/Documents/Obsidian-Vault`、対象 git ルートの既定は `~/git`。どちらも `--vault` / `--git-root` と環境変数 `CLAUDE_DAILY_LOG_VAULT` / `CLAUDE_DAILY_LOG_GIT_ROOT` で上書きできる。
- 作業ブランチ: Vault リポジトリは obsidian-git が `main` を直接同期する運用のため、**feature ブランチを切らず `main` 上でコミットする**（`00_Claude/conversations.md` の 2026-08-24 の記録に基づく既定運用）。Draft PR も作成しない。
- テスト実行コマンド（全タスク共通、絶対パス指定なので `cd` 不要）:

```bash
python3 -m unittest discover \
  -s /Users/yohira/Documents/Obsidian-Vault/00_Claude/scripts/claude_daily_log/tests \
  -t /Users/yohira/Documents/Obsidian-Vault/00_Claude/scripts/claude_daily_log -v
```

- テストはネットワークに接続しない。git を使うテストは一時ディレクトリに `git init -b main` したダミーリポジトリを作る。

---

## File Structure

| パス | 責務 |
| - | - |
| `00_Claude/scripts/claude_daily_log/sections.py` | `conversations.md` のテキスト解析のみ。見出し判定、セクション切り出し、タイトル正規化・サニタイズ |
| `00_Claude/scripts/claude_daily_log/projects.py` | `CLAUDE.md` の構成テーブルから対象リポジトリ一覧を作る |
| `00_Claude/scripts/claude_daily_log/sources.py` | git を叩いて `conversations.md` を発見・読み出し、対象日の `Entry` に変換、重複排除 |
| `00_Claude/scripts/claude_daily_log/mirror.py` | `00_Claude/projects/*.md` への追記・置換 |
| `00_Claude/scripts/claude_daily_log/daily.py` | `01_Daily/YYYY-MM-DD.md` の管理ブロック再生成 |
| `00_Claude/scripts/claude_daily_log/gitsync.py` | 未 clone プロジェクトの clone と並列 fetch |
| `00_Claude/scripts/claude_daily_log/cli.py` | 引数解析、排他ロック、ログ、サブコマンドの組み立て |
| `00_Claude/scripts/claude_daily_log/tests/` | unittest。`helpers.py` にダミーリポジトリ生成を集約 |
| `~/.claude/settings.json` | SessionEnd hook の登録（Vault 外・git 管理外） |
| `~/.claude/commands/daily-sync.md` | 手動実行用スラッシュコマンド（Vault 外・git 管理外） |

`cli.py` は自身のディレクトリを `sys.path` に追加するため、各モジュールは `import sections` のように平坦に import する。

---

### Task 1: セクション解析（sections.py）

**Files:**
- Create: `00_Claude/scripts/claude_daily_log/tests/__init__.py`
- Create: `00_Claude/scripts/claude_daily_log/tests/test_sections.py`
- Create: `00_Claude/scripts/claude_daily_log/sections.py`

**Interfaces:**
- Consumes: なし
- Produces:
  - `ANY_H2_RE`, `DATED_H2_RE`, `RANGE_H2_RE`（`re.Pattern`）
  - `Section(date: str, title: str, body: str, order: int)`（frozen dataclass）
  - `normalize_title(title: str) -> str`
  - `sanitize_title(title: str) -> str`
  - `scan_headings(lines: List[str]) -> List[Tuple[int, Optional[str], Optional[str]]]`（`(行番号, 日付 or None, 正規化タイトル or None)`。mirror.py と共用する）
  - `parse_sections(text: str) -> Tuple[List[Section], int]`（第2要素は日付なし見出しの件数）

- [ ] **Step 1: ディレクトリと空の `tests/__init__.py` を作る**

```bash
mkdir -p /Users/yohira/Documents/Obsidian-Vault/00_Claude/scripts/claude_daily_log/tests
: > /Users/yohira/Documents/Obsidian-Vault/00_Claude/scripts/claude_daily_log/tests/__init__.py
```

- [ ] **Step 2: 失敗するテストを書く**

`00_Claude/scripts/claude_daily_log/tests/test_sections.py`:

```python
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
```

- [ ] **Step 3: テストが失敗することを確認する**

Run:

```bash
python3 -m unittest discover \
  -s /Users/yohira/Documents/Obsidian-Vault/00_Claude/scripts/claude_daily_log/tests \
  -t /Users/yohira/Documents/Obsidian-Vault/00_Claude/scripts/claude_daily_log -v
```

Expected: `ModuleNotFoundError: No module named 'sections'`

- [ ] **Step 4: 実装する**

`00_Claude/scripts/claude_daily_log/sections.py`:

```python
"""conversations.md の見出し・セクション解析。"""
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

ANY_H2_RE = re.compile(r"^##\s+(.*)$")
DATED_H2_RE = re.compile(r"^##\s+(\d{4}-\d{2}-\d{2})\s*(?:[:：\-—–]\s*)?(.+?)\s*$")

_SANITIZE_MAP = {"#": "＃", "|": "｜", "[": "［", "]": "］"}


@dataclass(frozen=True)
class Section:
    date: str
    title: str
    body: str
    order: int


def normalize_title(title: str) -> str:
    """前後の空白と末尾のコロンを取り除く。"""
    return title.strip().rstrip(":：").strip()


def sanitize_title(title: str) -> str:
    """Obsidian の見出しリンクを壊す文字を全角に置き換える。"""
    return "".join(_SANITIZE_MAP.get(char, char) for char in title)


def scan_headings(lines: List[str]) -> List[Tuple[int, Optional[str], Optional[str]]]:
    """`## ` 見出しを (行番号, 日付 or None, 正規化タイトル or None) の一覧にする。"""
    heads = []
    for index, line in enumerate(lines):
        if not ANY_H2_RE.match(line):
            continue
        matched = DATED_H2_RE.match(line)
        if matched:
            heads.append((index, matched.group(1), normalize_title(matched.group(2))))
        else:
            heads.append((index, None, None))
    return heads


def parse_sections(text: str) -> Tuple[List[Section], int]:
    """日付付き `## ` セクションの一覧と、日付なし `## ` 見出しの件数を返す。"""
    lines = text.splitlines()
    heads = scan_headings(lines)

    parsed = []
    undated = 0
    order = 0
    for position, (index, date, title) in enumerate(heads):
        end = heads[position + 1][0] if position + 1 < len(heads) else len(lines)
        if date is None:
            undated += 1
            continue
        body = "\n".join(lines[index + 1:end]).strip("\n")
        parsed.append(Section(date=date, title=title, body=body, order=order))
        order += 1
    return parsed, undated
```

- [ ] **Step 5: テストが通ることを確認する**

Run: 上と同じ discover コマンド
Expected: `OK`（20 tests）

- [ ] **Step 6: コミットする**

```bash
cd /Users/yohira/Documents/Obsidian-Vault
git add 00_Claude/scripts/claude_daily_log/sections.py 00_Claude/scripts/claude_daily_log/tests
git commit -m "feat(daily-log): conversations.md のセクション解析を追加"
```

---

### Task 2: 対象プロジェクト一覧（projects.py）

**Files:**
- Create: `00_Claude/scripts/claude_daily_log/tests/test_projects.py`
- Create: `00_Claude/scripts/claude_daily_log/projects.py`

**Interfaces:**
- Consumes: なし
- Produces:
  - `Project(name: str, path: str)`（frozen dataclass、`exists` プロパティ付き）
  - `DEFAULT_CONFIG_FILES: Tuple[str, ...]` = `("alphasystem/CLAUDE.md", "coop/CLAUDE.md")`
  - `parse_project_table(text: str) -> List[str]`
  - `list_projects(git_root: str, config_files=DEFAULT_CONFIG_FILES) -> List[Project]`

- [ ] **Step 1: 失敗するテストを書く**

`00_Claude/scripts/claude_daily_log/tests/test_projects.py`:

```python
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
```

- [ ] **Step 2: テストが失敗することを確認する**

Run: Global Constraints の discover コマンド
Expected: `ModuleNotFoundError: No module named 'projects'`

- [ ] **Step 3: 実装する**

`00_Claude/scripts/claude_daily_log/projects.py`:

```python
"""CLAUDE.md の構成テーブルから対象プロジェクト一覧を得る。"""
import os
import re
from dataclasses import dataclass
from typing import List, Sequence

ROW_RE = re.compile(r"^\s*\|\s*([A-Za-z0-9_.-]+)\s*\|\s*(\.{1,2}/[^|]+?)\s*\|")

DEFAULT_CONFIG_FILES = ("alphasystem/CLAUDE.md", "coop/CLAUDE.md")


@dataclass(frozen=True)
class Project:
    name: str
    path: str

    @property
    def exists(self) -> bool:
        return os.path.isdir(os.path.join(self.path, ".git"))


def parse_project_table(text: str) -> List[str]:
    """相対フォルダーが `../` で始まる行だけを独立リポジトリとして採用する。"""
    names = []
    for line in text.splitlines():
        matched = ROW_RE.match(line)
        if not matched:
            continue
        if not matched.group(2).startswith("../"):
            continue
        name = matched.group(1)
        if name not in names:
            names.append(name)
    return names


def list_projects(git_root: str, config_files: Sequence[str] = DEFAULT_CONFIG_FILES) -> List[Project]:
    names = []
    for relative in config_files:
        path = os.path.join(git_root, relative)
        try:
            with open(path, encoding="utf-8") as handle:
                text = handle.read()
        except OSError:
            continue
        for name in parse_project_table(text):
            if name not in names:
                names.append(name)
    return [Project(name=name, path=os.path.join(git_root, name)) for name in sorted(names)]
```

- [ ] **Step 4: テストが通ることを確認する**

Run: discover コマンド
Expected: `OK`（28 tests）

- [ ] **Step 5: 実データでパース結果を目視確認する**

```bash
python3 -c "
import sys
sys.path.insert(0, '/Users/yohira/Documents/Obsidian-Vault/00_Claude/scripts/claude_daily_log')
import projects
for p in projects.list_projects('/Users/yohira/git'):
    print(p.name, p.exists)
"
```

Expected: 17 行が出力され、`alphabsmail` が含まれないこと。`coopcdeweb` / `coopcdeinput` / `coopcdealert` が `False` であること。

- [ ] **Step 6: コミットする**

```bash
cd /Users/yohira/Documents/Obsidian-Vault
git add 00_Claude/scripts/claude_daily_log/projects.py 00_Claude/scripts/claude_daily_log/tests/test_projects.py
git commit -m "feat(daily-log): CLAUDE.md から対象プロジェクト一覧を取得"
```

---

### Task 3: git からの収集（sources.py）

**Files:**
- Create: `00_Claude/scripts/claude_daily_log/tests/helpers.py`
- Create: `00_Claude/scripts/claude_daily_log/tests/test_sources.py`
- Create: `00_Claude/scripts/claude_daily_log/sources.py`

**Interfaces:**
- Consumes: `sections.parse_sections`, `sections.Section`
- Produces:
  - `Entry(source_id: str, date: str, title: str, body: str, origin: str, commit_date: str, order: int)`（frozen dataclass）
  - `GitCommandError(RuntimeError)`
  - `run_git(repo: str, args: List[str]) -> str`
  - `is_conversations_path(path: str) -> bool`
  - `source_id_from(repo_name: str, rel_path: str) -> str`
  - `local_files(repo: str) -> List[str]`
  - `remote_refs(repo: str) -> List[Tuple[str, str]]`（`(ref 名, コミット日時 ISO)`）
  - `collect_entries(repo: str, repo_name: str, target_date: str) -> Tuple[List[Entry], List[str]]`
  - `dedupe(entries: List[Entry]) -> List[Entry]`

- [ ] **Step 1: テスト用ヘルパーを書く**

`00_Claude/scripts/claude_daily_log/tests/helpers.py`:

```python
"""テスト用のダミー git リポジトリ生成ヘルパー。"""
import os
import subprocess


def git(repo, *args):
    subprocess.run(["git", "-C", repo] + list(args), check=True, capture_output=True)


def write(repo, rel_path, text):
    path = os.path.join(repo, rel_path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def init_repo(path, files, branch="main", message="init"):
    """files は {相対パス: 内容} の dict。コミットまで済ませたリポジトリを作る。"""
    os.makedirs(path, exist_ok=True)
    subprocess.run(["git", "init", "-b", branch, path], check=True, capture_output=True)
    git(path, "config", "user.email", "test@example.com")
    git(path, "config", "user.name", "test")
    for rel_path, text in files.items():
        write(path, rel_path, text)
    git(path, "add", "-A")
    git(path, "commit", "-m", message)
    return path


def clone_repo(source, dest):
    subprocess.run(["git", "clone", "--quiet", source, dest], check=True, capture_output=True)
    git(dest, "config", "user.email", "test@example.com")
    git(dest, "config", "user.name", "test")
    return dest


def commit_on_branch(repo, branch, files, message="update"):
    git(repo, "checkout", "-q", "-b", branch)
    for rel_path, text in files.items():
        write(repo, rel_path, text)
    git(repo, "add", "-A")
    git(repo, "commit", "-m", message)
```

- [ ] **Step 2: 失敗するテストを書く**

`00_Claude/scripts/claude_daily_log/tests/test_sources.py`:

```python
import os
import tempfile
import unittest

import sources
from tests import helpers


CONV_ROOT = """# 会話ログ

## 2026-09-06 直下のまとめ

直下の本文。

## 2026-09-05 前日のまとめ

前日の本文。
"""

CONV_DOCS = """# 会話記録

## 2026-09-06 docs 配下のまとめ

docs の本文。
"""

CONV_SUB = """# conversations

## 2026-09-06 サブプロジェクトのまとめ

サブの本文。

## 日付なし見出し

無視される本文。
"""


class PathRuleTest(unittest.TestCase):
    def test_only_conversations_md_is_accepted(self):
        self.assertTrue(sources.is_conversations_path("conversations.md"))
        self.assertTrue(sources.is_conversations_path("docs/conversations.md"))
        self.assertFalse(sources.is_conversations_path("docs/conversation.md"))
        self.assertFalse(sources.is_conversations_path("README.md"))

    def test_excluded_directories_are_rejected(self):
        self.assertFalse(sources.is_conversations_path("node_modules/x/conversations.md"))
        self.assertFalse(sources.is_conversations_path("dist/conversations.md"))

    def test_source_id_drops_docs_segment(self):
        self.assertEqual(sources.source_id_from("coopinf", "conversations.md"), "coopinf")
        self.assertEqual(sources.source_id_from("alphasystem", "docs/conversations.md"), "alphasystem")
        self.assertEqual(
            sources.source_id_from("alphasystem", "alphabsmail/docs/conversations.md"),
            "alphasystem/alphabsmail",
        )


class CollectEntriesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.origin = helpers.init_repo(
            os.path.join(self.tmp.name, "origin"),
            {
                "conversations.md": CONV_ROOT,
                "docs/conversations.md": CONV_DOCS,
                "alphabsmail/docs/conversations.md": CONV_SUB,
                "node_modules/pkg/conversations.md": CONV_ROOT,
            },
        )
        self.repo = helpers.clone_repo(self.origin, os.path.join(self.tmp.name, "work"))

    def tearDown(self):
        self.tmp.cleanup()

    def test_finds_conversations_at_any_depth(self):
        entries, _ = sources.collect_entries(self.repo, "alphasystem", "2026-09-06")
        self.assertEqual(
            sorted({entry.source_id for entry in entries}),
            ["alphasystem", "alphasystem/alphabsmail"],
        )

    def test_target_date_filters_sections(self):
        entries, _ = sources.collect_entries(self.repo, "alphasystem", "2026-09-05")
        self.assertEqual([entry.title for entry in sources.dedupe(entries)], ["前日のまとめ"])

    def test_undated_heading_is_reported_once(self):
        _, warnings = sources.collect_entries(self.repo, "alphasystem", "2026-09-06")
        matched = [w for w in warnings if "日付なし見出し" in w]
        self.assertEqual(len(matched), 1)
        self.assertIn("alphabsmail/docs/conversations.md", matched[0])

    def test_remote_branch_content_is_collected(self):
        helpers.commit_on_branch(
            self.origin,
            "feature/new",
            {"conversations.md": CONV_ROOT + "\n## 2026-09-06 ブランチ限定のまとめ\n\nブランチ本文。\n"},
        )
        helpers.git(self.repo, "fetch", "--quiet", "origin")
        entries = sources.dedupe(sources.collect_entries(self.repo, "alphasystem", "2026-09-06")[0])
        self.assertIn("ブランチ限定のまとめ", [entry.title for entry in entries])

    def test_local_worktree_wins_over_remote(self):
        helpers.write(self.repo, "conversations.md",
                      "## 2026-09-06 直下のまとめ\n\nローカルで書き足した本文。\n")
        entries = sources.dedupe(sources.collect_entries(self.repo, "alphasystem", "2026-09-06")[0])
        found = [entry for entry in entries if entry.title == "直下のまとめ"]
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].body, "ローカルで書き足した本文。")

    def test_untracked_local_file_is_collected(self):
        helpers.write(self.repo, "sub/docs/conversations.md",
                      "## 2026-09-06 未追跡ファイルのまとめ\n\n未追跡の本文。\n")
        entries = sources.dedupe(sources.collect_entries(self.repo, "alphasystem", "2026-09-06")[0])
        self.assertIn("alphasystem/sub", [entry.source_id for entry in entries])

    def test_repository_without_conversations_returns_empty(self):
        plain = helpers.init_repo(os.path.join(self.tmp.name, "plain"), {"README.md": "x"})
        entries, warnings = sources.collect_entries(plain, "plain", "2026-09-06")
        self.assertEqual(entries, [])
        self.assertEqual(warnings, [])

    def test_broken_repository_raises_git_command_error(self):
        broken = os.path.join(self.tmp.name, "broken")
        os.makedirs(broken)
        with self.assertRaises(sources.GitCommandError):
            sources.collect_entries(broken, "broken", "2026-09-06")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: テストが失敗することを確認する**

Run: discover コマンド
Expected: `ModuleNotFoundError: No module named 'sources'`

- [ ] **Step 4: 実装する**

`00_Claude/scripts/claude_daily_log/sources.py`:

```python
"""git リポジトリから conversations.md を収集する。"""
import os
import subprocess
from dataclasses import dataclass
from typing import Dict, List, Tuple

import sections as sections_module

CONV_BASENAME = "conversations.md"
EXCLUDE_SEGMENTS = {"node_modules", "dist", "build", ".next", "vendor"}
GIT_TIMEOUT = 30


class GitCommandError(RuntimeError):
    pass


@dataclass(frozen=True)
class Entry:
    source_id: str
    date: str
    title: str
    body: str
    origin: str
    commit_date: str
    order: int


def run_git(repo: str, args: List[str]) -> str:
    try:
        proc = subprocess.run(["git", "-C", repo] + args, capture_output=True, timeout=GIT_TIMEOUT)
    except (OSError, subprocess.SubprocessError) as error:
        raise GitCommandError("git %s: %s" % (" ".join(args), error))
    if proc.returncode != 0:
        raise GitCommandError("git %s: %s" % (" ".join(args), proc.stderr.decode("utf-8", "replace").strip()))
    return proc.stdout.decode("utf-8", "replace")


def is_conversations_path(path: str) -> bool:
    parts = path.split("/")
    if parts[-1] != CONV_BASENAME:
        return False
    return not any(part in EXCLUDE_SEGMENTS for part in parts[:-1])


def source_id_from(repo_name: str, rel_path: str) -> str:
    directories = [part for part in rel_path.split("/")[:-1] if part != "docs"]
    return "/".join([repo_name] + directories)


def local_files(repo: str) -> List[str]:
    found = []
    for args in (["ls-files", "-z"], ["ls-files", "--others", "--exclude-standard", "-z"]):
        output = run_git(repo, args)
        for path in output.split("\0"):
            if path and is_conversations_path(path) and path not in found:
                found.append(path)
    return found


def remote_refs(repo: str) -> List[Tuple[str, str]]:
    output = run_git(
        repo,
        ["for-each-ref", "--format=%(refname:short)\t%(committerdate:iso-strict)", "refs/remotes/origin"],
    )
    refs = []
    for line in output.splitlines():
        if "\t" not in line:
            continue
        name, commit_date = line.split("\t", 1)
        if name == "origin" or name.endswith("/HEAD"):
            continue
        refs.append((name, commit_date))
    return refs


def _to_entries(text, repo_name, rel_path, origin, commit_date, target_date, warnings):
    parsed, undated = sections_module.parse_sections(text)
    if undated and origin == "local":
        warnings.append("日付なし見出し %d 件: %s/%s" % (undated, repo_name, rel_path))
    source_id = source_id_from(repo_name, rel_path)
    return [
        Entry(
            source_id=source_id,
            date=section.date,
            title=section.title,
            body=section.body,
            origin=origin,
            commit_date=commit_date,
            order=section.order,
        )
        for section in parsed
        if section.date == target_date
    ]


def collect_entries(repo: str, repo_name: str, target_date: str) -> Tuple[List[Entry], List[str]]:
    entries: List[Entry] = []
    warnings: List[str] = []

    for rel_path in local_files(repo):
        try:
            with open(os.path.join(repo, rel_path), encoding="utf-8", errors="replace") as handle:
                text = handle.read()
        except OSError as error:
            warnings.append("%s/%s: 読み込みに失敗しました (%s)" % (repo_name, rel_path, error))
            continue
        entries.extend(_to_entries(text, repo_name, rel_path, "local", "", target_date, warnings))

    blob_cache: Dict[str, str] = {}
    for ref, commit_date in remote_refs(repo):
        try:
            listing = run_git(repo, ["ls-tree", "-r", "--name-only", ref])
        except GitCommandError:
            continue
        for rel_path in listing.splitlines():
            if not is_conversations_path(rel_path):
                continue
            try:
                blob = run_git(repo, ["rev-parse", "%s:%s" % (ref, rel_path)]).strip()
                text = blob_cache[blob] if blob in blob_cache else run_git(repo, ["cat-file", "blob", blob])
            except GitCommandError:
                continue
            blob_cache[blob] = text
            entries.extend(_to_entries(text, repo_name, rel_path, ref, commit_date, target_date, warnings))

    return entries, warnings


def _rank(entry: Entry) -> Tuple[int, str]:
    return (1 if entry.origin == "local" else 0, entry.commit_date)


def dedupe(entries: List[Entry]) -> List[Entry]:
    """(ソース識別子, 日付, タイトル) で重複を排除し、ローカル優先・新しいコミット優先で残す。"""
    best: Dict[Tuple[str, str, str], Entry] = {}
    for entry in entries:
        key = (entry.source_id, entry.date, entry.title)
        current = best.get(key)
        if current is None or _rank(entry) > _rank(current):
            best[key] = entry
    return sorted(best.values(), key=lambda entry: (entry.source_id, entry.order, entry.title))
```

- [ ] **Step 5: テストが通ることを確認する**

Run: discover コマンド
Expected: `OK`（39 tests）

- [ ] **Step 6: 実データで収集結果を確認する**

```bash
python3 -c "
import sys
sys.path.insert(0, '/Users/yohira/Documents/Obsidian-Vault/00_Claude/scripts/claude_daily_log')
import projects, sources
found = []
for p in projects.list_projects('/Users/yohira/git'):
    if not p.exists:
        continue
    entries, warnings = sources.collect_entries(p.path, p.name, '2026-09-06')
    found.extend(entries)
    for w in warnings:
        print('WARN', w)
for e in sources.dedupe(found):
    print(e.source_id, '|', e.title, '|', e.origin)
"
```

Expected: `coopinf | CFテンプレートの日本語コメントがコンソールで文字化けする件 | ...` が含まれること。処理が 30 秒以内に終わること。

- [ ] **Step 7: コミットする**

```bash
cd /Users/yohira/Documents/Obsidian-Vault
git add 00_Claude/scripts/claude_daily_log/sources.py 00_Claude/scripts/claude_daily_log/tests
git commit -m "feat(daily-log): git からの conversations.md 収集を追加"
```

---

### Task 4: ミラーノート出力（mirror.py）

**Files:**
- Create: `00_Claude/scripts/claude_daily_log/tests/test_mirror.py`
- Create: `00_Claude/scripts/claude_daily_log/mirror.py`

**Interfaces:**
- Consumes: `sections.scan_headings`, `sections.sanitize_title`, `sources.Entry`
- Produces:
  - `MIRROR_DIR: str` = `"00_Claude/projects"`
  - `mirror_relpath(source_id: str) -> str`
  - `update_mirror(vault: str, source_id: str, entries: List[Entry]) -> Tuple[int, int]`（`(追加数, 置換数)`）

- [ ] **Step 1: 失敗するテストを書く**

`00_Claude/scripts/claude_daily_log/tests/test_mirror.py`:

```python
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
```

- [ ] **Step 2: テストが失敗することを確認する**

Run: discover コマンド
Expected: `ModuleNotFoundError: No module named 'mirror'`

- [ ] **Step 3: 実装する**

`00_Claude/scripts/claude_daily_log/mirror.py`:

```python
"""Vault 内ミラーノート（00_Claude/projects/*.md）の更新。"""
import os
from typing import Dict, List, Tuple

import sections as sections_module

MIRROR_DIR = os.path.join("00_Claude", "projects")


def mirror_relpath(source_id: str) -> str:
    return os.path.join(MIRROR_DIR, source_id.replace("/", "-") + ".md")


def _index(lines: List[str]) -> Dict[Tuple[str, str], Tuple[int, int]]:
    """既存の日付付き見出しを {(日付, タイトル): (見出し行, 終端行)} に索引化する。"""
    heads = sections_module.scan_headings(lines)

    result = {}
    for position, (index, date, title) in enumerate(heads):
        end = heads[position + 1][0] if position + 1 < len(heads) else len(lines)
        if date is not None:
            result[(date, title)] = (index, end)
    return result


def update_mirror(vault: str, source_id: str, entries: List) -> Tuple[int, int]:
    """未収録セクションを追記し、本文が変化したセクションは置換する。"""
    if not entries:
        return (0, 0)

    path = os.path.join(vault, mirror_relpath(source_id))
    if os.path.exists(path):
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
    else:
        text = "# %s 作業ログ\n" % source_id

    lines = text.splitlines()
    added = 0
    replaced = 0

    for entry in entries:
        title = sections_module.sanitize_title(entry.title)
        body_lines = entry.body.splitlines()
        index = _index(lines)
        key = (entry.date, title)
        if key in index:
            head_index, end_index = index[key]
            current = "\n".join(lines[head_index + 1:end_index]).strip("\n")
            if current == entry.body:
                continue
            lines[head_index + 1:end_index] = [""] + body_lines + [""]
            replaced += 1
        else:
            while lines and lines[-1].strip() == "":
                lines.pop()
            lines.extend(["", "## %s %s" % (entry.date, title), ""] + body_lines)
            added += 1

    if added == 0 and replaced == 0 and os.path.exists(path):
        return (0, 0)

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines).rstrip("\n") + "\n")
    return (added, replaced)
```

- [ ] **Step 4: テストが通ることを確認する**

Run: discover コマンド
Expected: `OK`（46 tests）

- [ ] **Step 5: コミットする**

```bash
cd /Users/yohira/Documents/Obsidian-Vault
git add 00_Claude/scripts/claude_daily_log/mirror.py 00_Claude/scripts/claude_daily_log/tests/test_mirror.py
git commit -m "feat(daily-log): ミラーノートへの追記・置換を追加"
```

---

### Task 5: Daily ノート出力（daily.py）

**Files:**
- Create: `00_Claude/scripts/claude_daily_log/tests/test_daily.py`
- Create: `00_Claude/scripts/claude_daily_log/daily.py`

**Interfaces:**
- Consumes: `sections.sanitize_title`, `sources.Entry`
- Produces:
  - `DAILY_DIR`, `SECTION_HEADING`, `START_MARKER`, `END_MARKER`（str 定数）
  - `DailyMarkerError(RuntimeError)`（マーカーが壊れている Daily を検出したときに送出。cli 側で警告に変換する）
  - `daily_relpath(date: str) -> str`
  - `render_lines(entries: List[Entry]) -> List[str]`
  - `update_daily(vault: str, date: str, entries: List[Entry]) -> bool`（書き換えたら True）

- [ ] **Step 1: 失敗するテストを書く**

`00_Claude/scripts/claude_daily_log/tests/test_daily.py`:

```python
import os
import tempfile
import unittest

import daily
import sources

HANDWRITTEN = """- [x] 定例：coopbatch

## 社内システム

・MFクラウド連携(着手)
"""


def entry(source_id="coopinf", title="まとめ", date="2026-09-06", order=0):
    return sources.Entry(
        source_id=source_id, date=date, title=title, body="本文。",
        origin="local", commit_date="", order=order,
    )


class RenderTest(unittest.TestCase):
    def test_line_links_to_mirror_heading(self):
        self.assertEqual(
            daily.render_lines([entry(source_id="alphasystem/alphabsmail", title="Track1 の見直し")]),
            ["- **alphasystem/alphabsmail** — "
             "[[00_Claude/projects/alphasystem-alphabsmail#2026-09-06 Track1 の見直し|Track1 の見直し]]"],
        )

    def test_title_is_sanitized(self):
        line = daily.render_lines([entry(title="A|B")])[0]
        self.assertNotIn("A|B", line)
        self.assertIn("A｜B", line)


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

    def test_creates_daily_when_missing(self):
        self.assertTrue(daily.update_daily(self.vault, "2026-09-06", [entry()]))
        self.assertEqual(
            self.read(),
            "## Claude作業ログ\n\n<!-- claude-log:start -->\n"
            "- **coopinf** — [[00_Claude/projects/coopinf#2026-09-06 まとめ|まとめ]]\n"
            "<!-- claude-log:end -->\n",
        )

    def test_does_not_create_empty_daily(self):
        self.assertFalse(daily.update_daily(self.vault, "2026-09-06", []))
        self.assertFalse(os.path.exists(self.path))

    def test_appends_block_to_existing_note_without_markers(self):
        self.write(HANDWRITTEN)
        daily.update_daily(self.vault, "2026-09-06", [entry()])
        text = self.read()
        self.assertTrue(text.startswith(HANDWRITTEN.rstrip("\n")))
        self.assertIn("## Claude作業ログ", text)
        self.assertIn("<!-- claude-log:end -->", text)

    def test_replaces_only_managed_block(self):
        self.write(HANDWRITTEN)
        daily.update_daily(self.vault, "2026-09-06", [entry(title="旧")])
        daily.update_daily(self.vault, "2026-09-06", [entry(title="新")])
        text = self.read()
        self.assertIn(HANDWRITTEN.rstrip("\n"), text)
        self.assertNotIn("旧", text)
        self.assertIn("新", text)
        self.assertEqual(text.count("<!-- claude-log:start -->"), 1)

    def test_empty_entries_clears_block_but_keeps_markers(self):
        self.write(HANDWRITTEN)
        daily.update_daily(self.vault, "2026-09-06", [entry()])
        daily.update_daily(self.vault, "2026-09-06", [])
        text = self.read()
        self.assertIn("## Claude作業ログ", text)
        self.assertIn("<!-- claude-log:start -->\n<!-- claude-log:end -->", text)

    def test_second_run_with_same_entries_reports_no_change(self):
        daily.update_daily(self.vault, "2026-09-06", [entry()])
        before = self.read()
        self.assertFalse(daily.update_daily(self.vault, "2026-09-06", [entry()]))
        self.assertEqual(self.read(), before)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: テストが失敗することを確認する**

Run: discover コマンド
Expected: `ModuleNotFoundError: No module named 'daily'`

- [ ] **Step 3: 実装する**

`00_Claude/scripts/claude_daily_log/daily.py`:

```python
"""Daily ノート（01_Daily/YYYY-MM-DD.md）の管理ブロック更新。"""
import os
from typing import List

import sections as sections_module

DAILY_DIR = "01_Daily"
SECTION_HEADING = "## Claude作業ログ"
START_MARKER = "<!-- claude-log:start -->"
END_MARKER = "<!-- claude-log:end -->"


def daily_relpath(date: str) -> str:
    return os.path.join(DAILY_DIR, date + ".md")


def render_lines(entries: List) -> List[str]:
    rendered = []
    for entry in entries:
        note = entry.source_id.replace("/", "-")
        title = sections_module.sanitize_title(entry.title)
        rendered.append(
            "- **%s** — [[00_Claude/projects/%s#%s %s|%s]]"
            % (entry.source_id, note, entry.date, title, title)
        )
    return rendered


def update_daily(vault: str, date: str, entries: List) -> bool:
    """管理ブロックだけを再生成する。書き換えが発生したら True を返す。"""
    path = os.path.join(vault, daily_relpath(date))
    exists = os.path.exists(path)
    if not exists and not entries:
        return False

    if exists:
        with open(path, encoding="utf-8") as handle:
            original = handle.read()
        lines = original.splitlines()
    else:
        original = None
        lines = []

    block = [START_MARKER] + render_lines(entries) + [END_MARKER]
    if START_MARKER in lines and END_MARKER in lines:
        start = lines.index(START_MARKER)
        end = lines.index(END_MARKER, start)
        new_lines = lines[:start] + block + lines[end + 1:]
    else:
        while lines and lines[-1].strip() == "":
            lines.pop()
        prefix = lines + [""] if lines else []
        new_lines = prefix + [SECTION_HEADING, ""] + block

    new_text = "\n".join(new_lines).rstrip("\n") + "\n"
    if original == new_text:
        return False

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(new_text)
    return True
```

- [ ] **Step 4: テストが通ることを確認する**

Run: discover コマンド
Expected: `OK`（58 tests）

- [ ] **Step 5: コミットする**

```bash
cd /Users/yohira/Documents/Obsidian-Vault
git add 00_Claude/scripts/claude_daily_log/daily.py 00_Claude/scripts/claude_daily_log/tests/test_daily.py
git commit -m "feat(daily-log): Daily ノートの管理ブロック更新を追加"
```

---

### Task 6: CLI の sync とロック・ログ（cli.py）

**Files:**
- Create: `00_Claude/scripts/claude_daily_log/tests/test_cli_sync.py`
- Create: `00_Claude/scripts/claude_daily_log/cli.py`

**Interfaces:**
- Consumes: `projects.list_projects`, `sources.collect_entries`, `sources.dedupe`, `mirror.update_mirror`, `daily.update_daily`
- Produces:
  - `DEFAULT_VAULT`, `DEFAULT_GIT_ROOT`, `LOCK_PATH`, `STAMP_PATH`, `LOG_PATH`, `FETCH_INTERVAL_SECONDS`
  - `run_sync(vault: str, git_root: str, date: str) -> Dict`（キー: `date`, `sources`, `entries`, `mirror_added`, `mirror_replaced`, `daily_changed`, `warnings`）
  - `format_report(report: Dict) -> str`
  - `acquire_lock() -> Optional[IO]`
  - `setup_logging() -> None`
  - `main(argv=None) -> int`（常に 0）

Task 7 で `main` に `fetch` / `auto` を足すため、このタスクでは `sync` のみを実装する。

- [ ] **Step 1: 失敗するテストを書く**

`00_Claude/scripts/claude_daily_log/tests/test_cli_sync.py`:

```python
import os
import tempfile
import unittest

import cli
from tests import helpers

CONV = """# 会話ログ

## 2026-09-06 当日のまとめ

当日の本文。

## 2026-09-05 前日のまとめ

前日の本文。
"""

TABLE = """| プロジェクト名 | 相対フォルダー | 内容 |
| - | - | - |
| repo_a | ../repo_a | テスト用 |
| repo_b | ../repo_b | 未 clone |
"""


class RunSyncTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.git_root = os.path.join(self.tmp.name, "git")
        self.vault = os.path.join(self.tmp.name, "vault")
        os.makedirs(os.path.join(self.git_root, "alphasystem"))
        os.makedirs(self.vault)
        with open(os.path.join(self.git_root, "alphasystem", "CLAUDE.md"), "w", encoding="utf-8") as handle:
            handle.write(TABLE)
        origin = helpers.init_repo(os.path.join(self.tmp.name, "origin_a"), {"conversations.md": CONV})
        helpers.clone_repo(origin, os.path.join(self.git_root, "repo_a"))

    def tearDown(self):
        self.tmp.cleanup()

    def read_daily(self, date="2026-09-06"):
        path = os.path.join(self.vault, "01_Daily", date + ".md")
        with open(path, encoding="utf-8") as handle:
            return handle.read()

    def test_sync_writes_daily_and_mirror(self):
        report = cli.run_sync(self.vault, self.git_root, "2026-09-06")
        self.assertEqual(report["entries"], 1)
        self.assertTrue(report["daily_changed"])
        self.assertIn("当日のまとめ", self.read_daily())
        mirror_path = os.path.join(self.vault, "00_Claude", "projects", "repo_a.md")
        self.assertTrue(os.path.exists(mirror_path))

    def test_second_run_produces_no_diff(self):
        cli.run_sync(self.vault, self.git_root, "2026-09-06")
        before = self.read_daily()
        report = cli.run_sync(self.vault, self.git_root, "2026-09-06")
        self.assertEqual((report["mirror_added"], report["mirror_replaced"]), (0, 0))
        self.assertFalse(report["daily_changed"])
        self.assertEqual(self.read_daily(), before)

    def test_date_option_regenerates_past_day(self):
        cli.run_sync(self.vault, self.git_root, "2026-09-05")
        self.assertIn("前日のまとめ", self.read_daily("2026-09-05"))

    def test_uncloned_project_is_skipped_without_error(self):
        report = cli.run_sync(self.vault, self.git_root, "2026-09-06")
        self.assertEqual(report["warnings"], [])

    def test_missing_vault_is_reported_and_does_not_raise(self):
        report = cli.run_sync(os.path.join(self.tmp.name, "no_vault"), self.git_root, "2026-09-06")
        self.assertTrue(any("Vault" in warning for warning in report["warnings"]))

    def test_main_returns_zero(self):
        code = cli.main(["sync", "--date", "2026-09-06", "--vault", self.vault, "--git-root", self.git_root])
        self.assertEqual(code, 0)
        self.assertIn("当日のまとめ", self.read_daily())

    def test_report_option_prints_summary(self):
        report = cli.run_sync(self.vault, self.git_root, "2026-09-06")
        text = cli.format_report(report)
        self.assertIn("2026-09-06", text)
        self.assertIn("1", text)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: テストが失敗することを確認する**

Run: discover コマンド
Expected: `ModuleNotFoundError: No module named 'cli'`

- [ ] **Step 3: 実装する**

`00_Claude/scripts/claude_daily_log/cli.py`:

```python
#!/usr/bin/env python3
"""Claude Code の会話まとめを Obsidian の Daily ノートへ同期する。"""
import argparse
import datetime
import fcntl
import logging
import os
import sys
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import daily as daily_module
import mirror as mirror_module
import projects as projects_module
import sources as sources_module

DEFAULT_VAULT = os.path.expanduser("~/Documents/Obsidian-Vault")
DEFAULT_GIT_ROOT = os.path.expanduser("~/git")
LOCK_PATH = os.path.expanduser("~/.claude/cache/claude_daily_log.lock")
STAMP_PATH = os.path.expanduser("~/.claude/cache/claude_daily_log.fetch_stamp")
LOG_PATH = os.path.expanduser("~/.claude/logs/claude_daily_log.log")
LOG_MAX_BYTES = 1024 * 1024
FETCH_INTERVAL_SECONDS = 30 * 60


def setup_logging() -> None:
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        if os.path.exists(LOG_PATH) and os.path.getsize(LOG_PATH) > LOG_MAX_BYTES:
            os.replace(LOG_PATH, LOG_PATH + ".1")
        logging.basicConfig(
            filename=LOG_PATH,
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(message)s",
        )
    except OSError:
        logging.basicConfig(level=logging.CRITICAL)


def acquire_lock() -> Optional[object]:
    """取得できたらファイルオブジェクト、他プロセスが実行中なら None を返す。"""
    try:
        os.makedirs(os.path.dirname(LOCK_PATH), exist_ok=True)
        handle = open(LOCK_PATH, "w")
    except OSError:
        return None
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        return None
    return handle


def run_sync(vault: str, git_root: str, date: str) -> Dict:
    report = {
        "date": date,
        "sources": 0,
        "entries": 0,
        "mirror_added": 0,
        "mirror_replaced": 0,
        "daily_changed": False,
        "warnings": [],
    }
    if not os.path.isdir(vault):
        report["warnings"].append("Vault が見つかりません: %s" % vault)
        return report

    collected: List = []
    for project in projects_module.list_projects(git_root):
        if not project.exists:
            continue
        try:
            entries, warnings = sources_module.collect_entries(project.path, project.name, date)
        except Exception as error:  # git 失敗も含めてスキップする
            report["warnings"].append("%s: 収集に失敗しました (%s)" % (project.name, error))
            continue
        collected.extend(entries)
        report["warnings"].extend(warnings)

    entries = sources_module.dedupe(collected)
    by_source: Dict[str, List] = {}
    for entry in entries:
        by_source.setdefault(entry.source_id, []).append(entry)

    for source_id in sorted(by_source):
        try:
            added, replaced = mirror_module.update_mirror(vault, source_id, by_source[source_id])
        except OSError as error:
            report["warnings"].append("%s: ミラー更新に失敗しました (%s)" % (source_id, error))
            continue
        report["mirror_added"] += added
        report["mirror_replaced"] += replaced

    try:
        report["daily_changed"] = daily_module.update_daily(vault, date, entries)
    except daily_module.DailyMarkerError as error:
        report["warnings"].append("Daily の管理ブロックが壊れています: %s" % error)
    except OSError as error:
        report["warnings"].append("Daily 更新に失敗しました (%s)" % error)

    report["sources"] = len(by_source)
    report["entries"] = len(entries)
    logging.info(
        "sync date=%s sources=%d entries=%d added=%d replaced=%d daily_changed=%s warnings=%d",
        date, report["sources"], report["entries"], report["mirror_added"],
        report["mirror_replaced"], report["daily_changed"], len(report["warnings"]),
    )
    return report


def format_report(report: Dict) -> str:
    lines = [
        "対象日: %s" % report["date"],
        "プロジェクト %d 件 / エントリ %d 件" % (report["sources"], report["entries"]),
        "ミラー: 追加 %d / 置換 %d" % (report["mirror_added"], report["mirror_replaced"]),
        "Daily: %s" % ("更新しました" if report["daily_changed"] else "変更なし"),
    ]
    if report.get("fetched") is not None:
        lines.insert(1, "GitHub 同期: fetch %d / clone %d" % (report.get("fetched", 0), report.get("cloned", 0)))
    if report["warnings"]:
        lines.append("警告 %d 件:" % len(report["warnings"]))
        lines.extend("  - " + warning for warning in report["warnings"])
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Claude Code の会話まとめを Obsidian に同期する")
    parser.add_argument("command", choices=["sync"])
    parser.add_argument("--date", default=None, help="対象日 (YYYY-MM-DD)。既定は今日")
    parser.add_argument("--vault", default=os.environ.get("CLAUDE_DAILY_LOG_VAULT", DEFAULT_VAULT))
    parser.add_argument("--git-root", default=os.environ.get("CLAUDE_DAILY_LOG_GIT_ROOT", DEFAULT_GIT_ROOT))
    parser.add_argument("--report", action="store_true", help="結果を標準出力に表示する")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    setup_logging()
    date = args.date or datetime.date.today().isoformat()

    lock = acquire_lock()
    if lock is None:
        logging.info("他プロセスが実行中のため終了します")
        if args.report:
            print("他プロセスが実行中のためスキップしました")
        return 0
    try:
        report = run_sync(args.vault, args.git_root, date)
        if args.report:
            print(format_report(report))
    finally:
        lock.close()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # hook からの起動でも必ず 0 で終わる
        logging.exception("予期しないエラー")
        sys.exit(0)
```

- [ ] **Step 4: テストが通ることを確認する**

Run: discover コマンド
Expected: `OK`（65 tests）

- [ ] **Step 5: 実 Vault に対して dry run 相当の確認をする（コミット前に diff を見る）**

```bash
python3 /Users/yohira/Documents/Obsidian-Vault/00_Claude/scripts/claude_daily_log/cli.py sync --report
git status --short && git diff -- 01_Daily 00_Claude/projects | head -60
```

Expected: `01_Daily/2026-09-06.md` と `00_Claude/projects/*.md` が生成され、既存の手書き行が消えていないこと。想定外の差分があればここで停止して報告する。

- [ ] **Step 6: コミットする**

```bash
cd /Users/yohira/Documents/Obsidian-Vault
git add 00_Claude/scripts/claude_daily_log/cli.py 00_Claude/scripts/claude_daily_log/tests/test_cli_sync.py
git add 00_Claude/projects 01_Daily
git commit -m "feat(daily-log): sync サブコマンドと排他ロック・ログを追加"
```

---

### Task 7: GitHub 同期（gitsync.py）と auto サブコマンド

**Files:**
- Create: `00_Claude/scripts/claude_daily_log/tests/test_gitsync.py`
- Create: `00_Claude/scripts/claude_daily_log/gitsync.py`
- Modify: `00_Claude/scripts/claude_daily_log/cli.py`（`build_parser` の `choices`、`main` の分岐、`_fetch_due` / `_touch_stamp` を追加）

**Interfaces:**
- Consumes: `projects.list_projects`, `projects.Project`
- Produces:
  - `CLONE_URL_TEMPLATE: str` = `"https://github.com/alphacmc/%s.git"`
  - `MAX_WORKERS: int` = 8
  - `run_fetch(git_root: str, items: Optional[List[Project]] = None) -> Dict`（キー: `fetched`, `cloned`, `warnings`）
  - cli 側: `main` が `sync` / `fetch` / `auto` を受け付ける。`auto` は前回 fetch から 30 分以上経過、または `--force-fetch` 指定時のみ fetch してから sync する。

- [ ] **Step 1: 失敗するテストを書く**

`00_Claude/scripts/claude_daily_log/tests/test_gitsync.py`:

```python
import os
import tempfile
import time
import unittest

import cli
import gitsync
import projects
from tests import helpers


class RunFetchTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.origin = helpers.init_repo(os.path.join(self.tmp.name, "origin"), {"conversations.md": "# x\n"})
        self.work = helpers.clone_repo(self.origin, os.path.join(self.tmp.name, "work"))

    def tearDown(self):
        self.tmp.cleanup()

    def test_fetches_existing_clone(self):
        report = gitsync.run_fetch(self.tmp.name, [projects.Project(name="work", path=self.work)])
        self.assertEqual(report["fetched"], 1)
        self.assertEqual(report["warnings"], [])

    def test_new_remote_branch_becomes_visible_after_fetch(self):
        helpers.commit_on_branch(self.origin, "feature/x", {"conversations.md": "# y\n"})
        gitsync.run_fetch(self.tmp.name, [projects.Project(name="work", path=self.work)])
        refs = helpers.subprocess.run(
            ["git", "-C", self.work, "for-each-ref", "--format=%(refname:short)", "refs/remotes/origin"],
            capture_output=True, text=True, check=True,
        ).stdout
        self.assertIn("origin/feature/x", refs)

    def test_missing_project_is_cloned(self):
        # ネットワークに出ないよう、clone 元をローカルパスに差し替える
        original = gitsync.CLONE_URL_TEMPLATE
        gitsync.CLONE_URL_TEMPLATE = os.path.join(self.tmp.name, "%s")
        try:
            target = projects.Project(name="origin", path=os.path.join(self.tmp.name, "cloned"))
            report = gitsync.run_fetch(self.tmp.name, [target])
        finally:
            gitsync.CLONE_URL_TEMPLATE = original
        self.assertEqual(report["cloned"], 1)
        self.assertTrue(os.path.isdir(os.path.join(self.tmp.name, "cloned", ".git")))

    def test_clone_failure_is_reported_as_warning(self):
        original = gitsync.CLONE_URL_TEMPLATE
        gitsync.CLONE_URL_TEMPLATE = os.path.join(self.tmp.name, "no_such_%s")
        try:
            missing = projects.Project(name="ghost", path=os.path.join(self.tmp.name, "missing"))
            report = gitsync.run_fetch(self.tmp.name, [missing])
        finally:
            gitsync.CLONE_URL_TEMPLATE = original
        self.assertEqual(report["cloned"], 0)
        self.assertEqual(len(report["warnings"]), 1)
        self.assertIn("ghost", report["warnings"][0])


class FetchDueTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.stamp = os.path.join(self.tmp.name, "stamp")
        self._original = cli.STAMP_PATH
        cli.STAMP_PATH = self.stamp

    def tearDown(self):
        cli.STAMP_PATH = self._original
        self.tmp.cleanup()

    def test_due_when_stamp_missing(self):
        self.assertTrue(cli._fetch_due())

    def test_not_due_right_after_touch(self):
        cli._touch_stamp()
        self.assertFalse(cli._fetch_due())

    def test_due_when_stamp_is_old(self):
        cli._touch_stamp()
        old = time.time() - cli.FETCH_INTERVAL_SECONDS - 1
        os.utime(self.stamp, (old, old))
        self.assertTrue(cli._fetch_due())


if __name__ == "__main__":
    unittest.main()
```

補足: `helpers.subprocess` を使うため、`helpers.py` の先頭で `import subprocess` 済みであることを利用する（Task 3 で作成済み）。

- [ ] **Step 2: テストが失敗することを確認する**

Run: discover コマンド
Expected: `ModuleNotFoundError: No module named 'gitsync'`

- [ ] **Step 3: gitsync.py を実装する**

`00_Claude/scripts/claude_daily_log/gitsync.py`:

```python
"""GitHub との同期（未 clone プロジェクトの clone と並列 fetch）。"""
import concurrent.futures
import subprocess
from typing import Dict, List, Optional, Tuple

import projects as projects_module

CLONE_URL_TEMPLATE = "https://github.com/alphacmc/%s.git"
MAX_WORKERS = 8
FETCH_TIMEOUT = 60
CLONE_TIMEOUT = 300


def _fetch_one(path: str) -> Tuple[bool, str]:
    try:
        proc = subprocess.run(
            ["git", "-C", path, "fetch", "--quiet", "--prune", "origin"],
            capture_output=True, timeout=FETCH_TIMEOUT,
        )
    except (OSError, subprocess.SubprocessError) as error:
        return (False, str(error))
    if proc.returncode != 0:
        return (False, proc.stderr.decode("utf-8", "replace").strip())
    return (True, "")


def run_fetch(git_root: str, items: Optional[List] = None) -> Dict:
    """未 clone は clone し、clone 済みは並列に fetch する。失敗は warnings に積む。"""
    report = {"fetched": 0, "cloned": 0, "warnings": []}
    targets = items if items is not None else projects_module.list_projects(git_root)

    for project in [item for item in targets if not item.exists]:
        try:
            proc = subprocess.run(
                ["git", "clone", "--quiet", CLONE_URL_TEMPLATE % project.name, project.path],
                capture_output=True, timeout=CLONE_TIMEOUT,
            )
        except (OSError, subprocess.SubprocessError) as error:
            report["warnings"].append("%s: clone に失敗しました (%s)" % (project.name, error))
            continue
        if proc.returncode != 0:
            report["warnings"].append(
                "%s: clone に失敗しました (%s)" % (project.name, proc.stderr.decode("utf-8", "replace").strip())
            )
            continue
        report["cloned"] += 1

    present = [item for item in targets if item.exists]
    if present:
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            futures = {pool.submit(_fetch_one, item.path): item for item in present}
            for future in concurrent.futures.as_completed(futures):
                project = futures[future]
                ok, message = future.result()
                if ok:
                    report["fetched"] += 1
                else:
                    report["warnings"].append("%s: fetch に失敗しました (%s)" % (project.name, message))
    return report
```

- [ ] **Step 4: cli.py に fetch / auto を足す**

`cli.py` の import に追加:

```python
import gitsync as gitsync_module
import time
```

`build_parser` の該当行を差し替える:

```python
    parser.add_argument("command", choices=["sync", "fetch", "auto"])
    parser.add_argument("--force-fetch", action="store_true", help="auto でも必ず fetch する")
```

`acquire_lock` の下に追加:

```python
def _fetch_due() -> bool:
    try:
        return (time.time() - os.path.getmtime(STAMP_PATH)) >= FETCH_INTERVAL_SECONDS
    except OSError:
        return True


def _touch_stamp() -> None:
    try:
        os.makedirs(os.path.dirname(STAMP_PATH), exist_ok=True)
        with open(STAMP_PATH, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(datetime.datetime.now().isoformat())
    except OSError:
        pass
```

`main` の `try:` ブロックを次に差し替える:

```python
    try:
        fetch_report = None
        if args.command == "fetch" or (args.command == "auto" and (args.force_fetch or _fetch_due())):
            fetch_report = gitsync_module.run_fetch(args.git_root)
            _touch_stamp()
            logging.info(
                "fetch fetched=%d cloned=%d warnings=%d",
                fetch_report["fetched"], fetch_report["cloned"], len(fetch_report["warnings"]),
            )
        report = run_sync(args.vault, args.git_root, date)
        if fetch_report is not None:
            report["fetched"] = fetch_report["fetched"]
            report["cloned"] = fetch_report["cloned"]
            report["warnings"] = fetch_report["warnings"] + report["warnings"]
        if args.report:
            print(format_report(report))
    finally:
        lock.close()
```

- [ ] **Step 5: テストが通ることを確認する**

Run: discover コマンド
Expected: `OK`（72 tests）

- [ ] **Step 6: 実データで auto を実行し、所要時間と差分を確認する**

```bash
time python3 /Users/yohira/Documents/Obsidian-Vault/00_Claude/scripts/claude_daily_log/cli.py auto --force-fetch --report
cd /Users/yohira/Documents/Obsidian-Vault && git status --short
```

Expected: 未 clone の `coopcdeweb` / `coopcdeinput` / `coopcdealert` が `~/git` に clone され、全体が 60 秒以内に終わること。警告があれば内容を確認する。

- [ ] **Step 7: コミットする**

```bash
cd /Users/yohira/Documents/Obsidian-Vault
git add 00_Claude/scripts/claude_daily_log
git add 00_Claude/projects 01_Daily
git commit -m "feat(daily-log): GitHub 同期(clone/fetch)と auto サブコマンドを追加"
```

---

### Task 8: SessionEnd hook とスラッシュコマンドの導入

**Files:**
- Modify: `~/.claude/settings.json`（既存キーを保ったまま `hooks.SessionEnd` を追加）
- Create: `~/.claude/commands/daily-sync.md`
- Modify: `00_Claude/specs/2026-09-06-daily-claude-log-sync-design.md`（該当 0 件かつ Daily 未作成なら作らない挙動を追記）
- Create: `00_Claude/scripts/claude_daily_log/README.md`

**Interfaces:**
- Consumes: `cli.py`（`auto` サブコマンド）
- Produces: なし（設定の導入のみ）

- [ ] **Step 1: settings.json のバックアップを取る**

```bash
cp ~/.claude/settings.json ~/.claude/settings.json.bak
python3 -c "import json;print(json.load(open('/Users/yohira/.claude/settings.json')).keys())"
```

Expected: `dict_keys(['model', 'enabledPlugins', 'extraKnownMarketplaces', 'theme'])`

- [ ] **Step 2: hook を追記する（既存キーは保持）**

```bash
python3 - <<'PY'
import json

path = "/Users/yohira/.claude/settings.json"
with open(path, encoding="utf-8") as handle:
    settings = json.load(handle)

command = (
    'nohup /usr/bin/python3 '
    '"$HOME/Documents/Obsidian-Vault/00_Claude/scripts/claude_daily_log/cli.py" auto '
    '>/dev/null 2>&1 &'
)
hooks = settings.setdefault("hooks", {})
entries = hooks.setdefault("SessionEnd", [])
if not any(command in json.dumps(entry, ensure_ascii=False) for entry in entries):
    entries.append({"hooks": [{"type": "command", "command": command, "timeout": 10}]})

with open(path, "w", encoding="utf-8", newline="\n") as handle:
    json.dump(settings, handle, ensure_ascii=False, indent=2)
    handle.write("\n")
print(json.dumps(settings["hooks"], ensure_ascii=False, indent=2))
PY
```

Expected: `SessionEnd` に 1 エントリだけが登録された JSON が表示される。

- [ ] **Step 3: hook のコマンドが単体で動くことを確認する**

```bash
/usr/bin/python3 "$HOME/Documents/Obsidian-Vault/00_Claude/scripts/claude_daily_log/cli.py" auto --report
tail -3 ~/.claude/logs/claude_daily_log.log
```

Expected: hook が実行するのと同じコマンド（`auto`）が正常終了し、ログに `sync date=... entries=...` 行が追記されている。
バックグラウンド起動そのものは Step 9 の実セッション確認で検証する。

- [ ] **Step 4: スラッシュコマンドを作る**

```bash
mkdir -p ~/.claude/commands
cat > ~/.claude/commands/daily-sync.md <<'MD'
---
description: Claude Code の会話まとめを Obsidian の Daily ノートへ同期する
---

次のコマンドを Bash ツールで実行し、出力された同期結果をそのまま報告してください。
警告行がある場合は省略せずに伝えること。日付を引数で受け取った場合は `--date` に渡すこと。

/usr/bin/python3 "$HOME/Documents/Obsidian-Vault/00_Claude/scripts/claude_daily_log/cli.py" auto --force-fetch --report

引数: $ARGUMENTS
MD
ls -l ~/.claude/commands/daily-sync.md
```

Expected: ファイルが作成される。

- [ ] **Step 5: 使い方 README を Vault 側に置く**

`00_Claude/scripts/claude_daily_log/README.md`:

```markdown
# claude_daily_log

各リポジトリの `conversations.md` から当日分の会話まとめを収集し、
`00_Claude/projects/<プロジェクト>.md`（ミラー）と `01_Daily/YYYY-MM-DD.md`（サマリ）へ反映する。

## 使い方

```bash
# ローカルのみを走査して Daily を更新（1 秒未満）
python3 00_Claude/scripts/claude_daily_log/cli.py sync --report

# GitHub と同期してから更新（未 clone プロジェクトの clone も行う）
python3 00_Claude/scripts/claude_daily_log/cli.py auto --force-fetch --report

# 過去日をやり直す
python3 00_Claude/scripts/claude_daily_log/cli.py sync --date 2026-09-01 --report
```

Claude Code のセッション終了時には SessionEnd hook（`~/.claude/settings.json`）が
`auto` をバックグラウンド起動する。前回 fetch から 30 分以上経っていれば GitHub 同期も行う。
手動実行はスラッシュコマンド `/daily-sync`。

## 注意

- Daily ノートの更新対象は `<!-- claude-log:start -->` 〜 `<!-- claude-log:end -->` の間だけ。手書き部分は変更しない。
- 対象プロジェクトは `~/git/alphasystem/CLAUDE.md` と `~/git/coop/CLAUDE.md` の構成テーブルから決まる。
- 日付なしの `## ` 見出しは取り込まれない。`/daily-sync` の警告に件数が出る。

## テスト

```bash
python3 -m unittest discover \
  -s 00_Claude/scripts/claude_daily_log/tests \
  -t 00_Claude/scripts/claude_daily_log -v
```
```

- [ ] **Step 6: 設計書の該当箇所を実装に合わせて更新する**

`00_Claude/specs/2026-09-06-daily-claude-log-sync-design.md` の「5. Daily の出力仕様」にある
「Daily ノートが存在しない場合は、`## Claude作業ログ` とマーカーブロックのみのファイルを新規作成する。」の直後に次の 1 行を追加する。

```markdown
- ただし対象日の該当が 0 件かつ Daily ノートが存在しない場合は、空のノートを作らない。
```

- [ ] **Step 7: 全テストを再実行する**

Run: discover コマンド
Expected: `OK`（72 tests）

- [ ] **Step 8: コミットする**

```bash
cd /Users/yohira/Documents/Obsidian-Vault
git add 00_Claude/scripts/claude_daily_log/README.md 00_Claude/specs/2026-09-06-daily-claude-log-sync-design.md
git add 00_Claude/projects 01_Daily
git commit -m "docs(daily-log): README と設計書の補足を追加"
```

- [ ] **Step 9: 実セッションでの動作を確認する**

別の VSCode プロジェクト（例: `~/git/coopinf`）で Claude Code のセッションを開始・終了し、
`~/.claude/logs/claude_daily_log.log` に新しい `sync` 行が増えること、
`01_Daily/2026-09-06.md` の管理ブロックが最新化されることを確認する。

```bash
tail -5 ~/.claude/logs/claude_daily_log.log
sed -n '/claude-log:start/,/claude-log:end/p' /Users/yohira/Documents/Obsidian-Vault/01_Daily/2026-09-06.md
```

Expected: 管理ブロックに当日分のリンクが並ぶ。Obsidian で Daily を開き、リンクをクリックしてミラーノートの該当見出しへ飛べることを目視確認する。

---

## 完了条件

- 全 72 テストが green。
- `01_Daily/2026-09-06.md` に手書き部分を保ったまま `## Claude作業ログ` ブロックが生成される。
- `00_Claude/projects/*.md` のリンクが Obsidian 上で該当見出しへ遷移する。
- 別プロジェクトのセッション終了で Daily が自動更新される。
- `/daily-sync` が同期結果と警告を報告する。
