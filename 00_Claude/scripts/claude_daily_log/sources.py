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
