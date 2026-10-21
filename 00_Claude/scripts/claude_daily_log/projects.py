"""CLAUDE.md の構成テーブルから対象プロジェクト一覧を得る。"""
import os
import re
from dataclasses import dataclass
from typing import List, Sequence, Tuple

ROW_RE = re.compile(r"^\s*\|\s*([A-Za-z0-9_.-]+)\s*\|\s*(\.{1,2}/[^|]+?)\s*\|")

DEFAULT_CONFIG_FILES = ("alphasystem/CLAUDE.md", "coop/CLAUDE.md")

KIND_REPO = "repo"
KIND_NESTED = "nested"


@dataclass(frozen=True)
class Project:
    name: str
    path: str
    kind: str = KIND_REPO

    @property
    def is_nested(self) -> bool:
        """構成表で `./` 配下に置かれた同居ディレクトリ（独立リポジトリではない）。"""
        return self.kind == KIND_NESTED

    @property
    def exists(self) -> bool:
        if self.is_nested:
            # 同居は .git を持たない。ディレクトリの有無で判定する。
            return os.path.isdir(self.path)
        return os.path.isdir(os.path.join(self.path, ".git"))


def parse_project_table(text: str) -> List[Tuple[str, str]]:
    """構成表の行を (名前, 相対パス) で返す。

    `../` 行は独立リポジトリ、`./` 行は同居ディレクトリ。重複名は初出を優先する。
    """
    rows: List[Tuple[str, str]] = []
    seen = set()
    for line in text.splitlines():
        matched = ROW_RE.match(line)
        if not matched:
            continue
        name = matched.group(1)
        if name in seen:
            continue
        seen.add(name)
        rows.append((name, matched.group(2)))
    return rows


def list_projects(git_root: str, config_files: Sequence[str] = DEFAULT_CONFIG_FILES) -> List[Project]:
    """プロジェクト一覧（名前昇順）。重複名は初出優先。

    相対パスは、その CLAUDE.md が置かれたリポジトリのディレクトリ基準で解決する
    （`./alphabsmail` は `<git_root>/alphasystem/alphabsmail`）。

    並び順は呼び出し側の要件ではない（状況一覧は描画側で傘プロジェクトを先頭に
    並べ替える）。従来どおり名前昇順で返す。
    """
    found: List[Project] = []
    seen = set()
    for relative in config_files:
        config_path = os.path.join(git_root, relative)
        owner_dir = os.path.dirname(config_path)
        try:
            with open(config_path, encoding="utf-8") as handle:
                text = handle.read()
        except OSError:
            continue
        for name, rel_path in parse_project_table(text):
            if name in seen:
                continue
            seen.add(name)
            kind = KIND_NESTED if rel_path.startswith("./") else KIND_REPO
            path = os.path.normpath(os.path.join(owner_dir, rel_path))
            found.append(Project(name=name, path=path, kind=kind))
    return sorted(found, key=lambda project: project.name)
