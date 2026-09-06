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
