# conversations

## 2026-08-24 obsidian-git コンフリクト対処

### 事象
- ルートに `conflict-files-obsidian-git.md`（obsidian-git がコンフリクト時に自動生成する案内ファイル）が出現。
- `main` と `origin/main` が枝分かれし、`.obsidian/workspace.json` がマージ未解決状態だった。

### 根本原因
1. `.gitignore` が UTF-16 LE で保存されており、git が UTF-8 として読めずパターンが無効化。`.obsidian/workspace.json` の除外が効いていなかった。
2. `workspace.json` は既に追跡（tracked）済みだったため、`.gitignore` に書いても除外されなかった（gitignore は未追跡ファイルのみ有効）。

### 対処
1. `git checkout --ours` で workspace.json のコンフリクトをローカル採用し解決。
2. `git rm --cached .obsidian/workspace.json` で追跡解除（実体ファイルは保持）。
3. `.gitignore` を UTF-8（BOMなし・LF）で再作成（内容: `.obsidian/workspace.json` 1行）。
   - 注意: Claudian の Write ツールは UTF-16 LE で書き込むため、bash の `printf ... > .gitignore` で UTF-8 化した。
4. `conflict-files-obsidian-git.md` を削除。
5. コミット `ce08938` を作成し `origin/main` へ push。作業ツリー clean。

### 検証
- `git check-ignore -v .obsidian/workspace.json` → `.gitignore:1` にマッチ（ignore 有効）。
- `git ls-files --error-unmatch` → exit 1（追跡解除成功）。

### 備考
- obsidian-git は main を直接同期する運用のため、本対応は feature ブランチを切らず main 上で実施。
- 今後 `.gitignore` を編集する際は UTF-8（BOMなし）で保存すること。

## 2026-08-24 RTX1300 / XS508TM 一発適用スクリプトの可否と作成

### 結論
- **RTX1300**: 一発適用スクリプト（設定コマンドのテキスト）は作成可能。コンソール貼付/TFTP転送/USB起動で投入できる。
- **XS508TM**: Smart Managed Pro スイッチでCLI流し込み不可。設定はWeb GUI/NETGEAR Insight。一括適用は「GUIで1台設定→.cfgバックアップ→他機へリストア」のクローン方式のみ。手書きスクリプトは不可。

### 作成物（config_RTX1300.md を正として連結）
- `config/config_RTX1300_full.txt` … 全13章を投入順に連結した統合版（286行）。プレースホルダ `<...>` は投入前に実値へ置換。
- `config/config_RTX1300_staged.txt` … 章ごとにSTEP分割し、各STEP後に `# 確認:`（show系/疎通観点）を併記した切替当日用（219行）。

### 注意点（設計ノート由来）
- LAN2 は必ず `ra-prefix@lan2`（RA方式）。`dhcp-prefix@` はIPv4不通。
- VLAN間フィルタは静的passを動的filterより前に置く順序厳守。VLAN間pingは通らない設計（TCPで疎通確認）。
- L2TP は tunnel 1000 をひな型に 1001〜1004 の展開が要確定（TODO）。
- AWS拠点間VPN（11章）は切替当日スコープ外。AWSコンソールのYamaha向け設定を正とする。
- ファイルはUTF-8。git push 済み（commit 1f52559）。

### 補足
- Claudian の Write ツールはファイルにより UTF-16 になる場合があるため、投入用テキストは UTF-8 を確認して保存すること。

## 2026-08-25 RTX1300 ファームウェアRev確認・反映
- `show environment` のログより **Rev.23.00.17（2025-10-03ビルド）** を確認。
  - 該当行: `RTX1300 Rev.23.00.17 (Fri Oct  3 09:45:39 2025)`
  - 機体: serial=S78053841 / MAC f4:d5:80:3b:60:de〜e5
- 設計要件「Rev.23.00.17以降」を**満たす**（下限そのもの）。
- `config_RTX1300.md` 13章のファーム行を「未確認」→「確認済（Rev.23.00.17 / 2025-10-03ビルド、2026-08-25確認）」へ更新。

## 2026-09-06 Claude Code の会話まとめを Obsidian Daily へ自動反映する仕組みを構築

### 背景・目的

複数の VSCode プロジェクトで Claude Code と作業しており、その結論は各リポジトリの `conversations.md`
（グローバル CLAUDE.md のルール）に溜まっていた。これを Vault の Daily ノートへ集約したい。
各セッションは互いを認識できないが、**全セッションが同じ Daily を共有し、終了のたびに全プロジェクトを
走査してブロックを作り直す**ことで、結果的にセッション間が連動する構成にした。

### 決めたこと

- Daily には 1 行サマリ（`conversations.md` の見出し）＋ Vault 内ミラーノートへの見出しリンクだけを置く。
  本文は `00_Claude/projects/<プロジェクト>.md` にミラーする。
