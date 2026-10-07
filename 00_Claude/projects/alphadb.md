# alphadb 作業ログ

## 2026-10-06 夜間自動移行

- 方式: 既存 Bastion EC2 の systemd timer（JST 1:00）で実行。新規AWSリソースはロググループのみ。通知先は CloudWatch Logs。
- バックアップ: `s3://alpha-conbackup/alphadb.dmp`（旧システム側アカウント alphacmc / 525459588860。毎日 JST 0:00 に上書き。約4MB。SSE=AES256）。
- 毎晩「移行対象14テーブルを全消しして入れ直す」ことを了承。
- **`alp_customer_domain` / `alp_sales_email` / `alp_sales_email_contract_link` は現行システムに存在しない新システム側のテーブルで、移行処理の対象外**。夜間処理は TRUNCATE ... CASCADE を使わず、14テーブルだけを DELETE（FK検査停止）で入れ替え、3テーブルは触らない（Task 8）。
- 旧システム側 S3 のバケットポリシー（Bastion ロールへの `s3:GetObject`）は、JSON を提示し**利用者が適用する**。
- alphasyscdk のステージングデプロイは、正しい `AUTH_URL`（`.env.staging`）を利用者に確認し、`cdk diff` で ECS の差分が消えたことを確認してから StagingStack のみ実施する。

## 2026-10-06 ステージング Bastion への反映（Task 6/7）

- alphasyscdk PR #89（Draft）: Bastion の IAM（マスターシークレット読取・S3 GetObject）とロググループ `/alphasys/staging/nightly-migration`。**未デプロイ**（`cdk diff` に `AUTH_URL` 由来の ECS タスク定義置換が混ざるため、正しい値の確認待ち。ローカル `.env.staging` は `alphasys`、稼働中は `alphasystem`）。
- 旧システム側バケットポリシー（`nightly/alpha-conbackup-bucket-policy.json`）は利用者が適用する（現在バケットポリシーは無い）。
- Bastion（i-003e0a8a835bf70f8）へ配布済み（`deploy.sh`）・`setup_bastion.sh` 実行済み・`/etc/alphadb-migration.env` 設定済み。PostgreSQL サーバ稼働。タイマーは有効化のみで**未起動**。
- 未実施: 手動1回実行、失敗系の実機確認、タイマー起動（バケットポリシーと CDK デプロイが前提）。

## 2026-10-06 夜間自動移行 Task 6/7 の進め方と段取り

- 承認: Task 6（インフラ前提）/ Task 7（Bastion 実機）を進めてよい、とユーザーが指示。3テーブル除外は「DELETE + FK検査停止」案を選択。
- 実行順序（確定）: (1) 利用者が旧システム側バケットポリシーを適用 → (2) 利用者が正しい `AUTH_URL` を回答 → 私が `cdk diff` で ECS 差分が消えたことを確認して StagingStack のみデプロイ → (3) Bastion で手動1回実行（`systemctl start alphadb-migration.service`）→ (4) 失敗系の実機確認（`DUMP_URI` を存在しないキーに一時変更）→ (5) タイマー起動（`systemctl start alphadb-migration.timer`）→ 翌朝 CloudWatch で `RESULT: SUCCESS` を確認。
- やらないと決めたこと: `TRUNCATE ... CASCADE` を夜間処理で使わない。`load.sql` / `extract.sql` / `verify.sql` / `reset_sequences.sql` と手動用 `.ps1` は変更しない。

## 2026-10-06 夜間自動移行 ステージング反映の完了と Bastion 置換の発見

