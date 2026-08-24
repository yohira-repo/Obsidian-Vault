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