- 収集元はローカルクローン。GitHub の内容はリモート追跡ブランチ全部から拾い、
  未 commit のローカル作業ツリーを優先する。`fetch` は前回成功から 30 分でスロットル。
- 対象プロジェクトは `~/git/alphasystem/CLAUDE.md` と `~/git/coop/CLAUDE.md` の構成テーブルから決める（16 件）。
- 起動は SessionEnd hook（自動）と `/daily-sync`（手動）の併用。

### 調査で判明した実データの事情

- `conversations.md` はリポジトリ直下とは限らない（`docs/` 配下、`alphabsmail/docs/` 配下にも存在）。
  1 リポジトリに 2 ファイルある例（alphasystem）もあるため、ファイル単位で別プロジェクト扱いにした。
- 見出しの書式が 4 種類混在していた。日付範囲（`## 2026-08-28〜31 …`）は**終了日**に割り当てる方針とした。
- 日付なし見出しは取り込まず、警告として件数だけ報告する（推測はしない）。

### レビューで見つかり修正した重大な問題

1. **探索失敗時に Daily が警告なしで空になる**。`~/git/coop` で CLAUDE.md の無いブランチを
   チェックアウトしているだけで発火し、obsidian-git がその削除を他 PC へ伝播しうる。
   → 走査が失敗した場合は Daily を触らず警告する（`daily_skipped`）。該当 0 件との区別を明確化。
2. **書き込みが非アトミック**。hook はセッション終了時＝PC シャットダウン直前に走るため、
   途中で落ちると手書きの Daily が空・途中で壊れる。→ 一時ファイル＋ `os.replace` に変更。
3. **fetch が例外を投げると sync ごとスキップ**されていた（実ログに発生記録あり）。→ 分離。
4. **Daily のマーカーが片方だけ残った状態で 2 回実行すると手書き部分ごと消える**。
   → マーカー状態を検証し、異常なら書き換えずに `DailyMarkerError`。
5. `import fcntl` が無防備で **Windows では import 時点で落ちる**。
   → ガードし、`O_CREAT|O_EXCL` ロックファイルにフォールバック。

### 成果物

- 本体: `00_Claude/scripts/claude_daily_log/`（Python 3.9 標準ライブラリのみ、108 テスト）
- 設計書: `00_Claude/specs/2026-09-06-daily-claude-log-sync-design.md`
- 実装計画: `00_Claude/plans/2026-09-06-daily-claude-log-sync.md`
- hook とスラッシュコマンドは `claude-config` で複数 PC 共有（Draft PR #1）。
  hook は macOS/Windows(Git Bash) 両対応、Vault の場所は `CLAUDE_DAILY_LOG_VAULT` で上書き可。

### 残作業

- SessionEnd hook はこのセッション開始後に登録したため、`/hooks` を開くか再起動するまで有効にならない。
- 実セッションでの発火確認（別プロジェクトでセッションを開始・終了する）は未実施。

## 2026-09-07 Daily 反映の仕様変更（1ブロック化・as-of 表示）と運用確定

### 変更点

- Daily の管理ブロックを**プロジェクト単位の1リスト**に統合。日別サブセクション（この日の作業）は廃止。
  各行はそのプロジェクトの「対象日以前で最新の記録」を指す（as-of 表示）。朝は前日以前の最新が並び、
  その日のセッションで記録ができればその行が当日日付に変わる。
- 並び順は alpha グループ → 空行 → coop グループ → 空行 → その他。各グループの先頭は
  傘プロジェクト（alphasystem / coop）で固定。
- `--date` で過去日を再生成しても、その日より後の記録は出さない。
- **Daily ノートはツールから新規作成しない**（毎朝テンプレートから作る運用を尊重）。
  未作成の日は `daily_missing` として報告するだけ。

### 運用（確定）

- 朝: Daily を作成したあと `/daily-sync`（または `cli.py sync --report`）を手動実行する。
- 日中: セッション終了ごとに SessionEnd hook が自動更新する。
- 定時実行や SessionStart hook は**導入しない**と判断した（仕組みを増やさない方針）。

### 付随して入れたもの

- `~/.claude/keybindings.json`: Enter=改行 / Ctrl+J・Option+Enter=送信。書きかけプロンプトの誤送信対策。
  誤送信時は Esc で中断。claude-config の PR #2（Draft）で複数PC共有。
- claude-config PR #1（マージ済み）: SessionEnd hook と `/daily-sync` を管理対象に追加。
  hook は macOS/Windows(Git Bash) 両対応、Vault の場所は `CLAUDE_DAILY_LOG_VAULT` で上書き可。

### 反省点

- claude-config へ追加コミットする際、対象 PR が既にマージ済みかを push 前に確認しなかった。
  マージ済みブランチにコミットしてしまい、PR #2 に切り出して復旧した。

