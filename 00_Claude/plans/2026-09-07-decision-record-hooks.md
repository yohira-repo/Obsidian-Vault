# 決定・段取りの記録漏れを防ぐ hook 群 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 会話で確定した「日付付きの実行段取り」と「決定・合意」が記録されないまま流れる事象を、グローバル hook による機械的トリガーで防ぐ。

**Architecture:** hook スクリプト2本と共通ライブラリ1本を `claude-config` リポジトリで版管理し、`~/.claude/hooks/record/` へ配置する。`~/.claude/settings.json` に SessionStart / Stop として登録することで、全リポジトリに一括適用する。各リポジトリは `.claude/active-plan`（1行1パスの複数行テキスト）で「いま動いている計画ファイル」だけを宣言する。

**Tech Stack:** bash, jq（既存 hook が使用しており導入済み）, git。テストは bash による自作ハーネス（bats は未導入のため使わない）。

**設計書:** `00_Claude/specs/2026-09-07-decision-record-hooks-design.md`

> **⚠ Task 3・Task 4 の記述は古い。** Task 8（2026-09-07 追加）で hook の出力プロトコルを
> 変更し、`jq` 依存を排除した。Task 3・4 に出てくる `jq -r '.hookSpecificOutput...'` や
> `jq -r '.reason'` を使う検証コマンドは**現在の実装では動作しない**。
> 現在の仕様は次のとおり。
>
> | hook | 出力 |
> |---|---|
> | SessionStart | 平文を stdout に出して終了コード0（`grep` で直接検査する） |
> | Stop | 指示文を stderr に出して終了コード2（`2>&1 >/dev/null` で捕捉する） |
>
> Task 3・4 は実施済みの記録として残してあるだけで、再実行を想定していない。

## Global Constraints

- すべてのファイルは **UTF-8（BOMなし・LF）** で作成する。Claudian の Write ツールは UTF-16 LE で書き込むため、bash のヒアドキュメントまたは python3 で書き出すこと。
- スクリプト内に `/Users/yohira` 等の**絶対パスをハードコードしない**。`$HOME` とリポジトリルートからの相対解決のみを使う（Windows PC と共用するため）。
- hook は**失敗してもセッションを壊してはならない**。想定外の入力・欠損ファイルでは `exit 0` で静かに何もしない。
- Stop hook は `stop_hook_active` が `true` のとき必ず `exit 0` する（無限ループ防止）。
- git 管理下でないディレクトリ、および受け皿ファイルが1つも無いリポジトリでは何も出力しない。
- 注入量の上限: 計画ファイル1つあたり未チェック20件、全計画ファイル合計60件。
- `claude-config` の同期対象は `sync.ps1` の `$Targets`（`CLAUDE.md` / `AGENTS.md` / `settings.json` / `keybindings.json` / `hooks` / `commands/daily-sync.md`）。ここに含まれないパスに置いたものは他PCへ配布されない。

---

### Task 1: claude-config を安全な作業状態にする

**背景（着手前に必ず読むこと）:** このリポジトリには2つの地雷がある。

1. 現在ブランチ `feature/keybindings-sync` は **PR #2 で既にマージ済み**。このまま作業してはいけない。
2. `claude/CLAUDE.md` は**実機より古い**。repo 版は5行で `- コード修正の際は、特にしていない場合` という誤字を含む。実機 `~/.claude/CLAUDE.md` は14行。この状態で他PCが `sync.ps1 push` すると**個人ルールが5行に巻き戻る**。Task 5 で CLAUDE.md を編集する前に、必ずここで実機の内容を取り込む。

**Files:**
- Modify: `/Users/yohira/git/claude-config/claude/CLAUDE.md`（実機の内容で置き換え）
- Delete: `/Users/yohira/git/claude-config/claude/hooks/README.md`
- Delete: `/Users/yohira/git/claude-config/claude/hooks/hooks.json`
- Delete: `/Users/yohira/git/claude-config/claude/hooks/memory-persistence/README.md`
- Delete: `/Users/yohira/git/claude-config/claude/hooks/memory-persistence/hooks.json`

**Interfaces:**
- Produces: 作業ブランチ `feature/decision-record-hooks`、および ECC 生成物が除去され `claude/hooks/` が空になった状態（Task 2 以降がここにスクリプトを置く）

- [ ] **Step 1: マージ済みブランチであることを確認する**

```bash
cd /Users/yohira/git/claude-config
git rev-parse --abbrev-ref HEAD
gh pr list --state all --limit 5
```

期待: カレントブランチが `feature/keybindings-sync`、PR #2 が `MERGED` と表示される。

- [ ] **Step 2: main を最新化して新しいブランチを切る**

```bash
cd /Users/yohira/git/claude-config
git checkout main
git pull
git checkout -b feature/decision-record-hooks
```

期待: `Switched to a new branch 'feature/decision-record-hooks'`

- [ ] **Step 3: 実機の CLAUDE.md を repo へ取り込む**

```bash
cp /Users/yohira/.claude/CLAUDE.md /Users/yohira/git/claude-config/claude/CLAUDE.md
diff /Users/yohira/.claude/CLAUDE.md /Users/yohira/git/claude-config/claude/CLAUDE.md && echo "SAME"
```

期待: `SAME` と表示される（差分なし）。

- [ ] **Step 4: ECC 生成物を削除する**

`claude/hooks/` 配下の `README.md` / `hooks.json` / `memory-persistence/` は everything-claude-code の生成物であり、実機 `~/.claude/hooks/` には存在しない（実機にはディレクトリ自体が無い）。リポジトリ README の方針「プラグイン・フレームワークが生成するものは管理しない（乗り換え時に古い世代が復活するのを防ぐ）」に反しているため除去する。残したまま他PCで `sync.ps1 push` すると、意図しない hook 定義が配布される。

```bash
cd /Users/yohira/git/claude-config
git rm -r claude/hooks/README.md claude/hooks/hooks.json claude/hooks/memory-persistence
ls claude/hooks 2>/dev/null || echo "(空)"
```

期待: `(空)` と表示される。

- [ ] **Step 5: コミットして push し、Draft PR を作成する**

```bash
cd /Users/yohira/git/claude-config
git add claude/CLAUDE.md
git commit -m "chore: 実機のCLAUDE.mdを取り込み、ECC生成物のhooksを除去

- claude/CLAUDE.md が実機より9行古く、push時にルールが巻き戻る状態だったため同期
- claude/hooks/ 配下の ECC 生成物を除去（実機に存在せず、リポジトリ方針にも反するため）"
git push -u origin feature/decision-record-hooks
gh pr create --draft --title "決定・段取りの記録漏れを防ぐ hook 群" --body "設計書: Obsidian Vault \`00_Claude/specs/2026-09-07-decision-record-hooks-design.md\`

会話で確定した「日付付きの実行段取り」と「決定・合意」が記録されずに流れる事象への対策。
グローバル hook 2本で全リポジトリに一括適用する。

このコミットでは前提整備として、stale だった CLAUDE.md の同期と ECC 生成物の除去を行う。"
```

期待: PR の URL が出力される。

- [ ] **Step 6: 改行コードを LF に統一し、再発を防ぐ**

**背景（レビューで判明した不良の修正）:** Step 3 の `cp` は、実機の `CLAUDE.md` が CRLF だったため、**それまで LF だった repo 側を CRLF に退行させた**。repo 内の他ファイル（`settings.json` / `AGENTS.md` / `keybindings.json` / `README.md` / `sync.ps1` / `commands/daily-sync.md`）はすべて LF であり、実機側も `CLAUDE.md` 以外は LF。異常なのは実機の `CLAUDE.md` だけである。両方を LF に統一し、`.gitattributes` で再発を止める（2026-09-07 ユーザー判断）。

`* text=auto eol=lf` は Obsidian Vault で既に採用されている設定と同じ。`*.sh` が CRLF でチェックアウトされると `#!/bin/bash\r` と解釈され、後続タスクで作る hook が Windows で「bad interpreter」になるため、これは必須である。

```bash
cd /Users/yohira/git/claude-config
cat > .gitattributes <<'EOS'
# 改行は LF に統一する。
# 特に *.sh は CRLF だと shebang が壊れ、Windows で hook が起動しない。
* text=auto eol=lf
EOS
python3 - <<'EOS'
import io
for p in ('/Users/yohira/.claude/CLAUDE.md',
          '/Users/yohira/git/claude-config/claude/CLAUDE.md'):
    raw = io.open(p, 'rb').read()
    io.open(p, 'wb').write(raw.replace(b'\r\n', b'\n'))
    print("normalized", p)
EOS
file /Users/yohira/.claude/CLAUDE.md /Users/yohira/git/claude-config/claude/CLAUDE.md
diff /Users/yohira/.claude/CLAUDE.md /Users/yohira/git/claude-config/claude/CLAUDE.md && echo "SAME"
```

期待: `file` の出力に **CRLF が現れない**（`Unicode text, UTF-8 text` のみ）。`SAME` が出る。

- [ ] **Step 7: 全ファイルが LF であることを確認してコミットする**

```bash
cd /Users/yohira/git/claude-config
git add -A
git ls-files --eol | grep -v 'w/lf' || echo "全ファイル LF"
git commit -m "fix: CLAUDE.md の改行を LF に戻し、.gitattributes で LF を強制

Step 3 の cp で、LF だった repo 側 CLAUDE.md に実機の CRLF が混入していた。
repo 内の他ファイルは全て LF のため LF へ統一する。
*.sh が CRLF になると shebang が壊れ Windows で hook が起動しないため、
.gitattributes で恒久的に防ぐ。

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
git push
```

期待: `全ファイル LF` と表示され、コミット・push が成功する。

---

### Task 2: 共通ライブラリ `lib.sh` とテストハーネス

**Files:**
- Create: `/Users/yohira/git/claude-config/claude/hooks/record/lib.sh`
- Test: `/Users/yohira/git/claude-config/tests/test-record-hooks.sh`

**Interfaces:**
- Produces: 以下4関数。Task 3・Task 4 の両スクリプトが `. "$SCRIPT_DIR/lib.sh"` で読み込んで使う。
  - `repo_root()` … git リポジトリルートの絶対パスを stdout に出す。git 管理下でなければ何も出さず終了コード0
  - `find_records <root> <filename>` … `<root>` 配下 3 階層以内の `<filename>` を、root からの相対パスで1行ずつ出力。`.git/` と `node_modules/` は除外。ソート済み
  - `read_active_plans <root>` … `<root>/.claude/active-plan` を読み、空行・`#` 始まりを除外し、**実在するパスのみ**を1行ずつ出力
  - `unchecked_count <root> <relpath>` … 未チェック `- [ ]` 行の件数を出力（0件なら `0`）

