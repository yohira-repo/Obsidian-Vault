# claude_daily_log

各リポジトリの `conversations.md` から当日分の会話まとめを収集し、
`00_Claude/projects/<プロジェクト>.md`（ミラー）と `01_Daily/YYYY-MM-DD.md`（サマリ）へ反映する。

## 使い方

    # ローカルのみを走査して Daily を更新（1 秒未満）
    python3 00_Claude/scripts/claude_daily_log/cli.py sync --report

    # GitHub と同期してから更新（未 clone プロジェクトの clone も行う。10 秒程度）
    python3 00_Claude/scripts/claude_daily_log/cli.py auto --force-fetch --report

    # 過去日をやり直す
    python3 00_Claude/scripts/claude_daily_log/cli.py sync --date 2026-09-01 --report

Claude Code のセッション終了時には SessionEnd hook（`~/.claude/settings.json`）が
`auto` をバックグラウンド起動する。前回 fetch から 30 分以上経っていれば GitHub 同期も行う。
手動実行はスラッシュコマンド `/daily-sync`。

## 対象の決め方

- 対象プロジェクトは `~/git/alphasystem/CLAUDE.md` と `~/git/coop/CLAUDE.md` の構成テーブルから決まる
  （相対フォルダーが `../` の行のみ。`./` 始まりは配下ディレクトリなので対象外）。
- `conversations.md` はリポジトリ内の任意の深さを探索する（`docs/` 配下、サブプロジェクト配下も対象）。
  ソース識別子はパスから `docs` を除いて作る（`alphabsmail/docs/conversations.md` → `alphasystem/alphabsmail`）。
- ローカル作業ツリー（未 commit 分を含む）とリモート追跡ブランチ全部を見て、同じ見出しはローカルを優先する。

## 見出しの扱い

| 書き方 | 結果 |
| - | - |
| `## 2026-09-06 タイトル` | そのまま当日分 |
| `## 2026-09-06: タイトル` | 同上 |
| `## 2026-09-06 — タイトル` | 同上 |
| `## 2026-08-28〜31 タイトル` | **終了日**（2026-08-31）の分として扱う |
| `## タイトル`（日付なし） | 取り込まない。`/daily-sync` の警告に件数が出る |

## 注意

- Daily ノートの更新対象は `<!-- claude-log:start -->` 〜 `<!-- claude-log:end -->` の間だけ。手書き部分は変更しない。
- マーカーが片方だけ・順序が逆・重複している場合は、**ファイルを一切書き換えずに警告**を出す（手動で直すこと）。
- 常に終了コード 0 で終わる。失敗は警告としてログ（`~/.claude/logs/claude_daily_log.log`）に残る。
- 複数セッションが同時に終了しても `fcntl.flock` で排他される。

## テスト

    python3 -m unittest discover \
      -s 00_Claude/scripts/claude_daily_log/tests \
      -t 00_Claude/scripts/claude_daily_log -v
