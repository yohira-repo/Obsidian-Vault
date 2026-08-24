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