**なぜ `tests/` をリポジトリ直下に置くか:** `sync.ps1` の同期対象は `claude/` 配下のみ。テストは他PCへ配布する必要がないため、対象外の場所に置く。

- [ ] **Step 1: 失敗するテストを書く**

```bash
mkdir -p /Users/yohira/git/claude-config/tests
cat > /Users/yohira/git/claude-config/tests/test-record-hooks.sh <<'EOS'
#!/bin/bash
# record hooks のテスト。fixture を一時ディレクトリに作って検証する。
set -uo pipefail

HOOK_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/../claude/hooks/record" && pwd)
PASS=0
FAIL=0

TMPDIRS=()
cleanup() { for d in "${TMPDIRS[@]:-}"; do [ -n "$d" ] && rm -rf "$d"; done; }
trap cleanup EXIT

ok()   { PASS=$((PASS+1)); echo "  ok   - $1"; }
ng()   { FAIL=$((FAIL+1)); echo "  NG   - $1"; echo "         期待: [$2]"; echo "         実際: [$3]"; }
check(){ if [ "$2" = "$3" ]; then ok "$1"; else ng "$1" "$2" "$3"; fi; }

# fixture: git リポジトリを1つ作る
make_repo() {
  local d
  d=$(mktemp -d)
  git -C "$d" init -q
  TMPDIRS+=("$d")
  echo "$d"
}

echo "== lib.sh =="
. "$HOOK_DIR/lib.sh"

# --- find_records ---
R=$(make_repo)
mkdir -p "$R/docs" "$R/sub/docs" "$R/node_modules/pkg"
touch "$R/conversations.md" "$R/docs/conversations.md" "$R/sub/docs/conversations.md" "$R/node_modules/pkg/conversations.md"
GOT=$(cd "$R" && find_records "$R" conversations.md | tr '\n' ',')
check "find_records は3階層まで拾い node_modules を除外する" "conversations.md,docs/conversations.md,sub/docs/conversations.md," "$GOT"
cp "$R/conversations.md" "$R/.git/conversations.md"
GOT=$(find_records "$R" conversations.md | tr '\n' ',')
check "find_records は .git 配下を除外する" "conversations.md,docs/conversations.md,sub/docs/conversations.md," "$GOT"
rm -rf "$R"

# root に正規表現メタ文字や sed の区切り文字が含まれても壊れないこと。
# sed によるプレフィックス除去だと [ ] で絶対パスがそのまま返り、| ではコマンドが失敗する。
B=$(mktemp -d); TMPDIRS+=("$B")
R="$B/re[po] |x"
mkdir -p "$R/docs"
git -C "$R" init -q
touch "$R/conversations.md" "$R/docs/conversations.md"
GOT=$(find_records "$R" conversations.md | tr '\n' ',')
check "find_records は特殊文字を含むパスでも root 相対で返す" "conversations.md,docs/conversations.md," "$GOT"
rm -rf "$B"

R=$(make_repo)
GOT=$(cd "$R" && find_records "$R" conversations.md)
check "find_records は該当なしなら空を返す" "" "$GOT"
rm -rf "$R"

# --- read_active_plans ---
R=$(make_repo)
mkdir -p "$R/.claude" "$R/migration"
touch "$R/migration/cutover-plan.md" "$R/migration/verify-backfill-plan.md"
printf '# Phase 4\nmigration/cutover-plan.md\n\n#migration/verify-backfill-plan.md\nmigration/deleted-plan.md\n' > "$R/.claude/active-plan"
GOT=$(read_active_plans "$R" | tr '\n' ',')
check "read_active_plans はコメント・空行・実在しないパスを除外する" "migration/cutover-plan.md," "$GOT"
printf '   migration/cutover-plan.md   \n\t  # インデントされたコメント\n' > "$R/.claude/active-plan"
GOT=$(read_active_plans "$R" | tr '\n' ',')
check "read_active_plans は前後の空白を除去する" "migration/cutover-plan.md," "$GOT"
rm -rf "$R"

R=$(make_repo)
GOT=$(read_active_plans "$R")
check "read_active_plans は active-plan が無ければ空を返す" "" "$GOT"
rm -rf "$R"

# --- unchecked_count ---
R=$(make_repo)
printf -- '- [ ] a\n- [x] b\n  - [ ] c\n' > "$R/p.md"
check "unchecked_count は未チェック行を数える" "2" "$(unchecked_count "$R" p.md)"
printf -- '- [x] b\n' > "$R/q.md"
check "unchecked_count は0件なら0を返す" "0" "$(unchecked_count "$R" q.md)"
rm -rf "$R"

echo ""
echo "PASS=$PASS FAIL=$FAIL"
[ "$FAIL" -eq 0 ]
EOS
chmod +x /Users/yohira/git/claude-config/tests/test-record-hooks.sh
```

- [ ] **Step 2: テストを実行して失敗することを確認する**

```bash
/Users/yohira/git/claude-config/tests/test-record-hooks.sh
```

期待: FAIL。`claude/hooks/record` ディレクトリが存在しないため `cd` に失敗するエラーが出る。

- [ ] **Step 3: `lib.sh` を実装する**

```bash
mkdir -p /Users/yohira/git/claude-config/claude/hooks/record
cat > /Users/yohira/git/claude-config/claude/hooks/record/lib.sh <<'EOS'
#!/bin/bash
# record hooks 共通のパス解決処理。
# session-start-context.sh / stop-record-decisions.sh から source される。
# 単体では実行しない（set -e は呼び出し側に委ねる）。

# git リポジトリのルート絶対パス。git 管理下でなければ何も出力しない。
repo_root() {
  git rev-parse --show-toplevel 2>/dev/null || true
}

# find_records <root> <filename>
# <root> 配下3階層以内の <filename> を root 相対パスで出力する。
#
# プレフィックス除去に sed を使ってはならない。root は正規表現ではなくリテラルであり、
# パスに [ ] . を含むと誤マッチし、| を含むと区切り文字と衝突して sed 自体が失敗する
# （実機で再現確認済み）。bash のパラメータ展開 ${f#"$root"/} はリテラル一致のため安全。
find_records() {
  local root="$1" name="$2" f
  [ -d "$root" ] || return 0
  while IFS= read -r f; do
    printf '%s\n' "${f#"$root"/}"
  done < <(find "$root" -maxdepth 3 -name "$name" -type f \
             -not -path "*/.git/*" -not -path "*/node_modules/*" 2>/dev/null | sort)
}

# read_active_plans <root>
# <root>/.claude/active-plan を読み、実在する計画ファイルのみを root 相対で出力する。
# 空行と # 始まりの行は無視する。
read_active_plans() {
  local root="$1" f="$1/.claude/active-plan" line
  [ -f "$f" ] || return 0
  while IFS= read -r line || [ -n "$line" ]; do
    line="${line#"${line%%[![:space:]]*}"}"
    line="${line%"${line##*[![:space:]]}"}"
    [ -z "$line" ] && continue
    case "$line" in
      '#'*) continue ;;
    esac
    [ -f "$root/$line" ] && printf '%s\n' "$line"
  done < "$f"
  return 0
}

# unchecked_count <root> <relpath>
# 未チェックのチェックボックス行の件数を出力する。
unchecked_count() {
  local root="$1" rel="$2" n
  n=$(grep -c '^[[:space:]]*- \[ \]' "$root/$rel" 2>/dev/null || true)
  printf '%s\n' "${n:-0}"
}
EOS
```

- [ ] **Step 4: テストを実行して通ることを確認する**

```bash
/Users/yohira/git/claude-config/tests/test-record-hooks.sh
```

期待: `PASS=9 FAIL=0` と表示され、終了コード0。

- [ ] **Step 5: コミットする**

```bash
cd /Users/yohira/git/claude-config
git add claude/hooks/record/lib.sh tests/test-record-hooks.sh
git commit -m "feat: record hooks の共通パス解決ライブラリとテストを追加"
```

---

### Task 3: SessionStart hook `session-start-context.sh`

**Files:**
- Create: `/Users/yohira/git/claude-config/claude/hooks/record/session-start-context.sh`
- Modify: `/Users/yohira/git/claude-config/tests/test-record-hooks.sh`（末尾にテストを追加）

**Interfaces:**
- Consumes: Task 2 の `repo_root` / `find_records` / `read_active_plans` / `unchecked_count`
- Produces: 標準出力に `{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"..."}}` の JSON。注入すべき内容が無ければ何も出力せず終了コード0

- [ ] **Step 1: 失敗するテストを追記する**

`tests/test-record-hooks.sh` の `echo ""` `echo "PASS=$PASS FAIL=$FAIL"` の直前に、以下を挿入する。

