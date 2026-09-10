#!/bin/sh
# claude_daily_log クロスプラットフォーム起動ラッパー
#
# 目的:
#   Windows では `command -v python3` が Microsoft Store のスタブ
#   (…\WindowsApps\python3) に当たり、実行しても何もせず終了するため、
#   SessionEnd hook が無言で空振りする問題があった。
#   ここでは「実際に Python を実行できるコマンド」だけを選び（スタブは
#   検証で弾かれる）、cli.py を起動する。Windows / macOS 双方で同一に動く。
#
# 使い方:
#   sh run.sh              # 既定で `auto`（GitHub同期→Daily更新）
#   sh run.sh sync         # ローカルのみ
#   sh run.sh auto --force-fetch --report
#
# 環境変数:
#   CLAUDE_DAILY_LOG_VAULT  … Vault ルート（既定 $HOME/Documents/Obsidian-Vault）
set -u

VAULT="${CLAUDE_DAILY_LOG_VAULT:-$HOME/Documents/Obsidian-Vault}"
CLI="$VAULT/00_Claude/scripts/claude_daily_log/cli.py"
[ -f "$CLI" ] || exit 0

# 実際に動く Python を選ぶ（Store スタブや python2 は検証で除外）。
#   - python3 : macOS/Linux では実体。Windows では Store スタブのことがある。
#   - python  : Windows では実体（C:\PythonXX\python.exe）のことが多い。
#   - py      : Windows の Python ランチャー。macOS には無い。
PY=""
for c in python3 python py; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c "import sys" >/dev/null 2>&1; then
    PY="$c"
    break
  fi
done
[ -n "$PY" ] || exit 0

# 引数が無ければ auto。あればそのまま渡す。
if [ "$#" -eq 0 ]; then
  exec "$PY" "$CLI" auto
else
  exec "$PY" "$CLI" "$@"
fi
