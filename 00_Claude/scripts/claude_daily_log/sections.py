"""conversations.md の見出し・セクション解析。"""
import re
from dataclasses import dataclass
from datetime import date
from typing import List, Optional, Tuple

ANY_H2_RE = re.compile(r"^##\s+(.*)$")
FENCE_RE = re.compile(r"^\s{0,3}(`{3,}|~{3,})(.*)$")
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


def _resolve_range_end(start: date, end_raw: str) -> Optional[str]:
    """範囲見出しの終了日を解決する。終了日が不正なら None を返す。

    終了日の指定形式によって、開始日より前になった場合の繰り上げ単位が異なる。
    - 年月日がすべて指定された場合: 繰り上げなし（そのまま採用）。
    - 月日のみ指定された場合（年は開始日から補う）: 年を繰り上げる。
    - 日のみ指定された場合（年月は開始日から補う）: 月を繰り上げる
      （12月なら翌年の1月になる）。
    """
    start_y = start.year

    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", end_raw):
        end_y, end_m, end_d = (int(part) for part in end_raw.split("-"))
        rollover = "none"
    elif re.fullmatch(r"\d{2}-\d{2}", end_raw):
        end_m, end_d = (int(part) for part in end_raw.split("-"))
        end_y = start_y
        rollover = "year"
    else:
        end_d = int(end_raw)
        end_m = start.month
        end_y = start_y
        rollover = "month"

    try:
        end = date(end_y, end_m, end_d)
    except ValueError:
        return None

    if rollover == "year" and end < start:
        end_y += 1
        try:
            end = date(end_y, end_m, end_d)
        except ValueError:
            return None
    elif rollover == "month" and end < start:
        end_m += 1
        if end_m > 12:
            end_m = 1
            end_y += 1
        try:
            end = date(end_y, end_m, end_d)
        except ValueError:
            return None

    return end.isoformat()


def _parse_calendar_date(y: str, m: str, d: str) -> Optional[date]:
    """カレンダー上実在する日付なら date を、そうでなければ None を返す。"""
    try:
        return date(int(y), int(m), int(d))
    except ValueError:
        return None


def scan_headings(lines: List[str]) -> List[Tuple[int, Optional[str], Optional[str]]]:
    """`## ` 見出しを (行番号, 日付 or None, 正規化タイトル or None) の一覧にする。

    開始日がカレンダー上実在しない場合（例: 2026-13-45）は、同期処理を
    決して例外で落とさないため、日付なし見出しとして扱う。

    ``` / ~~~ のフェンスコードブロック内にある `## ` 始まりの行は見出しと
    みなさない（開始フェンスの記号種別・長さを閉じフェンスと照合し、
    情報文字列（```python 等）も許容する）。
    """
    heads = []
    in_fence = False
    fence_char = ""
    fence_len = 0
    for index, line in enumerate(lines):
        if in_fence:
            closing = FENCE_RE.match(line)
            if closing:
                fence, info = closing.groups()
                if fence[0] == fence_char and len(fence) >= fence_len and info.strip() == "":
                    in_fence = False
            continue

        opening = FENCE_RE.match(line)
        if opening:
            fence, _info = opening.groups()
            in_fence = True
            fence_char = fence[0]
            fence_len = len(fence)
            continue

        if not ANY_H2_RE.match(line):
            continue
        range_matched = RANGE_H2_RE.match(line)
        if range_matched:
            start_y, start_m, start_d, end_raw, raw_title = range_matched.groups()
            start = _parse_calendar_date(start_y, start_m, start_d)
            if start is None:
                heads.append((index, None, None))
                continue
            resolved = _resolve_range_end(start, end_raw)
            date_value = resolved if resolved is not None else start.isoformat()
            heads.append((index, date_value, normalize_title(raw_title)))
            continue
        matched = DATED_H2_RE.match(line)
        if matched:
            date_str = matched.group(1)
            try:
                date.fromisoformat(date_str)
            except ValueError:
                heads.append((index, None, None))
                continue
            heads.append((index, date_str, normalize_title(matched.group(2))))
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
