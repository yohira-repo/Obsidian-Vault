"""conversations.md の見出し・セクション解析。"""
import re
from dataclasses import dataclass
from datetime import date
from typing import List, Optional, Tuple

ANY_H2_RE = re.compile(r"^##\s+(.*)$")
DATED_H2_RE = re.compile(r"^##\s+(\d{4}-\d{2}-\d{2})\s*(?:[:：\-—–]\s*)?(.+?)\s*$")
RANGE_H2_RE = re.compile(
    r"^##\s+(\d{4})-(\d{2})-(\d{2})[〜~](\d{4}-\d{2}-\d{2}|\d{2}-\d{2}|\d{2})"
    r"\s*(?:[:：\-—–]\s*)?(.+?)\s*$"
)

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


def _resolve_range_end(start_y: int, start_m: int, start_d: int, end_raw: str) -> Optional[str]:
    """範囲見出しの終了日を解決する。終了日が不正なら None を返す。"""
    start = date(start_y, start_m, start_d)

    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", end_raw):
        end_y, end_m, end_d = (int(part) for part in end_raw.split("-"))
        adjust_year = False
    elif re.fullmatch(r"\d{2}-\d{2}", end_raw):
        end_m, end_d = (int(part) for part in end_raw.split("-"))
        end_y = start_y
        adjust_year = True
    else:
        end_d = int(end_raw)
        end_m = start_m
        end_y = start_y
        adjust_year = True

    try:
        end = date(end_y, end_m, end_d)
    except ValueError:
        return None

    if adjust_year and end < start:
        end_y += 1
        try:
            end = date(end_y, end_m, end_d)
        except ValueError:
            return None

    return end.isoformat()


def scan_headings(lines: List[str]) -> List[Tuple[int, Optional[str], Optional[str]]]:
    """`## ` 見出しを (行番号, 日付 or None, 正規化タイトル or None) の一覧にする。"""
    heads = []
    for index, line in enumerate(lines):
        if not ANY_H2_RE.match(line):
            continue
        range_matched = RANGE_H2_RE.match(line)
        if range_matched:
            start_y, start_m, start_d, end_raw, raw_title = range_matched.groups()
            resolved = _resolve_range_end(int(start_y), int(start_m), int(start_d), end_raw)
            date_value = resolved if resolved is not None else f"{start_y}-{start_m}-{start_d}"
            heads.append((index, date_value, normalize_title(raw_title)))
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