```bash
python3 - <<'EOS'
import io
p = '/Users/yohira/git/claude-config/tests/test-record-hooks.sh'
s = io.open(p, encoding='utf-8').read()
marker = '\necho ""\necho "PASS=$PASS FAIL=$FAIL"\n'
add = '''
echo "== session-start-context.sh =="
SS="$HOOK_DIR/session-start-context.sh"

# 受け皿が何も無ければ無出力
R=$(make_repo)
GOT=$(cd "$R" && "$SS" </dev/null)
check "SessionStart: 受け皿なしなら無出力" "" "$GOT"
rm -rf "$R"

# git 管理外なら無出力
R=$(mktemp -d)
touch "$R/conversations.md"
GOT=$(cd "$R" && "$SS" </dev/null)
check "SessionStart: git管理外なら無出力" "" "$GOT"
rm -rf "$R"

# LEARNINGS.md を注入する
R=$(make_repo)
mkdir -p "$R/migration"
printf 'ラーニング本文\\n' > "$R/migration/LEARNINGS.md"
GOT=$(cd "$R" && "$SS" </dev/null | jq -r '.hookSpecificOutput.hookEventName')
check "SessionStart: hookEventName が正しい" "SessionStart" "$GOT"
GOT=$(cd "$R" && "$SS" </dev/null | jq -r '.hookSpecificOutput.additionalContext' | grep -c 'ラーニング本文')
check "SessionStart: LEARNINGS.md の本文が含まれる" "1" "$GOT"
rm -rf "$R"

# active-plan の未チェック Step を注入する
R=$(make_repo)
mkdir -p "$R/.claude" "$R/migration"
printf -- '- [x] done\\n- [ ] STEP-ALPHA\\n- [ ] STEP-BRAVO\\n' > "$R/migration/cutover-plan.md"
printf 'migration/cutover-plan.md\\n' > "$R/.claude/active-plan"
CTX=$(cd "$R" && "$SS" </dev/null | jq -r '.hookSpecificOutput.additionalContext')
check "SessionStart: 未チェックStepが含まれる" "1" "$(printf '%s' "$CTX" | grep -c 'STEP-ALPHA')"
check "SessionStart: 済Stepは含まれない"     "0" "$(printf '%s' "$CTX" | grep -c 'done')"
check "SessionStart: 計画ファイル名が見出しに出る" "1" "$(printf '%s' "$CTX" | grep -c 'migration/cutover-plan.md')"
rm -rf "$R"

# 1ファイル20件の上限
R=$(make_repo)
mkdir -p "$R/.claude"
for i in $(seq 1 25); do printf -- '- [ ] item%02d\\n' "$i"; done > "$R/big-plan.md"
printf 'big-plan.md\\n' > "$R/.claude/active-plan"
CTX=$(cd "$R" && "$SS" </dev/null | jq -r '.hookSpecificOutput.additionalContext')
check "SessionStart: 20件で打ち切る"       "20" "$(printf '%s' "$CTX" | grep -c 'item')"
check "SessionStart: 残件数を件数だけ添える" "1"  "$(printf '%s' "$CTX" | grep -c '他に 5 件')"
rm -rf "$R"

# 全ファイル合計60件の上限
R=$(make_repo)
mkdir -p "$R/.claude"
: > "$R/.claude/active-plan"
for f in p1 p2 p3 p4; do
  for i in $(seq 1 25); do printf -- '- [ ] %s-item%02d\n' "$f" "$i"; done > "$R/$f.md"
  printf '%s.md\n' "$f" >> "$R/.claude/active-plan"
done
CTX=$(cd "$R" && "$SS" </dev/null | jq -r '.hookSpecificOutput.additionalContext')
check "SessionStart: 合計60件で打ち切る"     "60" "$(printf '%s' "$CTX" | grep -c -- '-item')"
check "SessionStart: 上限超過分は出力しない" "0"  "$(printf '%s' "$CTX" | grep -c 'p4.md')"
rm -rf "$R"
'''
assert marker in s
s = s.replace(marker, add + marker)
io.open(p, 'w', encoding='utf-8').write(s)
print("added")
EOS
```

- [ ] **Step 2: テストを実行して失敗することを確認する**

```bash
/Users/yohira/git/claude-config/tests/test-record-hooks.sh
```

期待: `session-start-context.sh` が存在しないため、`NG` が並び `FAIL` が0でない。

- [ ] **Step 3: `session-start-context.sh` を実装する**

```bash
cat > /Users/yohira/git/claude-config/claude/hooks/record/session-start-context.sh <<'EOS'
#!/bin/bash
# SessionStart hook:
#   - LEARNINGS.md があれば全文を
#   - .claude/active-plan が指す計画ファイルの未チェック Step を
#   コンテキストへ注入し、セッション開始時に「今どこ」が分かる状態にする。
set -uo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=lib.sh
. "$SCRIPT_DIR/lib.sh"

PER_FILE_CAP=20
TOTAL_CAP=60

ROOT=$(repo_root)
[ -n "$ROOT" ] || exit 0

CTX=""

# --- LEARNINGS.md ---
while IFS= read -r rel; do
  [ -n "$rel" ] || continue
  CTX="${CTX}## ${rel} の現在の内容

$(cat "$ROOT/$rel")

"
done < <(find_records "$ROOT" LEARNINGS.md)

# --- active-plan が指す計画ファイルの未チェック Step ---
PLAN_CTX=""
total=0
while IFS= read -r rel; do
  [ -n "$rel" ] || continue
  [ "$total" -lt "$TOTAL_CAP" ] || break
  n=$(unchecked_count "$ROOT" "$rel")
  [ "$n" -gt 0 ] || continue

  take="$PER_FILE_CAP"
  remain=$((TOTAL_CAP - total))
  [ "$take" -gt "$remain" ] && take="$remain"
  [ "$take" -gt "$n" ] && take="$n"

  PLAN_CTX="${PLAN_CTX}### ${rel}（未完了 ${n} 件）

$(grep '^[[:space:]]*- \[ \]' "$ROOT/$rel" | head -n "$take")
"
  if [ "$n" -gt "$take" ]; then
    PLAN_CTX="${PLAN_CTX}（他に $((n - take)) 件）
"
  fi
  PLAN_CTX="${PLAN_CTX}
"
  total=$((total + take))
done < <(read_active_plans "$ROOT")

if [ -n "$PLAN_CTX" ]; then
  CTX="${CTX}## 実行中の計画と未完了のステップ

${PLAN_CTX}"
fi

[ -n "$CTX" ] || exit 0

HEADER="以下はこのリポジトリの現在の作業コンテキストです。最初の応答で、実行中の計画がどこまで進んでいるかを簡潔に報告し、読み込み済みであることが分かるようにしてください。

---
"

jq -n --arg ctx "${HEADER}${CTX}" '{
  hookSpecificOutput: {
    hookEventName: "SessionStart",
    additionalContext: $ctx
  }
}'
EOS
chmod +x /Users/yohira/git/claude-config/claude/hooks/record/session-start-context.sh
```

- [ ] **Step 4: テストを実行して通ることを確認する**

```bash
/Users/yohira/git/claude-config/tests/test-record-hooks.sh
```

期待: `PASS=20 FAIL=0`、終了コード0。

- [ ] **Step 5: 実リポジトリで手動確認する**

```bash
cd /Users/yohira/git/coopinf && /Users/yohira/git/claude-config/claude/hooks/record/session-start-context.sh </dev/null | jq -r '.hookSpecificOutput.additionalContext' | head -20
```

期待: `migration/LEARNINGS.md の現在の内容` の見出しが出る。この時点では coopinf に `.claude/active-plan` が無いため、計画セクションは出ない（Task 6 で設置する）。

- [ ] **Step 6: コミットする**

```bash
cd /Users/yohira/git/claude-config
git add claude/hooks/record/session-start-context.sh tests/test-record-hooks.sh
git commit -m "feat: SessionStart hook を追加（LEARNINGS.md と実行中計画の未完了Stepを注入）"
```

---

### Task 4: Stop hook `stop-record-decisions.sh`

**Files:**
- Create: `/Users/yohira/git/claude-config/claude/hooks/record/stop-record-decisions.sh`
- Modify: `/Users/yohira/git/claude-config/tests/test-record-hooks.sh`（末尾にテストを追加）

**Interfaces:**
- Consumes: Task 2 の `repo_root` / `find_records` / `read_active_plans`
- Produces: 標準出力に `{"decision":"block","reason":"..."}` の JSON。促す必要が無ければ何も出力せず終了コード0

- [ ] **Step 1: 失敗するテストを追記する**

```bash
python3 - <<'EOS'
import io
p = '/Users/yohira/git/claude-config/tests/test-record-hooks.sh'
s = io.open(p, encoding='utf-8').read()
marker = '\necho ""\necho "PASS=$PASS FAIL=$FAIL"\n'
add = '''
echo "== stop-record-decisions.sh =="
ST="$HOOK_DIR/stop-record-decisions.sh"

# --- ケースA: conversations.md のみ（active-plan 宣言なし） ---
R=$(make_repo)
touch "$R/conversations.md"

GOT=$(cd "$R" && echo '{"stop_hook_active":true}' | "$ST")
check "Stop: stop_hook_active なら無出力" "" "$GOT"

GOT=$(cd "$R" && echo '{"stop_hook_active":false}' | "$ST" | jq -r '.decision')
check "Stop: decision は block" "block" "$GOT"

REASON=$(cd "$R" && echo '{}' | "$ST" | jq -r '.reason')
# 宣言が無いので項番1(段取り)と項番2(決定)の両方が conversations.md を指す = 2 行
check "Stop: conversations.md が書き先に列挙される" "2" "$(printf '%s' "$REASON" | grep -c '^    - conversations.md$')"
check "Stop: フォールバックである旨が明示される"    "1" "$(printf '%s' "$REASON" | grep -c 'フォールバック')"
check "Stop: 未完了は記録しない理由にならない旨"    "1" "$(printf '%s' "$REASON" | grep -c '完了していない')"
check "Stop: LEARNINGS.md が無ければ言及しない"     "0" "$(printf '%s' "$REASON" | grep -c 'LEARNINGS.md')"

GOT=$(cd "$R" && "$ST" </dev/null >/dev/null 2>&1; echo $?)
check "Stop: 空の標準入力でも落ちない" "0" "$GOT"

# --- ケースB: active-plan と LEARNINGS.md がある ---
mkdir -p "$R/.claude" "$R/migration"
touch "$R/migration/cutover-plan.md" "$R/migration/LEARNINGS.md"
printf 'migration/cutover-plan.md\n' > "$R/.claude/active-plan"
REASON=$(cd "$R" && echo '{}' | "$ST" | jq -r '.reason')
check "Stop: 計画ファイルが段取りの書き先になる" "1" "$(printf '%s' "$REASON" | grep -c '^    - migration/cutover-plan.md$')"
check "Stop: conversations.md は項番2のみになる" "1" "$(printf '%s' "$REASON" | grep -c '^    - conversations.md$')"
check "Stop: LEARNINGS.md が項番3に出る"        "1" "$(printf '%s' "$REASON" | grep -c '^    - migration/LEARNINGS.md$')"
check "Stop: 宣言があればフォールバック表記は出ない" "0" "$(printf '%s' "$REASON" | grep -c 'フォールバック')"
rm -rf "$R"

# --- ケースD: 受け皿が部分的にしか無い ---
# LEARNINGS.md だけがあるリポジトリで、存在しない conversations.md へ案内したり
# 項番が 1→3 と飛んだりしないこと。
R=$(make_repo)
mkdir -p "$R/migration"
touch "$R/migration/LEARNINGS.md"
REASON=$(cd "$R" && echo '{}' | "$ST" | jq -r '.reason')
check "Stop: LEARNINGS のみなら項番は1つだけ" "1. 効いた型・失敗・業務知識・覚えておく価値のある解法" "$(printf '%s' "$REASON" | grep -E '^[0-9]+\.')"
check "Stop: LEARNINGS のみなら conversations.md に言及しない" "0" "$(printf '%s' "$REASON" | grep -c 'conversations.md')"
rm -rf "$R"

# active-plan だけがあるリポジトリでは段取りの項目のみが出る。
R=$(make_repo)
mkdir -p "$R/.claude"
touch "$R/p.md"
printf 'p.md\n' > "$R/.claude/active-plan"
REASON=$(cd "$R" && echo '{}' | "$ST" | jq -r '.reason')
check "Stop: active-plan のみなら段取りだけが出る" "1. 日付・時刻・実行順序が確定した段取り" "$(printf '%s' "$REASON" | grep -E '^[0-9]+\.')"
rm -rf "$R"

# --- ケースC: 受け皿なし / git 管理外 ---
R=$(make_repo)
GOT=$(cd "$R" && echo '{}' | "$ST")
check "Stop: 受け皿なしなら無出力" "" "$GOT"
rm -rf "$R"

R=$(mktemp -d)
touch "$R/conversations.md"
GOT=$(cd "$R" && echo '{}' | "$ST")
check "Stop: git管理外なら無出力" "" "$GOT"
rm -rf "$R"
'''
assert marker in s
s = s.replace(marker, add + marker)
io.open(p, 'w', encoding='utf-8').write(s)
print("added")
EOS
```

