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
