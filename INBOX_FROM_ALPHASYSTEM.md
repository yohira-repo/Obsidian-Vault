# alphasystem からの申し送り（読んだら自分の記録に取り込み、このファイルを削除してください）

- 送付日時: 2026-10-21
- 送付元: alphasystem セッション（alphasystem-eb）
- 件名: デイリーノートに alpha 系・coop 系の「プロジェクト状況」表を /daily-sync で自動更新する機能の実装依頼

## 状況

設計は確定済み（brainstorming 完了、ユーザー承認済み、alphasystem PR #97 でマージ）。
brainstorming は不要で、**実装計画の作成から**始めてください。
SendMessage でも送りましたが届いていないとのことで、このファイルでも申し送ります（内容は同一）。

## 参照

- 設計書: `/Users/yohira/git/alphasystem/docs/design/2026-10-21-Obsidianデイリーノート-プロジェクト状況一覧-仕様.md`
- 決定の経緯: `/Users/yohira/git/alphasystem/docs/conversations/2026-10-21.md`
- 参考実装（判定条件と表記の元、bash）: `/Users/yohira/git/alphasystem/.claude/hooks/project-status.sh`（先頭コメントに整合ルール追記済み、PR #99）

## 実装先: `00_Claude/scripts/claude_daily_log`（Python）

- `status.py` 新規: 両 CLAUDE.md の構成表（既存 `projects.py`）から各リポジトリの ブランチ / ⚠upstream消失・(未push) / 未コミット N件 / 最終コミット（相対時刻の日本語化、件名 40 文字切り詰め、`|` エスケープ）を取得。1 リポジトリの失敗は「（取得失敗）」行で続行
- `projects.py`: 構成表の `./` 行（alphabsmail）を「同居」種別として保持できるよう `Project` に種別を追加（表示は「alphasystem内」、リンクなし）
- `daily.py`: 見出し「## プロジェクト状況」＋ `<!-- project-status:start -->` / `<!-- project-status:end -->` のマーカー区間。位置は「## Claude作業ログ」の直前（初回はその直前に挿入、無ければ末尾）。`### alpha` / `### coop` の表 2 つ、各グループ先頭は傘プロジェクト（alphasystem / coop）、以降は構成表順。プロジェクト名は `[[00_Claude/projects/<name>|<name>]]`。表の下に「（YYYY-MM-DD HH:MM 時点）」
- `cli.py`: 全体同期（sync/auto）のみで更新（`--project` 単体同期では更新しない）。順序は fetch → 記録収集 → ミラー更新 → 状況収集 → デイリー更新。状況収集の失敗は作業ログを止めず警告。作業ログと状況一覧は 1 回の原子的書き込み（既存 `atomicio`）。`--report` に「状況一覧: 更新しました / 変更なし / 取得失敗 N 件」を追加
- テスト（既存 unittest に追加）と README 追記
- 判定条件・表記は bash 版と同一にし、`status.py` 先頭に「正本は Python 版、変更時は bash 版にも同じ変更」を明記

不明点や契約の変更があれば alphasystem-eb へ SendMessage、または alphasystem リポジトリ直下に `INBOX_FROM_OBSIDIAN.md` を置いてください。