- [ ] **Step 2: テストを実行して失敗することを確認する**

```bash
/Users/yohira/git/claude-config/tests/test-record-hooks.sh
```

期待: `stop-record-decisions.sh` が存在せず `NG` が並ぶ。

- [ ] **Step 3: `stop-record-decisions.sh` を実装する**

```bash
cat > /Users/yohira/git/claude-config/claude/hooks/record/stop-record-decisions.sh <<'EOS'
#!/bin/bash
# Stop hook: 応答が終わるたびに、このターンで
#   1. 日付・時刻・実行順序が確定した段取り
#   2. 承認・方針変更・やらないと決めたこと
#   3. 効いた型・失敗・業務知識
# が出ていないかを自問させ、該当する受け皿へ追記するよう促す。
#
# 受け皿の実在パスをこのスクリプトが解決して指示文に埋め込む。
# 存在しない受け皿は指示文に出さない（書き先を誤らせないため）。
set -uo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=lib.sh
. "$SCRIPT_DIR/lib.sh"

INPUT=$(cat 2>/dev/null || true)
STOP_ACTIVE=$(printf '%s' "$INPUT" | jq -r '.stop_hook_active // false' 2>/dev/null || echo false)
[ "$STOP_ACTIVE" = "true" ] && exit 0

ROOT=$(repo_root)
[ -n "$ROOT" ] || exit 0

CONV=$(find_records "$ROOT" conversations.md)
LEARN=$(find_records "$ROOT" LEARNINGS.md)
PLANS=$(read_active_plans "$ROOT")

# 受け皿が1つも無いリポジトリでは何もしない
[ -n "${CONV}${LEARN}${PLANS}" ] || exit 0

# 指示文は「実在する受け皿がある項目だけ」を、番号を飛ばさずに並べる。
# 受け皿が部分的にしか無いリポジトリで、存在しないファイルへ案内したり
# 項番が 1→3 のように飛んだりしないよう、N を動的に採番する。
REASON="このターンを振り返ってください。次のいずれかが出ていれば、対応するファイルへ簡潔に追記してください。
"
N=0

# 1. 段取り。書き先は active-plan、無ければ conversations.md にフォールバックする。
#    どちらも無い場合はこの項目自体を出さない（宛先が存在しないため）。
if [ -n "$PLANS" ] || [ -n "$CONV" ]; then
  N=$((N + 1))
  if [ -n "$PLANS" ]; then
    PLAN_DEST=$(printf '%s' "$PLANS" | sed 's/^/    - /')
  else
    PLAN_DEST="$(printf '%s' "$CONV" | sed 's/^/    - /')
    （.claude/active-plan の宣言が無いため conversations.md にフォールバック）"
  fi
  REASON="${REASON}
${N}. 日付・時刻・実行順序が確定した段取り
   例:「Task 4 は 9/7 の日中」「9/8 09:30 の自動実行でカットオーバー」
   書き先:
${PLAN_DEST}
"
fi

# 2. 決定・合意
if [ -n "$CONV" ]; then
  N=$((N + 1))
  REASON="${REASON}
${N}. ユーザーの承認・go サイン / 方針変更 / やらないと決めたこと（不作為の決定）
   例:「その方針でいきましょう」「今回はやらない」「B案に変更する」
   書き先:
$(printf '%s' "$CONV" | sed 's/^/    - /')
"
fi

# 3. 学び
if [ -n "$LEARN" ]; then
  N=$((N + 1))
  REASON="${REASON}
${N}. 効いた型・失敗・業務知識・覚えておく価値のある解法
   例:「この切り分け手順が原因特定に効いた」「この仕様は直感に反する」
   書き先:
$(printf '%s' "$LEARN" | sed 's/^/    - /')
"
fi

REASON="${REASON}
重要: 「その件はまだ完了していない」ことは記録しない理由になりません。
決まった時点で記録してください。既に計画ファイルに1行書いてあることも、
会話で詰めた具体的な段取りを省略する理由にはなりません。

書き先の候補が複数ある場合は話題に最も近いものを選び、判断がつかなければユーザーに確認してください。
いずれにも該当しなければ、ファイルを変更せずそのまま終了してください。"
jq -n --arg r "$REASON" '{decision: "block", reason: $r}'
EOS
chmod +x /Users/yohira/git/claude-config/claude/hooks/record/stop-record-decisions.sh
```

- [ ] **Step 4: テストを実行して通ることを確認する**

```bash
/Users/yohira/git/claude-config/tests/test-record-hooks.sh
```

期待: `PASS=36 FAIL=0`、終了コード0。

- [ ] **Step 5: 実リポジトリで手動確認する**

```bash
cd /Users/yohira/git/coopinf && echo '{}' | /Users/yohira/git/claude-config/claude/hooks/record/stop-record-decisions.sh | jq -r '.reason'
echo '{}' | /Users/yohira/git/claude-config/claude/hooks/record/stop-record-decisions.sh | jq -r '.reason'
```

期待: coopinf では `conversations.md` と `migration/LEARNINGS.md` が書き先として列挙される。Vault では `00_Claude/conversations.md` が列挙され、LEARNINGS.md の項番3は出ない。

- [ ] **Step 6: コミットする**

```bash
cd /Users/yohira/git/claude-config
git add claude/hooks/record/stop-record-decisions.sh tests/test-record-hooks.sh
git commit -m "feat: Stop hook を追加（決定・段取り・学びの記録を毎ターン促す）"
```

---

### Task 5: `settings.json` への登録と CLAUDE.md の文言修正

**Files:**
- Modify: `/Users/yohira/.claude/settings.json`（実機）
- Modify: `/Users/yohira/git/claude-config/claude/settings.json`
- Modify: `/Users/yohira/git/claude-config/claude/CLAUDE.md`
- Modify: `/Users/yohira/.claude/CLAUDE.md`（実機）

**Interfaces:**
- Consumes: Task 3・Task 4 のスクリプト
- Produces: 実機で hook が発火する状態

**注意:** 実機の `~/.claude/hooks/` は存在しない。`claude-config` の `claude/hooks/record/` を実機へコピーして配置する。Windows PC へは `sync.ps1 push` で配布される（`hooks` は `$Targets` に含まれている）。

- [ ] **Step 1: スクリプトを実機へ配置する**

```bash
mkdir -p /Users/yohira/.claude/hooks/record
cp /Users/yohira/git/claude-config/claude/hooks/record/*.sh /Users/yohira/.claude/hooks/record/
chmod +x /Users/yohira/.claude/hooks/record/*.sh
ls -l /Users/yohira/.claude/hooks/record/
```

期待: `lib.sh` / `session-start-context.sh` / `stop-record-decisions.sh` の3本が実行権付きで並ぶ。

- [ ] **Step 2: 実機の settings.json に hook を登録する**

既存の SessionEnd（daily log sync）は消さないこと。

```bash
python3 - <<'EOS'
import json, io
p = '/Users/yohira/.claude/settings.json'
s = json.load(io.open(p, encoding='utf-8'))
hooks = s.setdefault('hooks', {})
hooks['SessionStart'] = [{
    "hooks": [{
        "type": "command",
        "shell": "bash",
        "command": "\"$HOME/.claude/hooks/record/session-start-context.sh\"",
        "timeout": 10
    }]
}]
hooks['Stop'] = [{
    "hooks": [{
        "type": "command",
        "shell": "bash",
        "command": "\"$HOME/.claude/hooks/record/stop-record-decisions.sh\"",
        "timeout": 10
    }]
}]
io.open(p, 'w', encoding='utf-8').write(json.dumps(s, ensure_ascii=False, indent=2) + "\n")
print("ok")
EOS
python3 -c "import json;json.load(open('/Users/yohira/.claude/settings.json'));print('valid json')"
jq -r '.hooks | keys[]' /Users/yohira/.claude/settings.json
```

期待: `valid json` と、`SessionEnd` / `SessionStart` / `Stop` の3つが出力される。

- [ ] **Step 3: CLAUDE.md の文言を修正する**

**前提:** Task 1 の修正で両ファイルとも LF に統一済み。`.gitattributes` の `* text=auto eol=lf` により、以降 CRLF が混入してもコミット時に正規化される。

```bash
python3 - <<'EOS'
import io
old = "- 結論は、コマンドライン上だけでは流れるので、conversations.mdに残してください。\n"
new = ("- 会話で確定した内容は、コマンドライン上だけでは流れるので、必ずファイルに残してください。"
       "書き先は次のとおり分けます。\n"
       "  - **日付・時刻・実行順序が確定した段取り** → `.claude/active-plan` が指す計画ファイル"
       "（宣言が無ければ conversations.md）。「まだ完了していない」ことは記録しない理由になりません。\n"
       "  - **承認・go サイン / 方針変更 / やらないと決めたこと** → conversations.md\n"
       "  - **効いた型・失敗・業務知識** → LEARNINGS.md（あるリポジトリのみ）\n")
for p in ('/Users/yohira/.claude/CLAUDE.md',
          '/Users/yohira/git/claude-config/claude/CLAUDE.md'):
    s = io.open(p, encoding='utf-8', newline='').read()
    assert old in s, p
    io.open(p, 'w', encoding='utf-8', newline='').write(s.replace(old, new))
    print("patched", p)
EOS
diff /Users/yohira/.claude/CLAUDE.md /Users/yohira/git/claude-config/claude/CLAUDE.md && echo "SAME"
file /Users/yohira/git/claude-config/claude/CLAUDE.md
cd /Users/yohira/git/claude-config && git diff --stat claude/CLAUDE.md
```

期待: 2ファイルとも `patched`、`SAME`、`file` の出力に **CRLF が現れない**こと、`git diff --stat` が **1行削除・4行追加**であること（全行が差分なら改行が壊れている）。

- [ ] **Step 4: 実機の settings.json を repo へ同期する**

```bash
cp /Users/yohira/.claude/settings.json /Users/yohira/git/claude-config/claude/settings.json
diff /Users/yohira/.claude/settings.json /Users/yohira/git/claude-config/claude/settings.json && echo "SAME"
```

期待: `SAME`

