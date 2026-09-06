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
