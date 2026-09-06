# Claude Code 会話まとめの Daily ページ反映（設計）

作成日: 2026-09-06

## 1. 目的

複数の VSCode プロジェクトで行っている Claude Code との会話の結論（各リポジトリの `conversations.md`）を、
Obsidian Vault の Daily ノート（`01_Daily/YYYY-MM-DD.md`）へ自動的に集約する。

各セッションは互いを認識できないが、**全セッションが同じ Daily ファイルを共有し、
終了のたびに全プロジェクトを走査して該当ブロックを作り直す**ことで、結果としてセッション間が連動する。

## 2. 前提（調査で確認済みの事実）

- グローバル CLAUDE.md のルールにより、各リポジトリに `conversations.md` が蓄積されている。
- **配置はリポジトリ直下とは限らない。**全リモートブランチを横断調査した結果、次の 3 パターンが存在する。

  | リポジトリ | パス |
  | - | - |
  | alphacdk / coopinf / coopcdebatch / coopbatch | `conversations.md` |
  | alphasystem | `docs/conversations.md` |
  | alphasystem | `alphabsmail/docs/conversations.md`（1 リポジトリに 2 ファイル） |

- 見出しは 4 パターンが混在する。
  - `## 2026-07-22 CSVバッチ処理のログ出力見直し（提案）`（空白区切り）
  - `## 2026-08-20: gas_bill.option_fee_code_1 埋め戻し — prd適用結果の記録`（コロン区切り）
  - `## 2026-08-12 — 営業メールのやりとりの可視化（brainstorming 開始）`（em ダッシュ区切り）
  - `## 経営層向け説明資料（PowerPoint）の作成`（日付なし。alphabsmail では 11 セクション中 4 件）
- 本文はおおむね日付昇順で末尾に追記されている。
- `conversations.md` は git 追跡下にあり GitHub（`alphacmc/*`）へ push 済み。ただし更新は
  feature ブランチ上に載ることが多く、デフォルトブランチだけを見ると当日分を取りこぼす。
- 対象プロジェクト一覧は `~/git/alphasystem/CLAUDE.md` と `~/git/coop/CLAUDE.md` のテーブルから機械的に取得できる（17 件）。
  - うちこの PC に clone 済みは 13 件、未 clone は coopcdeweb / coopcdeinput / coopcdealert。
  - `alphabsmail` は相対フォルダーが `./alphabsmail` で独立リポジトリではない。
- 13 リポジトリの並列 `git fetch` は実測 3.0 秒。
- Claude Code の SessionEnd hook はインストール済みバイナリで対応を確認済み。
- `~/.claude` は git 管理外。Vault は git 管理下（obsidian-git が main を直接同期）。

## 3. 構成要素

| # | 実体 | 役割 |
| - | - | - |
| A | `00_Claude/scripts/claude_daily_log.py`（Vault 内・git 管理） | 本体。python3 標準ライブラリのみ |
| B | `~/.claude/settings.json` の SessionEnd hook | 全プロジェクト共通の自動起動 |
| C | `~/.claude/commands/daily-sync.md` | 手動実行用スラッシュコマンド |

スクリプトを Vault 内に置く理由: git 管理され、obsidian-git 経由で他 PC にも同じツールが同期されるため。

### サブコマンド

- `fetch` … 未 clone プロジェクトを `~/git/` へ clone し、全対象リポジトリを並列 `git fetch --prune`（ネットワーク要、約 3 秒）
- `sync` … ローカルのみ走査して Vault を更新（ネットワーク不要、1 秒未満）

## 4. データフロー

0. **対象日の決定**
   既定はローカル時刻（JST）の当日。`--date YYYY-MM-DD` で明示指定でき、過去日の再生成にも使える。
1. **プロジェクト一覧の決定**
   `~/git/alphasystem/CLAUDE.md` と `~/git/coop/CLAUDE.md` の Markdown テーブルをパースし、
   相対フォルダー列が `../` で始まる行のみ独立リポジトリとして採用する（`./` 始まりは配下ディレクトリなので除外）。
2. **conversations.md の探索**（リポジトリごと・任意の深さ）
   - リモート: `refs/remotes/origin/*` の各ブランチを `git ls-tree -r --name-only` で走査し、
     ベース名が `conversations.md` のパスをすべて対象にする。
   - ローカル: `git ls-files` と `git ls-files --others --exclude-standard`（未追跡分）を同様に走査する。
   - `node_modules/` `dist/` `build/` `.next/` `vendor/` 配下は除外する。
3. **ソース識別子の決定**
   パスのディレクトリ部分から `docs` セグメントを取り除き、残りをリポジトリ名に連結する。
   - `conversations.md` → `coopinf`
   - `docs/conversations.md` → `alphasystem`
   - `alphabsmail/docs/conversations.md` → `alphasystem/alphabsmail`
   ファイル単位で独立したプロジェクトとして扱い、Daily の行もミラーノートも分ける。
4. **収集**（ソースごと）
   - ベース: リモート追跡ブランチの内容（＝GitHub の内容。他 PC の作業を含む）
   - 上書き: ローカル作業ツリーの内容（未 commit 分。同一キーならこちらを優先）
   - 同一 blob SHA は 1 回だけ解析する。
5. **抽出**
   正規表現 `^##\s+(\d{4}-\d{2}-\d{2})\s*(?:[:：\-—–]\s*)?(.+)$` で見出しを認識し（空白 / コロン / em ダッシュ区切りに対応）、
   対象日に一致するセクションを次の `## ` 見出しの直前まで本文ごと切り出す。
   日付を持たない `## ` 見出しはスキップし、「日付なし見出し N 件（ファイルパス）」を警告としてログと
   `/daily-sync` の報告に出す。日付の推測（直前見出しからの継承、git blame 等）は行わない。
