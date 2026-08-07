
## 概要

コープガス、コープでんき（実はCDE)の連携データを元に、料金、数量のデータを会員マイページおよび管理機能に表示する。

## 連携データ
- 契約データ（新規、更新、解約）
- 請求データ（利用月の翌月に請求）
- 速報値データ（検針終了後の速報値）

## 全体構成
- ドキュメント
  - 当初のドキュメント（https://drive.google.com/drive/folders/15IA_PGpCoTHMoZ3zS73ApfOauh3g4UoG）
  - バッチドキュメント（ https://github.com/alphacmc/coop ）
- インフラ構築( https://github.com/alphacmc/coopinf )
- Webアプリ（ https://github.com/alphacmc/coopcdeweb ）
- バッチ（ https://github.com/alphacmc/coopcdebatch ）
  - 次期バッチ（ https://github.com/alphacmc/coopbatch ）
-  運用サポート
  - CloudWatch Arert（ https://github.com/alphacmc/coopcdealert ）
  - S3 CSVビューア（ https://github.com/alphacmc/coops3view ）

## 現在状況
- 次期バッチ追加（コープにいがた、コープながの）に向けて、バッチリファクタリング試験中
  - 深夜に本番環境->ステージング環境に同期
  - 翌日バッチ処理終了後に、インプットCSVを本番環境->ステージング環境に送信、coopbatchを実行
  - 本番環境：ステージング環境テーブル比較（除く、タイムスタンプ列：created_at,updated_atなど）
- CSVフォーマット受領済み

# キャッチアッププラン

- [x] 全体説明（8/4）
- [x] Web手順書に沿った操作確認（ステージング環境）（8/5）
- [x] バッチ処理確認（随時）
- [ ] 詳細説明(8/6,7)
  - [ ] インフラ
  - [ ] バッチ
  - [ ] Web
  - [ ] 運用サポート
  