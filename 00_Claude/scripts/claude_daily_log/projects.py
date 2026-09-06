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