- [ ] **Step 5: 新しいセッションで発火を確認する**

Claude Code を新しいセッションで `~/git/coopinf` を対象に起動し、次の2点を目視で確認する。

1. 冒頭で LEARNINGS.md の内容を要約した報告が出る（SessionStart hook）
2. 1ターン応答させたあと、記録を促す動きが入る（Stop hook）

**PASS基準:** 上記2点が確認でき、かつセッションがエラーで停止しないこと。

- [ ] **Step 6: コミットする**

```bash
cd /Users/yohira/git/claude-config
git add claude/settings.json claude/CLAUDE.md
git commit -m "feat: record hooks を settings.json に登録し、CLAUDE.md の記録ルールを具体化"
git push
```

---

### Task 6: coopinf の既存 hook を撤去し `active-plan` を設置する

**Files:**
- Delete: `/Users/yohira/git/coopinf/.claude/hooks/session-start-learnings.sh`
- Delete: `/Users/yohira/git/coopinf/.claude/hooks/stop-learnings-reflect.sh`
- Modify: `/Users/yohira/git/coopinf/.claude/settings.local.json`
- Create: `/Users/yohira/git/coopinf/.claude/active-plan`

**Interfaces:**
- Consumes: Task 5 で稼働したグローバル hook
- Produces: coopinf でグローバル hook のみが単独で動作する状態

**注意:** coopinf の現在ブランチは `feature/learnings-cfn-non-ascii`。CLAUDE.md のルールにより、feature ブランチならそのまま作業する。ただし着手前に対象 PR がマージ済みでないか確認すること。

- [ ] **Step 1: ブランチと PR の状態を確認する**

```bash
cd /Users/yohira/git/coopinf
git rev-parse --abbrev-ref HEAD
gh pr list --state all --limit 5
```

期待: カレントブランチが表示される。該当 PR が `MERGED` なら、main から新しい feature ブランチを切り直してから以降を実施する。

- [ ] **Step 2: 既存 hook を削除する**

```bash
cd /Users/yohira/git/coopinf
git rm .claude/hooks/session-start-learnings.sh .claude/hooks/stop-learnings-reflect.sh
```

期待: 2ファイルが削除される。

- [ ] **Step 3: settings.local.json の hooks 節を削除する**

このファイルは gitignore 対象（`.gitignore:57`）なので git 管理外。実機のみ編集する。

```bash
python3 - <<'EOS'
import json, io
p = '/Users/yohira/git/coopinf/.claude/settings.local.json'
s = json.load(io.open(p, encoding='utf-8'))
s.pop('hooks', None)
io.open(p, 'w', encoding='utf-8').write(json.dumps(s, ensure_ascii=False, indent=2) + "\n")
print("ok")
EOS
cat /Users/yohira/git/coopinf/.claude/settings.local.json
```

期待: `hooks` キーが消えている。

- [ ] **Step 4: `active-plan` を設置する**

```bash
cat > /Users/yohira/git/coopinf/.claude/active-plan <<'EOS'
# Phase 4: coop-batch 本番カットオーバー
migration/cutover-plan.md
EOS
file /Users/yohira/git/coopinf/.claude/active-plan
```

期待: `UTF-8 text`（または `ASCII text` を含む Unicode text）と表示される。

- [ ] **Step 5: 二重発火していないこと・計画が注入されることを確認する**

```bash
cd /Users/yohira/git/coopinf
echo "--- SessionStart: 計画が注入されるか ---"
"$HOME/.claude/hooks/record/session-start-context.sh" </dev/null | grep -E '^## |^### '
echo "--- Stop: 段取りの書き先が計画ファイルになるか ---"
echo '{}' | "$HOME/.claude/hooks/record/stop-record-decisions.sh" 2>&1 >/dev/null | sed -n '1,8p'
```

期待:

- SessionStart の出力に `## 実行中の計画と未完了のステップ` と `### migration/cutover-plan.md（未完了 19 件）` が含まれる
- Stop の項番1の書き先が `- migration/cutover-plan.md` になり、**「フォールバック」の文字列が出ない**

> **注:** hook は JSON を返さない（Task 8 で変更）。`jq` でパースしようとするとエラーになる。

- [ ] **Step 6: コミットして Draft PR を作成する**

```bash
cd /Users/yohira/git/coopinf
git add .claude/active-plan
git commit -m "chore: ローカルhookをグローバルhookへ移行し、active-planを設置

- .claude/hooks/ の2本は ~/.claude/hooks/record/ のグローバル版に置き換わったため削除
- .claude/active-plan で実行中の計画ファイル(cutover-plan.md)を宣言"
git push -u origin HEAD
gh pr create --draft --title "ローカルhookをグローバルhookへ移行し active-plan を設置" --body "設計書: Obsidian Vault \`00_Claude/specs/2026-09-07-decision-record-hooks-design.md\`

\`claude-config\` 側で導入したグローバル hook に移行する。二重発火を防ぐためローカル hook を撤去し、
実行中の計画ファイルを \`.claude/active-plan\` で宣言する。"
```

期待: PR の URL が出力される。既に PR がある場合は push のみで足りる。

---

### Task 7: 横展開の確認と macOS への配布手段の明記

**Files:**
- Modify: `/Users/yohira/git/claude-config/README.md`
- Modify: `/Users/yohira/Documents/Obsidian-Vault/00_Claude/conversations.md`

**Interfaces:**
- Consumes: Task 8 で `jq` 依存を排除した hook、Task 9 の見出し併記

**注意:** hook は **JSON を返さない**（Task 8 で変更）。SessionStart は平文を stdout、Stop は指示文を stderr に出して終了コード2。`jq` でパースしようとすると失敗する。

- [ ] **Step 1: 全対象リポジトリで受け皿が正しく解決されることを確認する**

```bash
for r in /Users/yohira/git/coopinf /Users/yohira/git/coopbatch /Users/yohira/git/coopcdebatch \
         /Users/yohira/git/alphasystem /Users/yohira/git/alphacdk \
         /Users/yohira/Documents/Obsidian-Vault; do
  echo "===== $(basename "$r")"
  (cd "$r" && echo '{}' | "$HOME/.claude/hooks/record/stop-record-decisions.sh" 2>&1 >/dev/null \
     | grep -E '^    - ' | sed 's/^/  /')
done
```

期待:

| リポジトリ | 出力に含まれるべきパス |
| - | - |
| coopinf | `migration/cutover-plan.md`（段取り） / `conversations.md`（決定） / `migration/LEARNINGS.md`（学び） |
| coopbatch | `conversations.md`（段取りはフォールバック、決定） |
| coopcdebatch | `conversations.md`（同上） |
| alphasystem | `docs/conversations.md` と `alphabsmail/docs/conversations.md` の両方が2回ずつ |
| alphacdk | `conversations.md`（同上） |
| Obsidian Vault | `00_Claude/conversations.md` と `02_Note/社内ネットワーク更改/conversations.md` が2回ずつ |

coopinf だけ `.claude/active-plan` を設置済みのため、段取りの書き先が計画ファイルになり**フォールバック表記が出ない**。

- [ ] **Step 2: SessionStart も全リポジトリで壊れないことを確認する**

```bash
for r in /Users/yohira/git/coopinf /Users/yohira/git/coopbatch /Users/yohira/git/alphasystem \
         /Users/yohira/Documents/Obsidian-Vault; do
  printf "  %-14s " "$(basename "$r")"
  (cd "$r" && "$HOME/.claude/hooks/record/session-start-context.sh" </dev/null >/dev/null 2>&1; echo "exit=$?")
done
```

期待: すべて `exit=0`。注入対象が無いリポジトリでも異常終了しない。

- [ ] **Step 3: git 管理外で発火しないことを確認する**

```bash
cd /tmp
echo '{}' | "$HOME/.claude/hooks/record/stop-record-decisions.sh" 2>&1; echo "  Stop exit=$?"
"$HOME/.claude/hooks/record/session-start-context.sh" </dev/null 2>&1; echo "  SessionStart exit=$?"
```

期待: いずれも何も出力せず `exit=0`。

- [ ] **Step 4: macOS への配布手段を README に明記する**

**背景:** `sync.ps1` は PowerShell 製で Windows 専用。macOS では `~/.claude` へ手でコピーする必要がある。実際、PR #8 をマージしても macOS 実機の hook は古いままだった（2026-09-07 に発覚）。hook を変更するたびに同じ漏れが起きる。

**重要:** コピー対象は `sync.ps1` の `$Targets` **6項目すべて**である。一部だけ列挙すると、対象ファイルを変えて同じ穴を再生産することになる（レビュー指摘）。

```
CLAUDE.md / AGENTS.md / settings.json / keybindings.json / hooks / commands/daily-sync.md
```

ファイル名を並べる代わりに `$Targets` と同じリストでループさせ、`sync.ps1` と同じ意味（ディレクトリは中身ごと置き換える）にする。

