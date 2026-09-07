# 決定・段取りの記録漏れを防ぐ hook 群（設計）

作成日: 2026-09-07

## 1. 目的

Claude Code との会話で確定した **「日付付きの実行段取り」** と **「決定・合意」** が、
どのファイルにも残らないまま流れてしまう事象を、機械的なトリガーによって防ぐ。

対象外（今回のスコープに含めない）:

- 計画ファイルのチェックボックス進捗の自動更新
- 会話全文の要約ダンプ

## 2. 発端となった事象（2026-09-07）

coopinf の `migration/cutover-plan.md`（Phase 4 カットオーバー）Task 4 について、
9/7 に何をやるか・9/8 に何をやるかを会話で何度も詰めたにもかかわらず、
`conversations.md` に残っていたのは本筋から外れた **CloudFormation の文字化けの件だけ**だった。

## 3. 原因分析（実測に基づく）

### 3.1 自動トリガーを持つ受け皿だけが埋まっていた

| 受け皿 | 役割 | 書き込みトリガー | 実態 |
| - | - | - | - |
| `migration/LEARNINGS.md` | 学び | **Stop hook で毎ターン強制的に促される** | 9/8 の曜日誤記まで細かく記録されている |
| `conversations.md` | 結論 | グローバル CLAUDE.md の宣言的ルールのみ | 完結した調査の結論しか残らない |
| `migration/cutover-plan.md` | 計画・進捗 | executing-plans のチェックボックス | Task 4 の Step 1〜3 が未チェックのまま |

hook（`.claude/hooks/stop-learnings-reflect.sh`）が存在する `LEARNINGS.md` のみが機能していた。

### 3.2 「結論」という発火条件が狭すぎた

文字化けの件は「調査 → A案採用 → 完結」であり、"結論が出た" と判定されて記録された。
一方 9/7・9/8 の段取りは **未完了の合意** であるため "結論" と見なされず、
さらに「`cutover-plan.md` に実施予定として書いてあるから重複記録は不要」と判断されて落ちた。

実際に migration 配下に残っていたのは `cutover-plan.md:184` の
`実施予定: 2026-09-07(月) 日中帯` の 1 行のみで、会話で詰めた時系列の段取りは失われていた。

### 3.3 宣言的ルールの強化だけでは不十分

`00_Claude/projects/coopinf.md`（2026-08-20 のセッション履歴分析）に、
「Draft PR 自動作成ルールは明文化されているのに 3 日連続で守られず、適用が不安定」という
実測記録がある。CLAUDE.md の文言強化のみでは同種の再発をする。

## 4. 調査で確認した制約

### 4.1 リポジトリ個別に hook を配る方式は破綻する

- 対象 5 リポジトリ × スクリプト 2 本 = 10 ファイルの多重管理になる
- coopinf の hook 登録先 `.claude/settings.local.json` は **gitignore されている**
  （`coopinf/.gitignore:57`）。別 PC・再 clone で設定が消える
- 一方 `~/.claude/settings.json` と `~/.claude/hooks/` は `claude-config` リポジトリで
  版管理されており、`sync.ps1` で複数 PC に配布できる。
  既に SessionEnd hook（daily log sync）が同居している実績がある

### 4.2 アクティブな計画ファイルは自動検出できない

`*plan*.md` を機械的に走査した実測値:

| リポジトリ | ファイル | 未チェック数 | 実態 |
| - | - | - | - |
| coopinf | `migration/cutover-plan.md` | 19 | **本命** |
| coopinf | `migration/verify-backfill-plan.md` | 9 | 実質完了済みの残骸 |
| coopinf | `migration/plan.md` | 0 | チェックボックスなし |
| alphasystem | `docs/design/2026-07-29-secret-management-migration-plan.md` | 58 | 古い |
| alphasystem | `docs/design/2026-07-27-task0-mf-api-foundation-plan.md` | 79 | 古い |

自動検出はノイズを生む。明示的な宣言が必要。

### 4.3 `conversations.md` の配置はリポジトリごとに異なる

| リポジトリ | パス |
| - | - |
| coopinf / coopbatch / coopcdebatch / alphacdk | `conversations.md` |
| alphasystem | `docs/conversations.md` **かつ** `alphabsmail/docs/conversations.md`（2 ファイル） |
| Obsidian Vault | `00_Claude/conversations.md` |

抽象的に「conversations.md に書け」と指示すると書き先を誤る。hook 側で実在パスを解決して渡す。

## 5. 設計

### 5.1 全体構成

グローバル hook 1 セットで全リポジトリを賄い、リポジトリ側は 1 行の宣言ファイルのみを持つ。
hook の実体は `claude-config` リポジトリで版管理し、`~/.claude/hooks/` へ配置する。

### 5.2 コンポーネント 1: `~/.claude/hooks/stop-record-decisions.sh`（Stop hook・新規）

毎ターン終了時に、記録すべき事項が出ていないかの自問を促す。

**判定対象と書き分け:**

| 出たもの | 書く先 |
| - | - |
| 日付・時刻・実行順序が確定した段取り | アクティブな計画ファイル |
| 承認・go サイン / 方針変更 / やらないと決めたこと | `conversations.md` |
| 効いた型・失敗・業務知識 | `LEARNINGS.md`（存在する場合のみ） |

**仕様:**

