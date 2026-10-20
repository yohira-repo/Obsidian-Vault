# coopcdeweb 作業ログ

## 2026-10-20 coop の運用規則を取り込む

- **経緯**: coop から `INBOX_FROM_COOP.md` で申し送り（coop の conversations/2026-10-20.md「coopcdeweb・coops3view・coopcdealert にも運用規則を申し送る」）。
- **取り込んだ内容**:
  - 位置付け: coopcdeweb は Web担当。全体調整は coop。
  - 連携: `ListAgents`/`SendMessage` で直接送る。未起動なら相手リポジトリ直下に未追跡の `INBOX_FROM_<送り元>.md`。サブエージェントは記録不要の閉じた調査に限る。
  - 記録の置き場: 設計の決定は coop、実装計画以降はこのリポジトリ。結合試験は coop が担当。
  - ブランチ: main/staging の 2 本立ては採用しない。main をベースにする。
  - coopcdeinput・coopcdebatch は構成外（coopcdebatch は旧ロジックの参照元としてのみ読む）。
- **実施**: `CLAUDE.md` を新規作成（coop の CLAUDE.md に従う旨とリンク）、`conversations/`（README と本ファイル）を作成。受信ファイル `INBOX_FROM_COOP.md` は取り込み後に削除。

## 2026-10-20 denkiTanka1〜3Array の用途確認

- **質問（ユーザー）**: `denkiTanka1Array`・`denkiTanka2Array`・`denkiTanka3Array` は DB 書き込みに使われているか。
- **回答**: 使われていない。参照は `members.service.ts` の `getDenkiTanka1/2/3` のみで、電気請求明細の API レスポンス（`rate1Tanka`〜`rate3Tanka`）に詰めて画面（`DenkiBillMonthlyTable.tsx`）に単価として表示するだけ。DB の請求データ（`rate1` 等の金額）は読み取り専用で、単価は保存されない。