- ユーザーがバケットポリシーを適用。正しい `AUTH_URL` は `https://alphasys.alphacmc-test.com`（稼働中 ECS は `alphasystem` で、これが `redirect_uri_mismatch` の原因とみられる）。
- alphasyscdk を StagingStack のみデプロイ（PR #89）。ECS の AUTH_URL が `alphasys` に訂正され、サービスは 2/2 で安定。**同時に Bastion が置換された**（手動導入分が消えたため配布・セットアップ・設定をやり直した）。
- 実機の手動1回実行は `RESULT: SUCCESS`。失敗系（`DUMP_URI` 不正）は `RESULT: FAILED (STEP check-freshness) rc=254`。タイマーを起動し、次回は JST 1:00 から自動実行。
- 未決（要判断）: Bastion 置換への恒久対応（UserData で自動化 / AMI 固定 / 無音停止の検知アラーム）。詳細は nightly_automation.md §7。

## 2026-10-06 夜間自動移行 今夜以降の段取り

- 今夜 JST 1:00（UTC 16:00）に初回の自動実行。翌朝、CloudWatch Logs `/alphasys/staging/nightly-migration` の最新ストリームで `RESULT: SUCCESS` を確認する。ログストリームが作られていなければ Bastion が置換された疑い（復旧手順は nightly_automation.md §7）。
- 利用者側の確認事項: `AUTH_URL` 訂正後にログイン（`redirect_uri_mismatch`）が直ったか。
- 決定待ち: Bastion 置換への恒久対応（UserData で自動化 / AMI 固定 / 無音停止の検知アラーム。推奨は UserData 自動化 + 検知アラーム）。

## 2026-10-06 夜間自動移行 Bastion 置換への対応方針（やらないと決めたこと）

- `AUTH_URL` 訂正後、ユーザーが認証成功を確認（`redirect_uri_mismatch` は解消）。
- **やらない**: Bastion の UserData への PostgreSQL 導入・タイマー設定の組み込み / AMI 固定 / 無音停止の検知アラーム。理由: 当該 EC2 は夜間移行専用ではなく、並行稼働期間中の一時的な利用であるため。確認期間中はユーザーが毎日 CloudWatch Logs を目視確認する。
- 方針: **通常運用ではないもの（並行稼働中だけの処理）は CDK に組み入れない。** Bastion が置換された場合は nightly_automation.md §7 の手順（deploy.sh → setup_bastion.sh → env 再作成 → タイマー起動）で手動復旧する。

## 2026-10-06 夜間自動移行 PR ＃89（IAM・ロググループ）の扱い

- 確認待ち: 「通常運用ではないものは CDK に入れない」方針と、デプロイ済みの alphasyscdk PR #89（Bastion の IAM 権限 + ロググループ `/alphasys/staging/nightly-migration`）にずれがある。提案は「並行稼働が終わるまで維持し、終了時に削除」。ユーザーの回答待ち（特に指示がなければ維持）。
- 段取り（案）: 並行稼働の終了時に、タイマー停止（`systemctl stop alphadb-migration.timer`）→ PR #89 の変更を CDK から削除 → 旧システム側 `alpha-conbackup` のバケットポリシーを削除。PR #56 / #89 のマージはユーザーが行う。

## 2026-10-06 夜間自動移行 マージ完了と PR ＃89 の扱いの確定

- ユーザーが alphadb PR #56 と alphasyscdk PR #89 を staging にマージ（確認済み。マージ後の `cdk diff StagingStack` は差分なし）。
- PR #89（Bastion の IAM 権限・ロググループ）は**そのまま CDK に維持**する扱いで確定（マージによる承認）。
- 並行稼働の終了時の片付け（案どおり）: Bastion で `systemctl stop alphadb-migration.timer` → PR #89 の変更を CDK から削除 → 旧システム側 `alpha-conbackup` のバケットポリシー削除。
- 今夜 JST 1:00 が初回の自動実行。翌朝 CloudWatch Logs `/alphasys/staging/nightly-migration` で `RESULT: SUCCESS` を確認する（ユーザーが並行稼働期間中は毎日目視）。

- 2026-10-06 ユーザーの承認により、ローカル検証用の Docker（`alphadb-source` / `alphadb-target` / ネットワーク `alphadb-net`）を削除。再度ローカルで通し実行（`nightly/tests/integration_local.sh`）する場合は、これらを作り直し、移行先に Prisma のマイグレーションを適用してから実行する。