```bash
python3 - <<'EOS'
import io
p = '/Users/yohira/git/claude-config/README.md'
s = io.open(p, encoding='utf-8').read()
old = """### 2. このリポジトリの設定を反映する"""
new = """> **macOS には `sync.ps1` が使えない。** PowerShell 製で Windows 専用のため、
> macOS では下のコマンドで手動同期する。**設定や hook を変更したら必ず実行すること。**
> 実際に、hook を更新した PR をマージしたあと macOS 実機だけが古いまま残っていた事例がある。
>
> 対象は `sync.ps1` の `$Targets` と同じ6項目。ディレクトリは中身ごと置き換える
> （コピー元に無いファイルを残さない）。
>
> ```sh
> for t in CLAUDE.md AGENTS.md settings.json keybindings.json hooks commands/daily-sync.md; do
>   src=~/git/claude-config/claude/"$t"
>   dst=~/.claude/"$t"
>   [ -e "$src" ] || continue
>   mkdir -p "$(dirname "$dst")"
>   [ -d "$src" ] && rm -rf "$dst"
>   cp -R "$src" "$dst"
> done
> chmod +x ~/.claude/hooks/record/*.sh
> ```
>
> 反映漏れの確認も同じリストで行う。全項目が `OK` なら同期済み。
>
> ```sh
> for t in CLAUDE.md AGENTS.md settings.json keybindings.json hooks commands/daily-sync.md; do
>   if diff -r ~/.claude/"$t" ~/git/claude-config/claude/"$t" >/dev/null 2>&1; then
>     echo "OK   $t"
>   else
>     echo "DIFF $t"
>   fi
> done
> ```

### 2. このリポジトリの設定を反映する"""
assert old in s
s = s.replace(old, new, 1)
io.open(p, 'w', encoding='utf-8').write(s)
print("README を更新")
EOS
```

検証する。

```bash
cd /Users/yohira/git/claude-config
grep -c 'AGENTS.md keybindings.json hooks commands/daily-sync.md' README.md
for t in CLAUDE.md AGENTS.md settings.json keybindings.json hooks commands/daily-sync.md; do
  if diff -r ~/.claude/"$t" ~/git/claude-config/claude/"$t" >/dev/null 2>&1; then
    echo "OK   $t"
  else
    echo "DIFF $t"
  fi
done
```

期待: `grep -c` が 2（コピー用と確認用の2箇所）。`diff` の結果は現状を示すもので、`DIFF` が出た項目は実機が未同期であることを意味する。**その場合は README のコピー手順を実行して同期し、再度全項目 `OK` になることを確認する。**

- [ ] **Step 5: conversations.md の検証状況を最新化する**

既にエントリ本体は追記済み（Stop hook 自身が促して作成したもの）。**二重に追記しないこと。** 検証状況の表だけを実測に合わせて更新する。

```bash
grep -n "検証状況" -A 8 /Users/yohira/Documents/Obsidian-Vault/00_Claude/conversations.md
```

Step 1〜3 の結果を踏まえ、未確認のまま残っている行があれば更新する。SessionStart（macOS）は Task 7 の Step 2 で終了コード0を確認できるが、**実セッションでの注入確認は別途必要**なため、そこは正直に「未確認」のまま残してよい。

- [ ] **Step 6: コミットする**

claude-config は feature ブランチを切る。Vault は obsidian-git が main を直接同期する運用のため feature ブランチを切らない。

```bash
cd /Users/yohira/git/claude-config
git checkout main && git pull
git checkout -b docs/macos-sync-note
git add README.md
git commit -m "docs: macOS では sync.ps1 が使えず手でコピーする必要がある旨を明記

sync.ps1 は PowerShell 製で Windows 専用。macOS では ~/.claude へ手で
コピーする必要があるが、これが README に書かれておらず、hook を更新した
PR をマージしたあと macOS 実機だけが古いまま残っていた。

コピー手順と、反映漏れを確認する diff コマンドを追記した。

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
git push -u origin docs/macos-sync-note
gh pr create --draft --title "docs: macOS では sync.ps1 が使えず手でコピーする必要がある旨を明記" --body "## 背景

\`sync.ps1\` は PowerShell 製で Windows 専用。macOS では \`~/.claude\` へ手でコピーする必要があるが、README に書かれていなかった。

実際に、\`jq\` 依存を排除した PR #8 をマージしたあと **macOS 実機の hook だけが古いまま**残っていた（2026-09-07 に発覚）。hook を変更するたびに同じ漏れが起きる。

## 対応

README のセットアップ節に、macOS でのコピー手順と、反映漏れを確認する \`diff\` コマンドを追記した。

将来的には macOS 用の同期スクリプト（\`sync.sh\`）を用意する選択肢もあるが、まずは手順の明文化にとどめている。"

cd /Users/yohira/Documents/Obsidian-Vault
git add 00_Claude/conversations.md
git commit -m "docs: hook の横展開確認の結果を反映"
```

期待: PR の URL が出力される。Vault 側は変更が無ければコミット不要。


---

### Task 10: 記録先を conversations.md に集約し、計画ファイルはチェックボックスのみにする

**背景（2026-09-07〜08 ユーザー判断）:** 現在の Stop hook は段取りの書き先として `.claude/active-plan` が指す計画ファイルを提示する。しかし `cutover-plan.md` 等は**手順書も兼ねており**、会話の記録を本文に混ぜると性格が変わる。

あわせて、Obsidian Daily 同期が拾えない事故が起きた。`sections.py` の `DATED_H2_RE` は日付が見出しの**先頭**にあることを要求するが、hook の指示文に**書式の指定が1箇所も無い**ため、セッションごとに違う書式が生まれ黙って落ちる（2026-09-07 に coopinf で実害）。

**変更内容:**

| 対象 | 変更前 | 変更後 |
| - | - | - |
| 段取り（日付・順序） | `active-plan` が指す計画ファイル | **`conversations.md`** |
| 決定・合意 | `conversations.md` | 同じ |
| 学び | `LEARNINGS.md` | 同じ |
| 計画の進捗 | （指示なし） | **チェックボックスを `- [x]` に更新。本文は追記しない** |
| 見出し書式 | （指示なし） | **`## YYYY-MM-DD タイトル` を明示** |
| 日付の解釈 | （指示なし） | **「出来事が起きた日」を使う**（日付跨ぎ対策） |

フォールバックの概念は不要になる（段取りの書き先が常に `conversations.md` のため）。

**Files:**
- Modify: `/Users/yohira/git/claude-config/claude/hooks/record/stop-record-decisions.sh`
- Modify: `/Users/yohira/git/claude-config/tests/test-record-hooks.sh`

**Interfaces:**
- Consumes: Task 2 の `lib.sh`（変更なし）
- Produces: 受け皿ごとに節を分けた指示文。節も項番も、実在する受け皿の分だけ動的に採番する

- [ ] **Step 1: 既存テストのうち、旧仕様に依存するものを洗い出す**

```bash
cd /Users/yohira/git/claude-config
grep -n "フォールバック\|cutover-plan.md\|段取りの書き先\|conversations.md は項番2" tests/test-record-hooks.sh
```

期待: Stop 節のテストが数件ヒットする。これらは新仕様では成り立たないため Step 3 で書き換える。

- [ ] **Step 2: `REASON` の組み立てを節構成に置き換える**

`stop-record-decisions.sh` の `REASON` 組み立て部分（`# 指示文は…` のコメントから `printf '%s\n' "$REASON" >&2` の直前まで）を次に置き換える。

```bash
# 受け皿ごとに節を分ける。実在する受け皿の節だけを出し、項番は通しで採番する。
# 計画ファイルは手順書を兼ねるため、本文への追記はさせずチェックボックスの更新のみとする。
REASON="このターンを振り返ってください。次に該当するものがあれば記録してください。
"
N=0

if [ -n "$CONV" ]; then
  N=$((N + 1)); ITEM_A=$N
  N=$((N + 1)); ITEM_B=$N
  REASON="${REASON}
── conversations.md に追記する ──
書き先:
$(printf '%s' "$CONV" | sed 's/^/    - /')

${ITEM_A}. 日付・時刻・実行順序が確定した段取り
   例:「Task 4 は 9/7 の日中」「9/8 09:30 の自動実行でカットオーバー」
${ITEM_B}. ユーザーの承認・go サイン / 方針変更 / やらないと決めたこと（不作為の決定）
   例:「その方針でいきましょう」「今回はやらない」「B案に変更する」
"
fi

if [ -n "$LEARN" ]; then
  N=$((N + 1))
  REASON="${REASON}
── LEARNINGS.md に追記する ──
書き先:
$(printf '%s' "$LEARN" | sed 's/^/    - /')

${N}. 効いた型・失敗・業務知識・覚えておく価値のある解法
   例:「この切り分け手順が原因特定に効いた」「この仕様は直感に反する」
"
fi

if [ -n "$PLANS" ]; then
  N=$((N + 1))
  REASON="${REASON}
── 計画ファイルを更新する（本文は追記しない）──
対象:
$(printf '%s' "$PLANS" | sed 's/^/    - /')

${N}. 完了したステップのチェックボックスを - [x] にし、実施日を添える
   計画ファイルは手順書を兼ねるため、会話の記録を本文に書き込まないこと
"
fi

REASON="${REASON}
見出しは \`## YYYY-MM-DD タイトル\` 形式にし、日付を必ず先頭に置くこと。
末尾の括弧内に日付を書くと Obsidian Daily 同期のパーサが日付なし見出しと判定し黙ってスキップする。
日付は date コマンドで取得し、出来事が起きた日を使う（セッションが日付を跨ぐ場合に注意）。

重要: 「その件はまだ完了していない」ことは記録しない理由になりません。
決まった時点で記録してください。会話で詰めた具体的な段取りを省略しないこと。

書き先の候補が複数ある場合は話題に最も近いものを選び、判断がつかなければユーザーに確認してください。
いずれにも該当しなければ、ファイルを変更せずそのまま終了してください。"
```

- [ ] **Step 3: テストを新仕様に合わせて書き換える**

旧仕様のテスト（フォールバック表記、段取りの書き先が計画ファイル）は成り立たないため置き換える。`tests/test-record-hooks.sh` の Stop 節を次の内容にする。既存の `== stop-record-decisions.sh ==` の見出しから、その次の `echo "== ` の直前までを差し替える。

```bash
python3 - <<'EOS'
import io
p = '/Users/yohira/git/claude-config/tests/test-record-hooks.sh'
s = io.open(p, encoding='utf-8').read()
start = s.index('echo "== stop-record-decisions.sh =="')
end = s.index('echo "== ', start + 10)
new = """echo "== stop-record-decisions.sh =="
ST="$HOOK_DIR/stop-record-decisions.sh"

# 受け皿の有無で節と項番がどう変わるかを網羅する。
# 期待値は「節の数」と「項番の並び」で表す。
run_stop() {  # $1=repo  -> stderr を stdout に出す
  (cd "$1" && echo '{}' | "$ST" 2>&1 >/dev/null)
}
make_combo() {  # $1=conv $2=learn $3=plan (1/0)
  local d; d=$(make_repo); mkdir -p "$d/.claude" "$d/m"
  [ "$1" = 1 ] && touch "$d/conversations.md"
  [ "$2" = 1 ] && touch "$d/m/LEARNINGS.md"
  [ "$3" = 1 ] && { touch "$d/m/p.md"; printf 'm/p.md\\n' > "$d/.claude/active-plan"; }
  echo "$d"
}

R=$(make_combo 1 0 0)
OUT=$(run_stop "$R")
check "Stop: conv のみ → 節1・項番1,2" "1|1,2," "$(printf '%s' "$OUT" | grep -c '^── ')|$(printf '%s' "$OUT" | grep -oE '^[0-9]+' | tr '\\n' ',')"
check "Stop: conv のみ → 計画節を出さない" "0" "$(printf '%s' "$OUT" | grep -c '計画ファイルを更新')"
check "Stop: 段取りの書き先が conversations.md" "1" "$(printf '%s' "$OUT" | grep -c '^    - conversations.md$')"
check "Stop: フォールバック表記は使わない" "0" "$(printf '%s' "$OUT" | grep -c 'フォールバック')"
rm -rf "$R"

R=$(make_combo 0 1 0)
OUT=$(run_stop "$R")
check "Stop: learn のみ → 節1・項番1" "1|1," "$(printf '%s' "$OUT" | grep -c '^── ')|$(printf '%s' "$OUT" | grep -oE '^[0-9]+' | tr '\\n' ',')"
check "Stop: learn のみ → conversations.md に言及しない" "0" "$(printf '%s' "$OUT" | grep -c 'conversations.md')"
rm -rf "$R"

R=$(make_combo 0 0 1)
OUT=$(run_stop "$R")
check "Stop: plan のみ → 節1・項番1" "1|1," "$(printf '%s' "$OUT" | grep -c '^── ')|$(printf '%s' "$OUT" | grep -oE '^[0-9]+' | tr '\\n' ',')"
check "Stop: plan のみ → チェックボックス更新を指示" "1" "$(printf '%s' "$OUT" | grep -c 'チェックボックスを - \\[x\\] に')"
check "Stop: plan のみ → 本文追記を禁じる" "1" "$(printf '%s' "$OUT" | grep -c '本文に書き込まないこと')"
rm -rf "$R"

R=$(make_combo 1 1 1)
OUT=$(run_stop "$R")
check "Stop: 全部 → 節3・項番1,2,3,4" "3|1,2,3,4," "$(printf '%s' "$OUT" | grep -c '^── ')|$(printf '%s' "$OUT" | grep -oE '^[0-9]+' | tr '\\n' ',')"
check "Stop: 見出し書式を指示する" "1" "$(printf '%s' "$OUT" | grep -c '## YYYY-MM-DD')"
check "Stop: 出来事が起きた日を使うと指示する" "1" "$(printf '%s' "$OUT" | grep -c '出来事が起きた日')"
check "Stop: 未完了は記録しない理由にならない旨" "1" "$(printf '%s' "$OUT" | grep -c '完了していない')"
GOT=$(cd "$R" && echo '{"stop_hook_active":true}' | "$ST" 2>/dev/null; echo $?)
check "Stop: stop_hook_active ならブロックしない" "0" "$GOT"
GOT=$(cd "$R" && echo '{}' | "$ST" >/dev/null 2>&1; echo $?)
check "Stop: ブロックする(終了コード2)" "2" "$GOT"
rm -rf "$R"

R=$(make_combo 0 0 0)
GOT=$(cd "$R" && echo '{}' | "$ST" 2>&1; echo "rc=$?")
check "Stop: 受け皿なしなら無出力でブロックしない" "rc=0" "$GOT"
rm -rf "$R"

R=$(mktemp -d); touch "$R/conversations.md"
GOT=$(cd "$R" && echo '{}' | "$ST" 2>&1; echo "rc=$?")
check "Stop: git管理外なら無出力でブロックしない" "rc=0" "$GOT"
rm -rf "$R"

"""
s = s[:start] + new + s[end:]
io.open(p, 'w', encoding='utf-8').write(s)
print("Stop 節のテストを差し替え")
EOS
```

- [ ] **Step 4: テストを実行する**

```bash
/Users/yohira/git/claude-config/tests/test-record-hooks.sh
```

期待: `FAIL=0` かつ終了コード0。PASS の総数は実測値を報告する。

- [ ] **Step 5: 実リポジトリで出力を確認する**

```bash
cd /Users/yohira/git/coopinf
echo '{}' | "$HOME/.claude/hooks/record/stop-record-decisions.sh" 2>&1 >/dev/null
```

**注意: Step 6 の実機配布より前に実行すると古い版の出力になる。** 配布後に再確認すること。

期待: 3つの節（conversations.md / LEARNINGS.md / 計画ファイル）が出て、項番が 1〜4。段取りの書き先が `conversations.md` になっており、`migration/cutover-plan.md` はチェックボックス更新の対象としてのみ現れる。

- [ ] **Step 6: 実機へ配布する**

macOS には `sync.ps1` が使えないため手でコピーする。

```bash
cp /Users/yohira/git/claude-config/claude/hooks/record/*.sh /Users/yohira/.claude/hooks/record/
chmod +x /Users/yohira/.claude/hooks/record/*.sh
diff -r ~/.claude/hooks/record/ ~/git/claude-config/claude/hooks/record/ && echo "SAME"
```

期待: `SAME`

- [ ] **Step 7: コミットして Draft PR を作成する**

```bash
cd /Users/yohira/git/claude-config
git checkout main && git pull
git checkout -b feature/records-to-conversations
git add claude/hooks/record/stop-record-decisions.sh tests/test-record-hooks.sh
git commit -m "feat: 記録先を conversations.md に集約し計画ファイルはチェックボックスのみにする

計画ファイル(cutover-plan.md 等)は手順書を兼ねており、会話の記録を
本文に混ぜると性格が変わる。段取りの書き先を conversations.md に変更し、
計画ファイルへは完了ステップのチェックボックス更新のみを指示する。

あわせて見出し書式を指示文に明記した。Obsidian Daily 同期のパーサは
日付が見出しの先頭にあることを要求するが、書式の指定が無かったため
セッションごとに違う書式が生まれ黙って落ちていた(2026-09-07 に実害)。
日付は「出来事が起きた日」を使う。セッションが日付を跨ぐため。

受け皿ごとに節を分け、実在する分だけを動的に採番する。
段取りの書き先が常に conversations.md になったため
フォールバックの概念は不要になった。

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
git push -u origin feature/records-to-conversations
gh pr create --draft --title "feat: 記録先を conversations.md に集約し計画ファイルはチェックボックスのみにする" --body "実装計画: Obsidian Vault \`00_Claude/plans/2026-09-07-decision-record-hooks.md\` の Task 10

## 背景

計画ファイル（\`cutover-plan.md\` 等）は**手順書も兼ねている**。会話の記録を本文に混ぜると性格が変わる（2026-09-07 ユーザー指摘）。

あわせて Obsidian Daily 同期が拾えない事故が起きた。\`sections.py\` の \`DATED_H2_RE\` は日付が見出しの**先頭**にあることを要求するが、hook の指示文に書式の指定が無かったため、セッションごとに違う書式が生まれ**黙って落ちていた**。

## 変更

| 対象 | 変更前 | 変更後 |
|---|---|---|
| 段取り | \`active-plan\` が指す計画ファイル | **\`conversations.md\`** |
| 決定・合意 | \`conversations.md\` | 同じ |
| 学び | \`LEARNINGS.md\` | 同じ |
| 計画の進捗 | 指示なし | **チェックボックスのみ更新。本文は追記しない** |
| 見出し書式 | 指示なし | **\`## YYYY-MM-DD タイトル\` を明示** |
| 日付の解釈 | 指示なし | **出来事が起きた日**（日付跨ぎ対策） |

受け皿ごとに節を分け、実在する分だけを動的に採番する。段取りの書き先が常に \`conversations.md\` になったため**フォールバックの概念は不要**になった。

## 検証

受け皿の全8通りの組み合わせで、節の数・項番の連続性・存在しない受け皿の節が出ないことを検査している。"
```

期待: PR の URL が出力される。


---

### Task 11: macOS/Linux 用の `sync.sh` を作り、対象一覧の重複を解消する

**背景:** `sync.ps1` は PowerShell 製で Windows 専用。macOS では README に書いたシェルループを毎回貼る運用になっており現実的でない。さらに**同じ対象一覧が3箇所に重複**している。

1. `sync.ps1` の `$Targets`
2. README のコピー用ループ
3. README の確認用ループ

実際にずれが発生した。`/record` を足して6項目になったのに README の説明文が「同じ5項目」のまま残っている。2026-09-07 の Task 7 レビューで「対象ファイルを変えて同じ穴を再生産している」と指摘されたのと同じ構図。

**方針（2026-09-08 ユーザー判断・B案）:** `sync.sh` を作り、一覧を `sync.ps1` と `sync.sh` の2箇所に集約する。README からは一覧を消す。2箇所のずれは**テストで検出**する。

対案A（`targets.txt` に一覧を置き両方から読む）は不採用。PowerShell 側のパース処理が増え、文字コード事故の再来を招きうるため。

**Files:**
- Create: `/Users/yohira/git/claude-config/sync.sh`
- Create: `/Users/yohira/git/claude-config/tests/test-sync-targets.sh`
- Modify: `/Users/yohira/git/claude-config/README.md`

**Interfaces:**
- Produces: `./sync.sh {pull|push} [--force]`。`sync.ps1` と同じ意味（対象一覧、実行前に一覧表示して確認、ディレクトリは中身ごと置換）

- [ ] **Step 1: 一致検査テストを作る（この時点では落ちる）**

```bash
cat > /Users/yohira/git/claude-config/tests/test-sync-targets.sh <<'EOS'
#!/bin/bash
# sync.ps1 の $Targets と sync.sh の TARGETS が一致することを検査する。
# 一覧が2箇所にあるため、ずれると片方の環境だけ同期漏れが起きる。
set -uo pipefail

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

ps1_targets() {
  awk '/^\$Targets = @\(/{f=1;next} f&&/^\)/{exit} f' "$REPO_ROOT/sync.ps1" \
    | sed -n "s/.*'\(.*\)'.*/\1/p"
}
sh_targets() {
  awk '/^TARGETS=\(/{f=1;next} f&&/^\)/{exit} f' "$REPO_ROOT/sync.sh" \
    | sed -n "s/.*'\(.*\)'.*/\1/p"
}