- 受け皿の実在パスをスクリプト側で解決し、指示文に具体パスとして埋め込む
- 「アクティブな計画ファイル」は `<repo>/.claude/active-plan`（5.4）から解決する。
  複数宣言されている場合は候補を全て列挙し、どれに書くかの選択は Claude に委ねる
  （`conversations.md` が複数ある場合と同じ扱い）。判断がつかない場合はユーザーに確認する
- 宣言が無い場合は段取りの書き先を `conversations.md` にフォールバックさせる
- 存在しない受け皿は指示文から除外する
- `conversations.md` が複数見つかった場合は全パスを列挙し、選択は Claude に委ねる
- git リポジトリでない、または受け皿が 1 つも無い場所では即 `exit 0`（ノイズ抑制）
- `stop_hook_active` が true の場合は `exit 0`（無限ループ防止。現行実装を踏襲）

### 5.3 コンポーネント 2: `~/.claude/hooks/session-start-context.sh`（SessionStart hook・新規）

セッション開始時に「今どこ」を注入する。

- `LEARNINGS.md` が存在すれば全文を注入（現行 coopinf 版の挙動を維持）
- `.claude/active-plan` に列挙された各計画ファイルについて、未チェック `- [ ]` 行を注入する。
  どの計画ファイルの Step かが分かるよう、ファイル名を見出しとして添える
- 注入量の上限: 1 ファイルあたり 20 件、全ファイル合計 60 件。
  上限を超えた分は件数のみ（「他に N 件」）を添える。
  セッション冒頭の注入で本題の文脈が薄まるのを防ぐため
- どちらも無ければ何も注入しない

### 5.4 コンポーネント 3: `<repo>/.claude/active-plan`（新規・複数行テキスト）

現在実行中の計画ファイルを、リポジトリルートからの相対パスで **1 行 1 パス** 列挙する。

複数行を許容するのは、実際に並行進行が常態であるため:

- coopinf … `cutover-plan.md` と `verify-backfill-plan.md` が同時に存在していた
- alphasystem … `docs/design/` に計画が 2 本
- Obsidian Vault … 複数の作業系（社内システム / 回線更改 / ベーターサイト業務等）が並行

**書式:**

```
# Phase 4 カットオーバー
migration/cutover-plan.md

# 埋め戻し検証（残タスクあり）
migration/verify-backfill-plan.md
```

**仕様:**

- 空行および `#` で始まる行は無視する。
  見出しコメントを書けるようにし、一時的に対象から外す操作を `#` の付与で行えるようにする
- 実在しないパスは警告せず無視する。
  計画ファイルのリネーム・削除後の残骸で hook が壊れないようにするため
- coopinf の初期値: `migration/cutover-plan.md`
- gitignore 対象は `settings.local.json` のみのため、このファイルは版管理される
- ファイル自体が存在しないリポジトリでは計画注入のみスキップし、他機能は動作する

### 5.5 コンポーネント 4: coopinf の既存 hook の撤去

グローバル版と二重発火するため削除する。

- `coopinf/.claude/hooks/session-start-learnings.sh` を削除
- `coopinf/.claude/hooks/stop-learnings-reflect.sh` を削除
- `coopinf/.claude/settings.local.json` の `hooks` 節を削除

### 5.6 コンポーネント 5: `~/.claude/CLAUDE.md` の文言修正

現行の記述:

> 結論は、コマンドライン上だけでは流れるので、conversations.mdに残してください。

この「結論」という語が、完結した調査のみを拾い未完了の段取りを落とした原因であるため、
発火条件を「決定・合意・日付付き段取り」に具体化し、5.2 の書き分け表を明記する。

## 6. 適用範囲

| 対象 | conversations | LEARNINGS | 計画注入 |
| - | - | - | - |
| coopinf | ルート | `migration/` | `.claude/active-plan` を設置 |
| coopbatch | ルート | なし | 将来必要になれば設置 |
| coopcdebatch | ルート | なし | 将来必要になれば設置 |
| alphasystem | `docs/` と `alphabsmail/docs/` | なし | 将来必要になれば設置 |
| alphacdk | ルート | なし | 将来必要になれば設置 |
| Obsidian Vault | `00_Claude/` | なし | 将来必要になれば設置 |

グローバル hook であるため、今後 clone するリポジトリにも自動的に適用される。

Obsidian Vault を対象に含めるのは、プログラム以外の作業系を Vault の Note で管理し、
Claude Code に相談しながら進めているため（2026-09-07 ユーザー判断）。

## 7. 再発防止の検証

発端の事象に本設計を当てはめた場合:

1. 9/7・9/8 の段取りが確定したターンで Stop hook が発火する
2. 「日付・実行順序が確定したか」の判定に該当するため、`.claude/active-plan` が指す
   `migration/cutover-plan.md` へ段取りを書き戻す
3. 次セッションの SessionStart で未チェック Step が注入され、「今どこ」を見失わない

## 8. 設計上のトレードオフ

- Stop hook は毎ターン発火するため、ターンあたりのコストが発生する。
  これは現行の coopinf の挙動と同等であり、受け皿の実在チェックによる足切りで
  無関係な作業ディレクトリでは発火しない
- 書き込みの実行自体は引き続き Claude の判断に依存する。
  本設計が保証するのは「毎ターン必ず判定が走ること」と「発火条件が具体的であること」であり、
  書き込みそのものの強制ではない
- `active-plan` の更新は手動運用。計画ファイルを切り替えた際の更新漏れが起こり得る。
  ただし実在しないパスは無視されるため、更新漏れは「注入されない」で済み、hook は壊れない
