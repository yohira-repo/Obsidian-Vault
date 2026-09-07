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

## 2026-09-07 会話の決定・段取りが記録されずに流れる問題への対策（hook 導入）

### 事象

coopinf の Phase 4 カットオーバーで 9/7・9/8 の段取りを会話で何度も詰めたが、
`conversations.md` に残ったのは本筋から外れた CloudFormation 文字化けの件だけだった。

### 原因

自動トリガー（Stop hook）を持つ `migration/LEARNINGS.md` だけが埋まり、
宣言的ルールに委ねた `conversations.md` は「完結した調査の結論」しか拾えていなかった。
9/7・9/8 の段取りは**未完了の合意**であるため「結論」と判定されず落ちた。
CLAUDE.md の文言強化だけでは不十分（Draft PR ルールが明文化済みでも3日連続で守られなかった前例がある）。

### 決定事項

| 論点 | 決定 | 日付 |
| - | - | - |
| 記録すべき対象 | 「日付付きの実行段取り」と「会話で確定した決定・合意」の2つ。進捗チェックボックスと全文要約は対象外 | 2026-09-07 |
| 実現方式 | グローバル hook 2本を `claude-config` で版管理し `~/.claude/hooks/record/` に配置。リポジトリ個別配置は却下（`settings.local.json` が gitignore されており他PCで消えるため） | 2026-09-07 |
| 計画ファイルの特定 | 自動検出は却下。`.claude/active-plan` で明示宣言する（自動検出は完了済みの残骸や古い計画を拾うことを実測で確認） | 2026-09-07 |
| `active-plan` の形式 | **複数行**（1行1パス）。`#` コメント・空行・実在しないパスは無視するため、更新漏れでも壊れない | 2026-09-07 |
| 適用範囲 | 全リポジトリ + **Obsidian Vault も含める**（プログラム以外の作業系を Vault の Note で管理しているため） | 2026-09-07 |
| ECC 生成物 | `claude-config/claude/hooks/` 配下の everything-claude-code 生成物は**削除する** | 2026-09-07 |
| 改行コード | repo・実機とも **LF に統一**し、`.gitattributes` の `* text=auto eol=lf` で再発を防ぐ | 2026-09-07 |
| 実行方式 | Subagent-Driven（タスクごとに実装者とレビュアーを立てる） | 2026-09-07 |

### 成果物

- `~/.claude/hooks/record/lib.sh` … パス解決の共通処理
- `~/.claude/hooks/record/session-start-context.sh` … `LEARNINGS.md` と実行中計画の未完了 Step を注入（1ファイル20件 / 合計60件が上限）
- `~/.claude/hooks/record/stop-record-decisions.sh` … 毎ターン3観点を自問させる
- `~/.claude/settings.json` に SessionStart / Stop を登録（既存の SessionEnd 同期は維持）
- `~/.claude/CLAUDE.md` の記録ルールを「結論」から「決定・合意・日付付き段取り」へ具体化

設計書は `00_Claude/specs/2026-09-07-decision-record-hooks-design.md`、
実装計画は `00_Claude/plans/2026-09-07-decision-record-hooks.md`。

### レビューで見つかった欠陥（すべて計画に書いたコードの不良）

1. `cp` により repo 側 `CLAUDE.md` が LF から CRLF に退行
2. `find_records` の `sed "s|^${root}/||"` が、パスに `[` `]` を含むと絶対パスを返し `|` を含むとコマンド自体が失敗
3. Stop hook が、受け皿が部分的にしか無いリポジトリで存在しないファイルへ案内し項番が 1→3 に飛ぶ

いずれもテストが通っている状態で潜んでいた。レビューを挟まなければそのまま入っていた。

### 限界（合意済み）

hook が保証するのは「毎ターン必ず判定が走る」ことであり、書き込みの強制ではない。
記録すべきかの最終判断は Claude 側に残る。

### 検証状況

- Stop hook … **2026-09-07 のこの会話で実発火を確認**（本エントリがその成果物）
- SessionStart hook … 新セッションでの発火確認が未実施（ユーザー確認待ち）

## 2026-09-07 sync.ps1 が Windows PowerShell でパースエラーになる件

### 事象

Windows で `.\sync.ps1 push` を実行するとパースエラーで起動しない。
日本語コメントが `蛛ｴ繧剃ｸ頑嶌縺搾ｼ` のように化けていた。

### 根本原因: BOM 無し UTF-8 を CP932 として読んでいた

`sync.ps1` は UTF-8 で BOM が無く、Windows PowerShell 5.1 は BOM の無いスクリプトを
ANSI コードページ（日本語環境では CP932）として読む。

単なる文字化けにとどまらないのがポイント。CP932 は2バイト文字の先行バイトを見ると
**次の1バイトを必ず後続バイトとして取り込む**。このファイルには行末が CP932 先行バイトに
なる行が9箇所（1, 3, 4, 7, 9, 16, 22, 57, 95行目）あり、そこで**改行そのものが
文字の一部として飲み込まれ、行が連結**される。結果コメントとコードが混ざりパーサーが崩壊した。

報告されたエラー行番号が、飲み込まれた改行数を差し引いた予測と完全一致したことで確定:

| 箇所 | ファイル上の実際の行 | CP932誤読時の予測 | 報告 |
| - | - | - | - |
| `[string]$Direction,` | 14 | 9 | 9 |
| `$label = "$RepoStore...` | 50 | 43 | 43 |
| `$state = if (Test-Path...` | 68 | 60 | 60 |

### 決定: ASCII 化（2026-09-07 ユーザー判断）

| 案 | 採否 | 理由 |
| - | - | - |
| 日本語を ASCII 化 | **採用** | エンコーディングに一切依存しなくなる |
| UTF-8 BOM を付与 | 不採用 | 日本語は残せるが BOM の有無に依存し続ける |
| pwsh 7 で実行する運用 | 不採用 | 5.1 で実行すると再発する余地が残る |

ロジックは変更していない（文字列リテラルの中身を除いた正規化比較で84行すべて一致）。
唯一の実質変更は書式幅 `{0,-8}` → `{0,-9}`（`'上書き'` 3文字が `'overwrite'` 9文字になったため）。
再発防止に `tests/test-ascii-only.sh` を追加（旧版に対しては21行検出して落ちる）。

PR #6（`fix/sync-ps1-ascii`）。hook 本体の PR #5 とは無関係のため別ブランチに分離した。

### 判明したこと: この不具合は最初から存在していた

- BOM は初回コミット `1c25add` から一度も付いていない
- `.gitattributes` 追加の前後で `sync.ps1` の blob は同一（`6f75f674`）で1バイトも変わっていない

つまり今回の hook 導入作業とは無関係。これまで動いていたとすれば PowerShell 7（`pwsh`）で
実行されていたはず（7 は既定が UTF-8）。

### 残課題

- Windows での実動作確認（この Mac に PowerShell が無いため未検証）
- Windows 側の `core.autocrlf` 設定の確認（実機 `~/.claude/CLAUDE.md` は git 管理外のため、
  `sync.ps1 push` で再び CRLF 化する余地がある）