A=$(ps1_targets)
B=$(sh_targets)

echo "  sync.ps1 の \$Targets:"; printf '%s\n' "$A" | sed 's/^/    /'
echo "  sync.sh の TARGETS:";   printf '%s\n' "$B" | sed 's/^/    /'
echo ""

FAIL=0
if [ -z "$A" ]; then echo "  NG   - sync.ps1 から \$Targets を抽出できない"; FAIL=$((FAIL+1)); fi
if [ -z "$B" ]; then echo "  NG   - sync.sh から TARGETS を抽出できない"; FAIL=$((FAIL+1)); fi
if [ "$A" = "$B" ]; then
  echo "  ok   - 対象一覧が一致している（$(printf '%s\n' "$A" | wc -l | tr -d ' ') 項目）"
else
  echo "  NG   - 対象一覧が一致しない"
  diff <(printf '%s\n' "$A") <(printf '%s\n' "$B") | sed 's/^/         /'
  FAIL=$((FAIL+1))
fi

echo ""
echo "FAIL=$FAIL"
[ "$FAIL" -eq 0 ]
EOS
chmod +x /Users/yohira/git/claude-config/tests/test-sync-targets.sh
/Users/yohira/git/claude-config/tests/test-sync-targets.sh
```

期待: `sync.sh` がまだ無いため `NG - sync.sh から TARGETS を抽出できない` が出て `FAIL` が1以上になる。**ここで落ちることを必ず確認する。**

- [ ] **Step 2: `sync.sh` を作る**

`TARGETS` は `sync.ps1` の `$Targets` と**同じ順序・同じ内容**にすること。

```bash
cat > /Users/yohira/git/claude-config/sync.sh <<'EOS'
#!/bin/bash
# Claude Code の個人設定を ~/.claude とこのリポジトリの間で同期する（macOS / Linux 用）。
#
#   ./sync.sh pull   … ~/.claude  →  このリポジトリ（設定を変えた後に取り込む）
#   ./sync.sh push   … このリポジトリ  →  ~/.claude （新しいPCや他PCへ反映する）
#
# Windows では sync.ps1 を使う。対象一覧は両者で一致させること
# （tests/test-sync-targets.sh が一致を検査する）。
set -uo pipefail

