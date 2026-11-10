# 計画: プロジェクト状況表のPRベース化（GitHub基準）

作成: 2026-11-10 / 対象: `00_Claude/scripts/claude_daily_log`（Vault）＋ `alphasystem/.claude/hooks/project-status.sh`

## 目的
「プロジェクト状況」表を、ローカルHEAD基準から **GitHub の open PR 基準** に変更する。
各 open PR のブランチを行として表示（複数PR→複数行）。どのPCで生成しても同じ内容になる。

## 確定仕様
- 取得: `gh pr list --repo alphacmc/<name> --state open --json number,title,headRefName,baseRefName,isDraft,updatedAt`
  - 12リポジトリでも並列化すれば 1〜2 秒（直列実測: 6件で約3.7秒）。認証は `yohira-repo` で確認済み。
- 行の出し方:
  - **open PR あり**: PR ごとに 1 行。
    - ブランチ列: `headRefName`（`#番号`、Draft印、`→ baseRefName`）
    - 最終コミット: fetch 済み `origin/<headRefName>` の `%cr`（日本語化）/`%s`（40字切詰・`|`エスケープ）
    - 未コミット/未push: そのリポジトリのローカル値（同一リポの複数PR行では各行に同値）
    - 最新の記録列: 従来どおり（mirror 見出しへのリンク）
  - **open PR なし**: 1 行。ブランチ列=`PRなし`、最終コミット=`origin/staging`（無ければ `origin/main`）の時刻。
  - 未clone / git管理外 / 同居(alphasystem内) / 取得失敗: 従来の `_plain` 行を維持。
- **gh 不可時**（未認証/オフライン/未導入）: 警告を出し、**現行ローカル基準表示にフォールバック**（壊さない）。フォールバック単位は既定で**リポジトリ単位**。
- 維持する既存仕様: alpha/coop/その他のグループ化、傘プロジェクト（alphasystem/coop）先頭固定、「最新の記録」統合列、`|` エスケープ、内容不変時の時刻行据え置き。

## 既定（未指定だったので既定を採用。変更希望あれば差し替え）
- 列ヘッダ: `ブランチ` → `PR / ブランチ` に改名（PR番号・ブランチ・base を含むため）。
- gh フォールバック単位: リポジトリ単位。

## 影響ファイルと PR（2本）
- **PR-X（Vault, `feature/status-pr-based`, base=main）**
  - `status.py`: データモデルを「プロジェクト→PR行リスト」に拡張。`gh` 呼び出し（並列）＋ `origin/<branch>` 読み＋フォールバック。
  - `daily.py`: 複数行レンダリング、ブランチ列/最終コミット列の意味変更、PRなし行、ヘッダ改名。
  - `cli.py`: 収集ワイヤリング（必要なら）。
  - `tests/`: `test_status.py`・`test_daily.py`・`test_cli_sync.py` の追加/改修（gh はスタブ/モック）。
  - `README.md`: 仕様追記。
- **PR-Y（alphasystem, `feature/project-status-pr-based`, base=staging）**
  - `.claude/hooks/project-status.sh` を同仕様に（正本は Python 版。両者整合を保つ）。

## 実行順序
1. PR-X（Vault 側）を TDD で実装 → テスト緑 → Draft PR。
2. 挙動確定後、PR-Y（bash 版）を同仕様で実装 → Draft PR。
3. Draft 解除・マージは利用者。

## リスク/留意
- `gh` 依存とネットワークが status 収集に加わる（従来はローカルのみ）。フォールバックで緩和。
- fork 由来 PR のブランチは `origin/<headRefName>` に無い場合がある → その行の最終コミットは `gh` の `updatedAt` 等で代替（社内運用は同一リポブランチ中心のため影響小）。
- 非 force の通常実行では origin ref が最大30分古い可能性（既存仕様どおり）。
