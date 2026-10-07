# alphasyscdk 作業ログ

## 2026-10-07 RDSインスタンスクラス縮小の方針確定

- 方針: RDS(Aurora PostgreSQL 16)の既定を `db.r6g.large` → `db.t4g.medium`（Aurora PostgreSQLで選べる最小クラス）に変更する。
  - 根拠: データ量は数GB、利用者は100名未満。
- 対象範囲の判断:
  - staging: 変更する。
  - prod: 未構築のため触らない。インスタンス数は `2`（Multi-AZ）のまま据え置く。構築時は同じ既定値(`t4g.medium`)が適用される。
- やらないと決めたこと: Aurora Serverless v2 への移行（ローテーションLambda・clone・同期ステートマシンに影響し範囲が大きいため）。
- 実施: `lib/constructs/rds.ts` の既定値と `README.md` の context 表を更新。Draft PR #91（base: staging）。
  - `cdk diff StagingStack` の差分は `DBInstanceClass` のみ（置換なし）。
- 段取り: staging への即時デプロイはユーザーが手動で実施する。
  - コマンド: `npm run build` → `npx cdk deploy StagingStack --profile staging`（feature/rds-smaller-instance ブランチ上）。
  - `npm run deploy:staging` は `--all --require-approval never` のため使わない。
  - デプロイ後に `describe-db-instances` でクラスを確認し、PR #91 の Test plan を完了させる。