# 同期対象（~/.claude からの相対パス）。sync.ps1 の $Targets と同じ順序・同じ内容にする。
TARGETS=(
  'CLAUDE.md'
  'AGENTS.md'
  'settings.json'
  'hooks'
  'commands/daily-sync.md'
  'commands/record.md'
)

DIRECTION="${1:-}"
FORCE="${2:-}"
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
CLAUDE_HOME="$HOME/.claude"
REPO_STORE="$SCRIPT_DIR/claude"

case "$DIRECTION" in
  pull|push) ;;
  *) echo "usage: ./sync.sh {pull|push} [--force]" >&2; exit 2 ;;
esac
[ -d "$CLAUDE_HOME" ] || { echo "Claude Code の設定ディレクトリが見つかりません: $CLAUDE_HOME" >&2; exit 1; }
mkdir -p "$REPO_STORE"

if [ "$DIRECTION" = "pull" ]; then
  SRC_ROOT="$CLAUDE_HOME"; DST_ROOT="$REPO_STORE"
  LABEL="$CLAUDE_HOME  ->  $REPO_STORE  （リポジトリ側を上書き）"
else
  SRC_ROOT="$REPO_STORE"; DST_ROOT="$CLAUDE_HOME"
  LABEL="$REPO_STORE  ->  $CLAUDE_HOME  （~/.claude 側を上書き）"
fi

echo ""; echo "$LABEL"; echo ""

PLAN=()
for t in "${TARGETS[@]}"; do
  src="$SRC_ROOT/$t"
  dst="$DST_ROOT/$t"
  if [ ! -e "$src" ]; then
    printf '  skip       %s  (コピー元に存在しない)\n' "$t"
    continue
  fi
  state=$([ -e "$dst" ] && echo "上書き" || echo "新規")
  printf '  %-9s  %s\n' "$state" "$t"
  PLAN+=("$t")
done

if [ "${#PLAN[@]}" -eq 0 ]; then
  echo ""; echo "コピー対象がありません。"; exit 0
fi

if [ "$FORCE" != "--force" ] && [ "$FORCE" != "-f" ]; then
  echo ""
  printf '実行しますか (y/N): '
  read -r answer
  if [ "$answer" != "y" ]; then echo "中止しました。"; exit 0; fi
fi

for t in "${PLAN[@]}"; do
  src="$SRC_ROOT/$t"
  dst="$DST_ROOT/$t"
  mkdir -p "$(dirname "$dst")"
  # ディレクトリは中身ごと置き換える（コピー元に無いファイルを残さない）
  [ -d "$src" ] && rm -rf "$dst"
  cp -R "$src" "$dst"
  printf '  done       %s\n' "$t"
done

[ -d "$DST_ROOT/hooks/record" ] && chmod +x "$DST_ROOT/hooks/record/"*.sh 2>/dev/null

echo ""
if [ "$DIRECTION" = "pull" ]; then
  echo "取り込みました。git diff で差分を確認してからコミットしてください。"
else
  echo "反映しました。Claude Code を再起動すると設定が読み込まれます。"
fi
EOS
chmod +x /Users/yohira/git/claude-config/sync.sh
```

- [ ] **Step 3: 一致検査テストが通ることを確認する**

```bash
/Users/yohira/git/claude-config/tests/test-sync-targets.sh
```

期待: `ok - 対象一覧が一致している（6 項目）` と `FAIL=0`。

- [ ] **Step 4: 偽の HOME で動作を検証する（実機を壊さない）**

```bash
cd /Users/yohira/git/claude-config
FAKE=$(mktemp -d); mkdir -p "$FAKE/.claude"
echo "--- push（初回）---"
HOME="$FAKE" ./sync.sh push --force
echo "--- 配置結果 ---"
find "$FAKE/.claude" -type f | sed "s|$FAKE/.claude|~/.claude|" | sort
echo "--- 2回目（入れ子にならないか）---"
HOME="$FAKE" ./sync.sh push --force >/dev/null
[ -d "$FAKE/.claude/hooks/hooks" ] && echo "NG: 入れ子ができた" || echo "OK: 入れ子なし"
ls -l "$FAKE/.claude/hooks/record/lib.sh" | cut -c1-11
echo "--- 引数なし ---"
HOME="$FAKE" ./sync.sh; echo "exit=$?"
rm -rf "$FAKE"
```

期待: 6項目が配置される。2回目でも `hooks/hooks` は作られない。`lib.sh` は `-rwxr-xr-x`。引数なしは usage を出して `exit=2`。

- [ ] **Step 5: README から一覧の重複を消す**

macOS 向けのブロック（`> **macOS には ...` から `### 2. このリポジトリの設定を反映する` の直前まで）を差し替える。

```bash
python3 - <<'EOS'
import io
p = '/Users/yohira/git/claude-config/README.md'
s = io.open(p, encoding='utf-8').read()
start = s.index('> **macOS には `sync.ps1` が使えない。**')
end = s.index('### 2. このリポジトリの設定を反映する')
new = """> **macOS / Linux では `sync.ps1` の代わりに `sync.sh` を使う。**
> `sync.ps1` は PowerShell 製で Windows 専用のため。
>
> ```sh
> ./sync.sh push    # このリポジトリ  →  ~/.claude
> ./sync.sh pull    # ~/.claude  →  このリポジトリ
> ```
>
> **設定や hook を変更したら必ず実行すること。** 実際に、hook を更新した PR を
> マージしたあと macOS 実機だけが古いまま残っていた事例がある。
>
> 対象一覧は `sync.ps1` の `$Targets` と `sync.sh` の `TARGETS` の2箇所にある。
> ずれると片方の環境だけ同期漏れが起きるため、`tests/test-sync-targets.sh` が
> 一致を検査する。**対象を増やすときは両方に足すこと。**

"""
s = s[:start] + new + s[end:]
io.open(p, 'w', encoding='utf-8').write(s)
print("README を更新")
EOS
grep -n "sync.sh\|5項目\|6項目" /Users/yohira/git/claude-config/README.md
```

期待: `sync.sh` の記述が現れ、**「5項目」の記述が消えている**こと。README 内にコピー用・確認用のループが残っていないこと。

- [ ] **Step 6: 全テストを実行する**

```bash
cd /Users/yohira/git/claude-config
./tests/test-sync-targets.sh | tail -3
./tests/test-ascii-only.sh | tail -2
./tests/test-record-hooks.sh | tail -2
```

期待: いずれも `FAIL=0`。`test-ascii-only.sh` は `*.ps1` のみを対象とするため `sync.sh` の日本語は問題ない。

- [ ] **Step 7: 実機で `./sync.sh push` を実行して同期する**

```bash
cd /Users/yohira/git/claude-config
./sync.sh push --force
for t in CLAUDE.md AGENTS.md settings.json hooks commands/daily-sync.md commands/record.md; do
  diff -r ~/.claude/"$t" ~/git/claude-config/claude/"$t" >/dev/null 2>&1 && echo "OK   $t" || echo "DIFF $t"
done
```

期待: 6項目すべて `OK`。

- [ ] **Step 8: コミットして Draft PR を作成する**

```bash
cd /Users/yohira/git/claude-config
git checkout main && git pull
git checkout -b feature/sync-sh
git add sync.sh tests/test-sync-targets.sh README.md
git commit -m "feat: macOS/Linux 用の sync.sh を追加し対象一覧の重複を解消する

sync.ps1 は PowerShell 製で Windows 専用のため、macOS では README に
書いたシェルループを毎回貼る運用になっていた。さらに同じ対象一覧が
3箇所(sync.ps1 の \$Targets / README のコピー用ループ / README の確認用ループ)
に重複しており、実際にずれが発生していた(/record を足して6項目になったのに
README の説明文が「同じ5項目」のまま残っていた)。

sync.sh を追加して一覧を2箇所に減らし、README からは一覧を消した。
残る2箇所のずれは tests/test-sync-targets.sh が検出する。

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
git push -u origin feature/sync-sh
gh pr create --draft --title "feat: macOS/Linux 用の sync.sh を追加し対象一覧の重複を解消する" --body "実装計画: Obsidian Vault \`00_Claude/plans/2026-09-07-decision-record-hooks.md\` の Task 11

## 背景

\`sync.ps1\` は PowerShell 製で **Windows 専用**。macOS では README に書いたシェルループを毎回貼る運用になっており現実的でなかった。

さらに**同じ対象一覧が3箇所に重複**していた。

1. \`sync.ps1\` の \`\$Targets\`
2. README のコピー用ループ
3. README の確認用ループ

実際にずれが発生した。\`/record\` を足して6項目になったのに README の説明文が「同じ5項目」のまま残っていた。

## 対応（B案・ユーザー判断）

- \`sync.sh\` を追加。\`./sync.sh push\` / \`./sync.sh pull\` の1コマンドにする
- README から一覧を消す（重複3箇所 → 2箇所）
- 残る2箇所のずれは \`tests/test-sync-targets.sh\` が検出する

対案A（\`targets.txt\` に一覧を置き両方から読む）は不採用。PowerShell 側のパース処理が増え、\`sync.ps1\` で起きた文字コード事故の再来を招きうるため。

## 検証

- 一致検査テストは、わざと一覧をずらすと確実に落ちることを確認済み
- \`sync.sh\` は偽の \`HOME\` で検証。6項目の配置、2回実行しても \`hooks/hooks\` の入れ子ができないこと、実行権が付くこと、引数なしで usage を出して \`exit=2\` になることを確認"
```

期待: PR の URL が出力される。


## タスク依存関係

```
Task 1（claude-config を安全な状態に）
   └→ Task 2（lib.sh + テスト）
        ├→ Task 3（SessionStart hook）─┐
        └→ Task 4（Stop hook）─────────┴→ Task 5（settings.json + CLAUDE.md + 実機確認）
                                              ├→ Task 6（coopinf 移行）
                                              └→ Task 7（横展開の確認）
```

Task 3 と Task 4 は独立して並行実施できる。Task 6 と Task 7 も Task 5 完了後は並行可能。