6. **重複排除**
   キーは `(ソース識別子, 日付, 正規化タイトル)`。正規化はタイトル前後の空白と末尾コロンの除去。
   優先順位はローカル作業ツリー > コミット日時の新しいブランチ。
7. **ミラー出力**
   `00_Claude/projects/<ソース識別子のスラッシュを - に置換>.md` に、未収録のセクションのみを本文ごと末尾追記する。
   （例: `alphasystem/alphabsmail` → `00_Claude/projects/alphasystem-alphabsmail.md`）
   ファイルが無ければ `# <ソース識別子> 作業ログ` を先頭に付けて新規作成する。
   見出しは `## YYYY-MM-DD タイトル` 形式に正規化する（Daily からの見出しリンクを一意にするため）。
   既に同じキーが収録済みで本文だけが変化している場合（同じ日のうちに追記された場合）は、
   該当セクションの範囲だけを新しい本文で置換する。収録順は変えない。
   Obsidian の見出しリンクを壊さないため、タイトル中の `#` `|` `[` `]` は全角に置換してから見出しに書く。
   ミラーノートも Daily と同様に、手書きで加筆された箇所（管理対象セクション外）は変更しない。
8. **Daily 出力**
   `01_Daily/YYYY-MM-DD.md` の管理ブロックのみを毎回再生成する。

## 5. Daily の出力仕様

```markdown
## Claude作業ログ
<!-- claude-log:start -->
- **alphasystem/alphabsmail** — [[00_Claude/projects/alphasystem-alphabsmail#2026-09-06 営業メール可視化 Track1 の実装計画見直し|営業メール可視化 Track1 の実装計画見直し]]
- **coopinf** — [[00_Claude/projects/coopinf#2026-09-06 CFテンプレートの日本語コメントがコンソールで文字化けする件|CFテンプレートの日本語コメントがコンソールで文字化けする件]]
<!-- claude-log:end -->
```

- 1 行サマリは `conversations.md` の見出しタイトルをそのまま使う。
- 並び順はソース識別子の昇順、同一ソース内は `conversations.md` の出現順。
- 更新対象は `<!-- claude-log:start -->` と `<!-- claude-log:end -->` の間だけ。手書き部分は読み書きとも一切変更しない。
- Daily ノートが存在しない場合は、`## Claude作業ログ` とマーカーブロックのみのファイルを新規作成する。
- Daily ノートは存在するがマーカーが無い場合は、ファイル末尾に `## Claude作業ログ` ごと追加する。
- 対象日の該当が 0 件の場合はマーカーブロックを空にする（見出しとマーカーは残す）。

## 6. hook / コマンドの挙動

- SessionEnd hook は `sync` をバックグラウンドで起動し、hook 自体は即座に exit 0 する（セッション終了を遅らせない）。
- 前回 `fetch` 成功から 30 分以上経過している場合に限り、同じバックグラウンド処理内で `fetch` を先に実行する。
  最終実行時刻は `~/.claude/cache/claude_daily_log.fetch_stamp` に保持する。
- `/daily-sync` は `fetch` と `sync` を続けて実行し、結果（更新されたリポジトリ数・追加行数）を報告する。

## 7. 異常系

- Vault が存在しない、書き込み権限が無い、git コマンド失敗、オフライン → 該当分のみスキップし、常に exit 0。
- 同時実行は `fcntl.flock`（`~/.claude/cache/claude_daily_log.lock`）で排他し、ロックを取得できなければ即終了する。
  Daily は毎回全再生成なので、取りこぼしは次回実行で回復する。
- 未 clone リポジトリの clone に失敗した場合は警告のみ記録し、他リポジトリの処理を継続する。
- ファイル入出力は UTF-8 固定（BOM なし・LF）。Claudian の Write が UTF-16 で書く問題を避けるため、生成・追記は本スクリプトから行う。
- 動作ログは `~/.claude/logs/claude_daily_log.log` に追記し、1 MB を超えたら 1 世代ローテートする。

## 8. テスト

python3 標準の unittest で実装し、ネットワークには接続しない。
一時ディレクトリにダミーの git リポジトリ・CLAUDE.md・Vault を構築して検証する。

- CLAUDE.md テーブルのパース（`../` 採用 / `./` 除外 / 見出し行除外）
- 任意の深さの `conversations.md` の探索（直下 / `docs/` 配下 / `<サブ>/docs/` 配下、`node_modules/` 除外）
- ソース識別子の生成（`docs` セグメント除去、1 リポジトリ 2 ファイルが別プロジェクトとして分かれること）
- 見出し 3 形式（空白 / コロン / em ダッシュ区切り）の抽出
- 日付なし `## ` 見出しがスキップされ、警告として件数が報告されること
- セクション本文が次の `## ` 直前まで正しく切り出されること
- Daily 新規作成
- 既存 Daily の手書き部分が保持されること
- マーカーが無い既存 Daily への追加
- 同じ入力で 2 回実行して差分が出ないこと（冪等性）
- 同じキーのセクション本文が増えた場合に、ミラー側の該当セクションだけが置換されること
- タイトルに `#` `|` `[` `]` を含む場合に見出しがサニタイズされ、Daily のリンクが壊れないこと
- `--date` 指定で過去日を再生成できること
- リモートブランチとローカル作業ツリーで内容が異なる場合にローカルが優先されること
- 該当 0 件の日にマーカーブロックが空になること
- `conversations.md` を持たないリポジトリのスキップ
- 未 clone・git 失敗時に exit 0 で終了すること

## 9. スコープ外

- Daily の手書きタスクと Claude 作業ログの突き合わせ・統合
- conversations.md 自体の書式統一やリライト
- Vault の自動 commit / push（obsidian-git に委ねる）
