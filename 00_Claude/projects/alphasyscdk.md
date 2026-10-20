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

## 2026-10-20 alphasystem からの申し送り受領（情報共有のみ）

- **経緯**: `INBOX_FROM_ALPHASYSTEM.md` で alphasystem から申し送りを受領。取り込み後にファイルを削除した。
- **内容**:
  - 依頼作業はなし（情報共有のみ）。
  - PR #99（staging の desiredCount=1 固定、Draft）はユーザーのマージ待ち。
  - PR #99 マージ後、次回 StagingStack デプロイ前に `cdk diff` で `AUTH_URL` に差分が無いことを確認する（正: `https://alphasys.alphacmc-test.com`）。別 PC の `.env.staging` に古い値が残っている可能性がある。
  - 本番環境（ProductionStack 等）は、staging の目処が立つまで着手しない（ユーザー決定 2026-10-19）。
- **次のアクション**: PR #99 マージ後の StagingStack デプロイ時に、上記 `cdk diff` の確認を行う。

## 2026-10-20 alphasystem 申し送りファイルの取り扱いルールを決定

- **経緯**: ユーザーから `INBOX_FROM_ALPHASYSTEM.md` の処理を依頼された際に、今後の扱いも指示された。
- **結論**: 今後もリポジトリ直下に `INBOX_FROM_ALPHASYSTEM.md` があれば、本ファイル（docs/conversations.md）に日付見出しで取り込み、取り込み後に削除する（恒常ルール）。

## 2026-10-20 PR ＃99（staging desiredCount=1 固定）マージ

- **経緯**: ユーザーが PR #99 をマージした（staging のマージコミット 4a0f4c6）。
- **状況**: この PC には `.env` / `.env.staging` が無い（`.example` だけ）ため、ここでは `npm run diff:staging` が実行できない（`bin/app.ts` の必須環境変数チェックで止まる）。
- **次のアクション**: StagingStack をデプロイする PC で、デプロイ前に `npm run diff:staging` を実行し、`AUTH_URL` に差分が無いことを確認する（正: `https://alphasys.alphacmc-test.com`）。差分があれば、その PC の `.env.staging` を直してからデプロイする。

## 2026-10-20 StagingStack デプロイ前の cdk diff 確認（PR ＃99 マージ後）

- **経緯**: ユーザーがこの PC に `.env` / `.env.staging` を用意したため、`npm ci` を行ってから `npm run diff:staging` を実行した。
- **結果**:
  - `.env.staging` の `AUTH_URL` は正しい値（`https://alphasys.alphacmc-test.com`）だった。
  - SharedStack は差分なし。
  - StagingStack の差分は `ECSUnifiedServiceA2C1AAA2` の `DesiredCount` が 2 → 1 になることだけ（PR #99 の意図どおり）。`AUTH_URL` を含むタスク定義には差分が無い。
  - 補足: いまの cdk CLI では `cdk diff --all` を実行すると「Unknown option(s): --all」という警告が出る（両スタックとも diff は取れている）。
- **次のアクション**: ユーザーの了解を得てから `npm run deploy:staging` を実行する。

## 2026-10-20 StagingStack デプロイ実施（PR ＃99 反映）

- **経緯**: ユーザーの go サインを受けて、2026-10-20 11:13〜11:15 に `npm run deploy:staging` を実行した。
- **結果**:
  - SharedStack は CDK メタデータの更新だけで完了した。
  - StagingStack は ECS サービス（`ECSUnifiedServiceA2C1AAA2`）が UPDATE_COMPLETE になった。
  - デプロイ後の `staging-alphasys-cluster` は desired=1 / running=1 / pending=0 で、デプロイのロールアウトは COMPLETED。
- これで PR #99 の申し送り（デプロイ前の `AUTH_URL` 差分確認と、デプロイ）は完了した。
