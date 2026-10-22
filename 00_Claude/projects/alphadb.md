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

## 2026-10-08 設計バグ対応: 契約（Contract）への取引先番号の追加（alphadb 側）

- 発端: alphasystem で確定した仕様（`alphasystem/docs/design/2026-10-08-契約への取引先追加-仕様.md`）。プロジェクトの受発注一体化により Contract が取引先を持たず、発注先（仕入先）が記録できない設計バグ。
- 仕様: `Contract.customerNo` を**必須**で追加。受注契約=受注先（`Project.customerNo` と同値）、発注契約・仮契約=発注先。移行では**付け替え前の `project_id` が指すプロジェクトの `customer_no`**を取る（`alp_contract.customer_no` は使わない）。
- 実データ検証（9/24 ダンプ）: 発注契約 3,338 件はすべて付け替え前PJが発注PJ（受注PJを指す行は 0 件）。仮契約・親なしは 0 件。受注契約のうち 5 件は付け替え前PJが発注PJだが、現行の抽出条件で除外済みのため影響なし。
- 承認（ユーザー回答）: (1) Customer への**外部キー + index を付ける**、(2) バージョンは **0.1.0（minor）**、(3) ステージング反映は **PR マージ後、同日中に続けて実施**（マイグレーション適用 → `deploy.sh` で SQL 配布 → 手動1回実行 = 再投入）。途中で夜間実行（JST 1:00）が走ると、その夜は失敗する（ロールバックされ前日のデータが残る）ため、夜間実行より前に完了させる。
- alphadb の作業: schema.prisma / マイグレーション（NULL許容で追加 → Project から埋める → NOT NULL → FK・index）/ `extract.sql` 03 contract / `load.sql` 列リスト / `verify.sql`・夜間 `check.sql` の整合チェック / ドキュメント / 0.1.0 で publish。alphasys の画面修正は alphasys のセッションで行う（alphadb は 0.1.0 を publish するまで）。

- 2026-10-08 実装を完了し Draft PR #60（base: staging）を作成。ユーザーのレビュー・マージ待ち。マージ後の段取り（同日中、夜間実行 JST 1:00 より前）: (1) `alphadb-publish` で 0.1.0 を publish → (2) ステージングにマイグレーション適用（適用方法＝CodeBuild 経由か手動かは、マージ後に確認してから実施）→ (3) `nightly/deploy.sh` で Bastion に SQL 配布 → (4) 手動で1回実行（再投入）→ (5) 発注契約の取引先がプロジェクトと異なることを確認。
- alphasys は 0.1.0 に更新し、契約の追加・編集で取引先を扱う（alphasys のセッションで実施。alphadb では行わない）。

## 2026-10-08 契約への取引先追加 ステージング反映の完了

- PR #60 をユーザーがマージ（alphadb `main` へも PR #61 で反映済み）。反映は同日中（12:2x〜12:3x JST）に実施し、夜間実行（JST 1:00）より前に完了。
- 実施内容: (1) `alphadb-publish`（CodeBuild）で 0.1.0 を publish（CodeArtifact に 0.0.1 / 0.1.0 / 1.0.0 が存在）→ (2) `staging-prisma-merge-project-build`（CodeBuild。CDK の BuildTrigger と同じ。alphadb `main` から `prisma migrate deploy`）でマイグレーション `20261008120000_add_contract_customer_no` を適用（既存 6,337 契約が全件 NOT NULL）→ (3) `nightly/deploy.sh` で Bastion に新SQLを配布 → (4) 手動で1回実行（再投入）= `RESULT: SUCCESS`・`check ok`。
- 結果（集計）: 受注契約 2,927 件は全件プロジェクトの取引先と一致、発注契約 3,410 件は全件プロジェクトと相違（発注先）。Track1 の `alp_sales_email`（740 件）は保持。
- 影響: ステージングの alphasys（alphadb 0.0.1 使用）は、契約の**新規作成が NOT NULL 違反で失敗**する（`customer_no` を渡していないため）。alphasys を 0.1.0 に更新し、契約の追加・編集で取引先を扱うまで解消しない（alphasys のセッションで実施）。

## 2026-10-13 MFクラウド連動 alphadb側スキーマ追加の方針確定

- 発端: alphasystem の仕様（`alphasystem/docs/design/2026-10-09-MFクラウド連動-仕様.md`、前提のタスク0仕様 `2026-07-27-task0-mf-api-foundation-spec.md`）のうち alphadb 担当分の検討依頼。完了後に alphasys/alphaexapi へ修正依頼予定とのこと。
- 現状確認: 前提1「契約への取引先追加」は実装済み（PR #60/#61/#62、ステージング反映済み）。前提2「タスク0（MfOauthToken/MfLink）」は 2026-07-27 に実装計画まで書かれていたが、**alphadb・alphaexapi・alphasys いずれにも未着手**（該当PR/ブランチなし、schema.prismaにMf*定義なし）と判明。
- 承認（ユーザー回答）:
  1. **PRは2つに分ける**（既存計画通り）。まずタスク0分（`MfOauthToken`/`MfLink`/`MfProduct`/`MfEntityType`/`MfSyncStatus`）のPRを作り、その後に7章分（`MfJob`/`MfJobDetail`/`MfJobType`/`MfJobStatus`/`MfJobDetailResult`）のPRを作る。
  2. `MfJobDetail.contractNo` / `customerNo` は Contract/Customer への正式リレーションを張らず、`SalesEmail.suggestedContractNo` と同様の**緩い参照**（Int型のみ、リレーションなし）にする。
- 着手: `feature/add-mf-integration-schema` ブランチ（staging起点）で `MfOauthToken`/`MfLink` と関連3 enumを `schema.prisma` に追加し `prisma validate` 成功を確認。マイグレーションSQL生成（`prisma migrate diff`、DB接続不要な方式）を試みたところ、ローカル `.env` の接続先（`localhost:5434` の `track1_dev`）が未起動で、起動中の docker コンテナ（`pgsql_db`, port 5432）には alphadb 用DBが存在しないことが判明。ユーザーがコンテナ状況を確認中のため作業中断（**マイグレーションSQLファイルは未生成、schema.prismaの変更はコミット前**）。

## 2026-10-13 MFクラウド連動 alphadb側スキーマ追加の方針確定と実装

- 発端: alphasystem の仕様（`alphasystem/docs/design/2026-10-09-MFクラウド連動-仕様.md`、前提のタスク0仕様 `2026-07-27-task0-mf-api-foundation-spec.md`）のうち alphadb 担当分の検討依頼。完了後に alphasys/alphaexapi へ修正依頼予定とのこと。
- 現状確認: 前提1「契約への取引先追加」は実装済み（PR #60/#61/#62、ステージング反映済み）。前提2「タスク0（MfOauthToken/MfLink）」は 2026-07-27 に実装計画まで書かれていたが、**alphadb・alphaexapi・alphasys いずれにも未着手**（該当PR/ブランチなし、schema.prismaにMf*定義なし）と判明。
- 承認（ユーザー回答）:
  1. **PRは2つに分ける**（既存計画通り）。まずタスク0分（`MfOauthToken`/`MfLink`/`MfProduct`/`MfEntityType`/`MfSyncStatus`）のPRを作り、その後に7章分（`MfJob`/`MfJobDetail`/`MfJobType`/`MfJobStatus`/`MfJobDetailResult`）のPRを作る。
  2. `MfJobDetail.contractNo` / `customerNo` は Contract/Customer への正式リレーションを張らず、`SalesEmail.suggestedContractNo` と同様の**緩い参照**（Int型のみ、リレーションなし）にする。
- ローカルDB: ユーザーがdockerコンテナを新システム用（`alphaexapi-postgres-1`, postgres:16, port 5432, db `alphasys`）に変更。`.env` をこれに合わせて修正（`postgresql://postgres:postgres@localhost:5432/alphasys`）。既存7マイグレーション適用済みで健全なことを確認。
- 実装・PR作成:
  - PR #64（タスク0: `MfOauthToken`/`MfLink`、`feature/add-mf-integration-schema`、base: staging）。`prisma migrate dev`で実際にローカルDBへ適用し、生成Prisma Clientの型（`prisma.mfOauthToken`/`prisma.mfLink`、複合ユニーク名`entityType_localId_mfProduct`）を確認、`npm test`通過。
  - PR #65（7章: `MfJob`/`MfJobDetail`、`feature/add-mf-job-schema`、base: staging、PR #64とは独立・依存なし）。このブランチはPR #64のマイグレーションを含まないため、ローカル共有DBとの履歴不整合（ドリフト）を避ける目的で、一時シャドウDB（`alphadb_shadow_tmp`。生成後に削除済み）を使った`prisma migrate diff`でSQLのみ生成し、実DBには未適用（型確認は`prisma generate`のみで実施）。
  - 両PRとも `prisma/doc/table_design.md` ＋ `prisma/doc/tables/alp_mf_*.md` を同時更新。既存テーブルへの`ALTER`/`DROP`は含まれない（追加のみ）ことを確認済み。
- 残作業: PR #64→#65の順でユーザーがレビュー・マージ。マージ後、ステージングDBへのマイグレーション適用・publishの要否・手順は契約取引先追加（2026-10-08）と同様の流れになる見込み（実施前に確認）。alphasys/alphaexapiへの修正依頼は、このalphadb対応の完了後にユーザーが行う予定。

## 2026-10-13 PR ＃64/＃65 マージ時のコンフリクトでschema.prismaが破損（発見・修正）

- ユーザーがPR #64・#65を`staging`へマージ。コンフリクトが発生したため手動で解消。
- 確認を依頼され、`prisma validate`を実行したところ `P1012` エラーでパース不能と判明。原因は手動マージで `enum MfJobDetailResult` の閉じ括弧 `}` が1つ欠落していたこと。それ以外（`MfOauthToken`/`MfLink`/`MfJob`/`MfJobDetail`とその enum、`table_design.md`の一覧27-30、`tables/alp_mf_*.md`の4ファイル、マイグレーション2本）は欠落・重複なく正しくマージされていた。コンフリクトマーカーの残存もリポジトリ全体でなし。
- 修正をDraft PR #67（`fix/mf-job-detail-result-missing-brace`、base: staging）として作成。`prisma validate`/`prisma format --check`/`npm test`すべて通過。ユーザーのレビュー・マージ待ち。
- 教訓: Prismaスキーマのコンフリクト解消後は`prisma validate`で必ず構文確認する（今回のように壊れていてもGit上は「コンフリクト解消済み」に見えてしまうため）。

## 2026-10-13 PR ＃67マージとバージョンアップ（0.2.1）の指示

- ユーザーがPR #67（schema.prisma破損修正）を`staging`へマージ。
- 承認: publish用のバージョンを**0.2.1**にする、とユーザーが指定（現在CodeArtifact公開済みは`0.0.1`/`0.1.0`/`1.0.0`、`latest`タグは`0.1.0`。package.json側も`0.1.0`で一致）。
- 対応: `package.json`/`package-lock.json`の`version`を`0.1.0`→`0.2.1`に変更し、Draft PR #69（`chore/bump-version-0.2.1`、base: staging）を作成。マージ後は`alphadb-publish`（CodeBuild）での publish が必要（未実施）。

## 2026-10-13 MFクラウド連動 alphadb側対応の完了

- ユーザーがPR #69（`staging`）とPR #70（`staging`→`main`）をマージ。`alphadb-publish`・`staging-prisma-merge-project-build`（どちらもwebhook無し・手動起動）を実行完了。
- CodeArtifact上で`0.2.1`が`Published`・`latest`になっていることを確認（`0.0.1`/`0.1.0`/`0.2.1`/`1.0.0`が存在）。
- **alphadb側の作業はここで終了**。以降はalphasys/alphaexapi側のセッションで、`package.json`の`alphadb`依存を`0.2.1`に上げてからの作業（MF APIクライアント・OAuth基盤・ジョブ実行状態の活用等）を継続する。

## 2026-10-13 MfLink — 新規作成待ち・対象外の状態を表現する方式を決定

- 発端: alphasystem仕様3.6章「継続的な新規取引先の扱い」で、alphaexapiセッション側が
  `MfLink.mfId`必須のため「担当者が新規作成を承認したがまだMF側IDが無い」状態を
  表現できないと判明。alphadb側セッションで検討依頼。
- 整理: 担当者の3設定（新規作成/更新/対象外）のうち、**「更新」は既存`MfLink`行の
  `syncStatus`を`PENDING`に戻すだけでスキーマ変更不要**と判明。論点は「新規作成待ち」
  「対象外」の2状態をどう永続化するかに絞られた。
- 提示した2案: (A) `MfLink`を拡張（`mfId`をNULL許容＋`EXCLUDED`状態追加）/ (B) 担当者の
  設定を別テーブル（`MfJob`/`MfJobDetail`と同様に「事実とログを分ける」設計）に分離。
- **承認（ユーザー回答）: A案を採用**。実利用者（alphaexapi実装）がまだ無いため
  NOT NULL緩和のリスクは小さい、という理由。
- 実装: `MfLink.mfId`を`String?`に変更、`MfSyncStatus`に`EXCLUDED`を追加。
  バージョンは当初ユーザー指定の`0.1.3`から、**公開済み最新`0.2.1`より古くlatestタグが
  後退するリスクを指摘し、ユーザーが`0.2.2`に訂正**。Draft PR #73（base: staging）を作成。
- ユーザーがPR #73（`staging`）とPR #74（`staging`→`main`）をマージ、`alphadb-publish`・
  `staging-prisma-merge-project-build`を実行完了。CodeArtifactで`0.2.2`が`Published`・
  `latest`になっていること、`staging`/`main`の同期・`prisma validate`/`npm test`正常・
  コンフリクト破損無しを確認。**alphadb側の対応完了**。

## 2026-10-15 Contract「入金予定日」のテーブル設計もれが発覚

- ユーザーが旧システムの契約情報修正画面のスクリーンショットから指摘。`alp_contract`に
  「入金予定日」（数値項目）があるが、alphadbの`Contract`モデル・`alp_contract.md`・
  夜間移行`extract.sql`のいずれにも存在しないことを確認（スキーマ設計のもれ）。
- 業務ルール: `0` = 翌月末日、`0以外` = 翌々月の該当日（最大で翌々月末日）。
- 旧システム側の列名は**`scheduled_payment_date`（int型）**とユーザーが確認・回答。
- 提案した対応方針（ユーザーの最終承認は未取得・提示直後）: `Contract.scheduledPaymentDate`
  （nullable想定）を追加し、`alp_contract.md`に業務ルールを記載、夜間移行の`extract.sql`/
  `load.sql`に列を追加（`verify.sql`/`check.sql`は他の非FK数値列と同様、個別チェックは
  追加しない）。スコープはalphadb側まで（alphasys側の画面実装は別セッション）。
- ユーザーが提案方針を承認しDraft PR #77（記録のみ）をマージ。「実装をお願いします」との
  指示を受け実装・Draft PR #78（base: staging）を作成。publishバージョンは
  ユーザーに確認のうえ**0.2.3**（公開済み最新0.2.2の次）に決定。
- ユーザーがPR #78（`staging`）とPR #79（`staging`→`main`）をマージ、`alphadb-publish`・
  `staging-prisma-merge-project-build`を実行完了。CodeArtifactで`0.2.3`が`Published`・
  `latest`になっていること、`staging`/`main`の同期・`prisma validate`/`npm test`正常・
  コンフリクト破損無しを確認。**alphadb側の対応完了**。

## 2026-10-16 MFクラウド連動 CSV経路追加（alphadbスキーマ対応）

- 発端: alphasystemの仕様書に「2.4 CSV経路（移行期間中の並行経路）」「7.1 CSV経路の扱い」
  が2026-10-16付けで追加され、現行システム（alphaofficesystem）の手動CSV連携をAPI経路とは
  別のトリガーとして実装しつつ、実行履歴は既存の`MfJob`/`MfJobDetail`で一元管理する方針と
  判明。alphadb側の対応が必要と確認し、ユーザーに修正依頼。
- 提案方針: enum `MfJobSource`（API/CSV）・`MfUploadMode`（NEW/ADD）を新設し、`MfJob`に
  `source`（既定値API）・`uploadMode`・`deletedCount`を追加。`MfJobDetail`/`MfLink`/
  `MfOauthToken`は変更なし。
- 承認: ユーザーが方針とバージョン**0.2.4**（公開済み最新0.2.3の次）を承認。
- 実装: `feature/add-mf-job-source-and-upload-mode`ブランチで実装、Draft PR #82（base:
  staging）を作成。`prisma validate`・型チェック（API経路のデフォルト動作／CSV経路の
  NEWモード指定）・`npm test`で確認済み。既存テーブルへの変更は列追加のみ。
- 併せて、CLAUDE.mdの新ルール（ベースブランチにマージ済みのローカルブランチは新規ブランチ
  作成時に削除する）に従い、マージ済みローカルブランチ18本を削除。

## 2026-10-19 MF給与CSV人件費取込 — alphadb側対応（alphasystemセッションからの引き継ぎ）

- 発端: alphasystemセッション（alphasystem-92）からクロスセッションメッセージで引き継ぎ。
  設計書は`alphasystem/docs/design/2026-10-19-MF給与CSV人件費取込-仕様.md`（brainstorming
  で全セクション承認済み・確定）。設計書8章の内容を直接確認し、引き継ぎ内容と一致している
  ことを確認したうえで着手。
- 対応: enum `MfJobType`に`PAYROLL_SALARY_IMPORT`/`PAYROLL_BONUS_IMPORT`を追加（MfJobに
  種別列は足さない）。`MfProduct.PAYROLL`は今回追加しない（MFクラウド給与API連携は②として
  保留、着手時に追加）。`alp_usercost`(Usercostモデル)・`MfJobDetail`には変更なし（給与取込は
  社員ごとの明細行を作らず、MfJobの件数のみ記録する設計のため、仕様書7章）。
- バージョンをCodeArtifact公開済み最新`0.2.4`の次`0.2.5`に決定。`feature/add-mf-job-type-payroll`
  ブランチで実装、Draft PR #84（base: staging）を作成。`prisma validate`・型チェック・
  `npm test`で確認済み。既存テーブルへの変更はenum値追加のみ。
- 実装順はalphadb→alphaexapi→alphasys。alphaexapi-4cとalphasys-f1が並行して同じ設計書で
  作業中。alphasys-f1から進捗確認のクロスセッションメッセージがあり、「Draft PR #84作成済み・
  未マージ・未publish。publishされれば0.2.5」と返信。
- ユーザーがPR #84（`staging`）とPR #85（`staging`→`main`）をマージ、`alphadb-publish`・
  `staging-prisma-merge-project-build`を実行完了。CodeArtifactで`0.2.5`が`Published`・
  `latest`になっていること、`staging`/`main`の同期・`prisma validate`/`npm test`正常・
  コンフリクト破損無しを確認。alphaexapi-4c・alphasys-f1へ「0.2.5がpublish済み」を連絡。
  **alphadb側の対応完了**（実装順の次はalphaexapi→alphasys）。

## 2026-10-20 alphasystemからの申し送り（INBOX_FROM_ALPHASYSTEM.md 取り込み）

- 運用ルール（ユーザー指示）: リポジトリ直下に`INBOX_FROM_ALPHASYSTEM.md`があれば、内容を
  本conversations.mdへ取り込んでから削除する。今後も同様に扱う。
- 依頼: `prisma/doc/migration/overview.md`の「6. 残タスク」「2. 移行ステータス一覧」の文書整合。
  - 実態は**夜間自動移行**（Bastionのsystemd timer、毎日JST 1:00、`nightly_automation.md`、
    PR #56/#58、alphasyscdk #89）。CloudWatch `/alphasys/staging/nightly-migration`で
    10/12〜10/19毎晩`RESULT: SUCCESS`を確認済み。「一気通貫の再実施」という作業は存在しない。
  - D3は2026-09-30に「移行対象外（システムの中で作成するもの）」で確定済み。「要判断」を確定表記に直す。
  - 画面での実データ確認は2026-09-30に「可能なものは確認済み」としてクローズ済み
    （alphasystem/docs/conversations.md「2026-09-30 データ移行の残タスクを確定し…」）。
  - 進め方: 修正は文書のみ。方式案を示して承認後に着手（featureブランチ→Draft PR、base=staging）。
- 状況共有:
  - MF給与CSV取込: alphadb側は0.2.5 publish済みで完了。追加作業なし。
  - 将来（②給与API連携着手時）: `MfProduct.PAYROLL`追加が必要（今は保留）。
  - 将来（段階2 ユーザー単位OAuth）: `MfOauthToken`を製品×ユーザー単位へ変更（v0.2.6想定、
    alphaexapi設計2026-10-16承認済み）。**着手指示が出るまで待機**。

## 2026-10-20 D5（alp_laborcost_history）の確定状況をalphasystemへ問い合わせ

- overview.md文書整合の修正案（ステータス一覧・D3・残タスク）を提示。**承認待ち（未着手）**。
- 表#11 `alp_laborcost_history`が「要判断」のまま（本文D5は「原則 新規入力（移行不要）」）。
  ユーザーは判断がつかないため、alphasystemセッション（alphasystem-37）へ確定状況を問い合わせた。
  回答があるまで#11の表記は変えない。

## 2026-10-20 D5（alp_laborcost_history）はalphasystem側でも未確定と回答

- alphasystem-37の回答: D5の確定記録は無く未確定。過去単価を別ソースから起こす案の生死も未決。
  MF給与CSV取込は`alp_usercost`のみ対象で、D5の判断材料にはならない。
- 表記方針: ステータス一覧#11は**「要判断」のまま**。備考に「原則は新規入力（移行元なし）。
  過去単価を移すかは未決」と事実だけ追記するのは可。**「確定」とは書かない**。
- 確定にはユーザー判断が必要。alphasystemからユーザーへ確認し、決まったら改めて連絡が来る。

## 2026-10-20 D5（alp_laborcost_history）は「保留」とユーザーが回答

- ユーザー回答: `alp_laborcost_history`は**技術者別採算管理サブシステムを構築する際に使用するもの**で、
  **現在は保留**。移行要否（過去単価を起こすか）も、同サブシステム構築時に判断する。
- overview.md表記案: ステータス一覧#11の状態を「要判断」→「保留（技術者別採算管理サブシステム
  構築時に判断）」へ。D5節にも同趣旨を追記。「確定（移行対象外）」とは書かない。（文書修正全体は承認待ち）
- alphasystem-37へ本回答を連絡。

## 2026-10-20 overview.md文書整合 — ユーザー承認・Draft PR作成

- ユーザーが「PRを出してください」と指示（修正案の承認）。
- `feature/docs-migration-overview-status`ブランチで`prisma/doc/migration/overview.md`を修正
  （ステータス一覧14テーブル→「✅夜間自動移行中」、#7 D3→対象外確定、#11 D5→保留、
  6章の残タスクを「本番での実施（本番環境構築後）」のみに整理、一気通貫は夜間自動移行で代替）。
  文書のみの変更。Draft PR #88（base: staging）を作成し、alphasystem-37へ連絡済み。

## 2026-10-20 会話記録を日付別ファイルに切り替え（alphasystemからの申し送り）

- 発端: `INBOX_FROM_ALPHASYSTEM.md`（2026-10-20）で依頼。決定はalphasystem側でユーザー承認済み。
  Obsidian同期とStopフックは新旧両対応に修正済み。
- 承認: alphadbセッションで手順を提示し、ユーザーが「この手順で進めてください」と承認。
- 対応: `conversations/`ディレクトリと`README.md`（alphasystemの`docs/conversations/README.md`を雛形）を作成。
  以後の記録は`conversations/<日付>.md`に書く。見出しは`## YYYY-MM-DD タイトル`（日付を先頭）。
- やらないと決めたこと: 既存の`conversations.md`は過去分のアーカイブとして残し、**追記しない・分割/移動しない**
  （リンク切れ防止）。同日10/20の前半の記録（申し送り取り込み、D5保留、PR #88）はそちらにある。
- Stopフックは`conversations/`ディレクトリの有無で書き先を切り替える。切替後の書き先が今日付ファイルになることを確認する。
- INBOXは本ファイルへ取り込んで削除。今後のINBOX取り込み先も`conversations/<日付>.md`とする。
- 前提確認: PR #88（overview.md文書整合）は2026-10-20にマージ済み。マージ済みローカルブランチ
  `feature/docs-migration-overview-status`を削除し、`feature/conversations-by-date`ブランチで作業。
- 結果: Draft PR #90（base: staging）を作成。切替後のStopフックの書き先が`conversations/2026-10-20.md`
  になったことを実機で確認済み（旧`conversations.md`は書き先から外れた）。

## 2026-10-22 4_7_1 社員情報変更依頼・MFユーザー単位OAuthのスキーマ依頼を受領し方式案を提示

- 発端: alphasystem-6b から依頼（2026-10-22 ユーザー承認済み。方式案を alphasystem に示し了解後に着手）。
  設計書: `alphasystem/docs/design/2026-10-22-社員情報変更依頼-仕様.md`（第5版）8章、
  `alphaexapi/docs/superpowers/specs/2026-10-16-mf-user-oauth-design.md` 3章、
  alphaexapi 契約書草案 `2026-10-22-employee-change-request-api-contract.md` 8章（alphaexapi Draft PR #152）。
- alphaexapi-aa 経由の確定事項: メール確認トークンは `UserChangeData` に列を持つ（changeInfo に入れない）。
  ChgType追加・staffScode NULL許容・rejectReason・索引・completedBy・MfJobType.EMPLOYEE_CSV_IMPORT は案どおり。
- やらないと決めたこと: **`Users.commutingCost` の追加は保留**（ユーザー判断、実態把握のため。alphasystem-6b 連絡）。
  通勤費の依頼は完了しても alp_users へ適用せず履歴だけ残す。
- 方式案（alphasystem-6b・alphaexapi-aa へ送付、了解待ち）:
  - 4_7_1: ChgType に `CHANGE_EMERGENCY`/`CHANGE_MAIL`、`staffScode Int?`、`rejectReason String?`、
    enum `ChgCompletedBy { MANUAL, CSV }` と `completedBy ChgCompletedBy? @map("completed_by")`、
    `tokenHash String? @map("token_hash") @db.VarChar(64)`、`tokenExpiresAt DateTime? @map("token_expires_at") @db.Timestamptz(6)`、
    `@@index([scode, changeType, changeStatus])`、MfJobType に `EMPLOYEE_CSV_IMPORT`。
  - `ChgStatus.SYNCED` は削除を提案（使用コード無し。移行の抽出は 1〜3→REQUEST/RECEPTION/COMPLETE のみで SYNCED 行は存在しない）。
  - `alp_change_req` は不採用。テーブル設計書を「廃止（alp_user_change_data に一本化）」と整理し、
    `alp_user_change_data.md` を新しい列・enum・状態遷移に更新する。
  - OAuth: 設計書3章どおり（`userEmail VarChar(256)`、FKなし、`@@unique([mfProduct, userEmail])`、既存2行はマイグレーションで削除）。
  - 版数案: OAuth を 0.2.6、4_7_1 を 0.2.7 で別ブランチ・別PR（公開は OAuth→4_7_1 の順）。
- 判断を仰いだ点: 夜間自動移行が毎晩 `alp_user_change_data` を DELETE→旧8行で入れ直すため、
  新システムで作った依頼が staging で毎晩消える（alp_users も毎晩入れ直されるため完了時の反映も戻る）。
  対処案を alphasystem に提示（回答待ち）。移行時 `staff_scode` を `COALESCE(...,0)` で 0 にしている点の扱いも確認。
  - 対処案: a. 現状のまま（試験は1日で完結） / b. `alp_user_change_data` を夜間処理で触らないテーブルにする（clear/load/check/verify 修正） /
    c. 結合試験期間中は夜間タイマーを止める。alphadb の推奨は a か c（本番向けの夜間移行手順を変えないため）。
  - `staff_scode` の 0 は変えない（抽出SQLを変更しない）ことを推奨。
- alphaexapi-aa へ確認中: 承認なし項目（緊急連絡先・メール）を COMPLETE で記録する際の `completedBy`（NULL か）と `staffScode`（本人か NULL か）。
- 着手条件: alphasystem-6b の了解後に OAuth（0.2.6）→ 4_7_1（0.2.7）の順で別ブランチ・別 Draft PR（base: staging）。

## 2026-10-22 alphaexapi-aa が契約・版数・列の最終案に合意

- 合意: OAuth の契約、版数と公開順（0.2.6 OAuth → 0.2.7 4_7_1）、4_7_1 の列の最終案はすべてそのまま。`ChgStatus.SYNCED` の削除も可。
- 回答: 承認なし項目（緊急連絡先・メール）を COMPLETE で記録する際の `completedBy` は **NULL**（MANUAL/CSV は総務の確定手段）。
  `staffScode` は受付・却下・完了を操作した総務の scode。本人の操作（依頼作成・取消・承認なし項目の保存・メール確認）では NULL。
  CSV 完了時は CSV を取り込んだ総務の scode。`tokenHash` は SHA-256 hex 64文字で `VarChar(64)`。
  alphaexapi 契約書（Draft PR #152）に明記済み。テーブル設計書の備考にもこの意味を書く。
- 残: alphasystem-6b の了解（方式案全体・夜間移行の対処 a/b/c・staff_scode の 0）待ち。着手はその後。

## 2026-10-22 alphasystem-6b が方式案を了承 — 着手

- 了承: 4_7_1 の変更一式（ChgType追加・staffScode NULL許容・rejectReason/completedBy/tokenHash/tokenExpiresAt・索引・
  EMPLOYEE_CSV_IMPORT・SYNCED削除・alp_change_req廃止と設計書整理）、Users.commutingCost を追加しないこと、
  OAuth（設計書3章どおり）、版数（OAuth 0.2.6 → 4_7_1 0.2.7、別ブランチ・別 Draft PR）。
- (B) 旧データの staff_scode は**変えない**（抽出の COALESCE(...,0) のまま）で了承。
- 留意: 0.2.6 の publish は先でよいが、**staging DB へのマイグレーション適用は alphaexapi のユーザー単位 OAuth 実装の
  staging デプロイに合わせる**（現行 alphaexapi は製品単位の一意前提のため）。PR 説明に明記し、alphaexapi-aa と日程を合わせる。
- (A) 夜間移行で alp_user_change_data・alp_users が毎晩入れ直される件はユーザー確認中。**結論が出るまで夜間移行キットは変更しない**。

## 2026-10-22 OAuth（0.2.6）・4_7_1（0.2.7）を実装し Draft PR を作成／夜間移行は結合試験中に停止と決定

- OAuth: `feature/mf-oauth-token-per-user` で実装、Draft PR #92（base: staging）。staging DB への適用は alphaexapi の
  ユーザー単位 OAuth の staging デプロイに合わせる旨を PR に明記。
- 4_7_1: `feature/employee-change-request` を #92 の上に積んで実装（版数・マイグレーション順を揃えるため）。
  **#92 を先にマージする**。マイグレーション `20261022100000_employee_change_request`。
- 確認: `prisma validate`・`npm test`。マイグレーション SQL は `prisma migrate diff`（alphaexapi の prisma 6.19.3 を使用。
  alphadb の node_modules 未導入・CodeArtifact トークン期限切れのため）で生成。実 DB への適用は未確認。
- 決定（ユーザー、alphasystem-6b 経由）: (A) 夜間自動移行は **c. 結合試験の期間中だけ夜間タイマーを止める**。
  夜間移行キット（clear/load/check/verify）は変更しない。停止期間は 4_7_1 結合試験の開始〜終了（タイミングは alphasystem から連絡）。
- 依頼: `nightly_automation.md` に「結合試験中の一時停止」の節を追記（停止・状態確認・再開コマンド、停止中は staging データが
  更新されないこと、再起動や Bastion 置換で再開してしまうかの確認、再開後最初の夜の CloudWatch `RESULT: SUCCESS` 確認）。
  実際の停止・再開はユーザーが行う。

## 2026-10-22 夜間タイマーの一時停止手順を追記／夜間移行が10/19以降止まっていることを発見

- `nightly_automation.md` に「9. 結合試験中の一時停止」を追記（`feature/docs-nightly-pause-during-test`、Draft PR #94）。
  停止は `systemctl disable --now`（`stop` だけだと Bastion 再起動で再開するため）、再開は `enable --now`。
  `Persistent=false` のため再開時に止めていた分の実行はしない。停止中は §7 の復旧手順・`setup_bastion.sh` を実施しない
  （timer が enable される）。CloudWatch 確認コマンドは実機で動作確認済み（`--max-items` は余計な `None` 行が出るため `--limit` を使う）。
- 発見: Bastion が 2026-10-19 13:25 JST と 2026-10-22 16:25 JST に置換されており、夜間移行は **10/19 の SUCCESS を最後に停止**
  （10/20〜10/22 のログストリーム無し）。§7 の復旧は未実施。**復旧するか試験終了まで止めたままにするかは未決**
  （alphasystem・ユーザーに判断を依頼。alphadb からは何も実行しない）。

## 2026-10-22 PR ＃92〜＃94 マージ／夜間移行を今すぐ復旧（ユーザー決定）／Bastion 置換の原因

- ユーザーが PR #92〜#94 を staging にマージ（publish・staging への migrate は未実施。最新 publish は 0.2.5、
  `alphadb-publish`・`staging-prisma-merge-project-build` の最終実行は 2026-10-19）。
- 決定（ユーザー）: 夜間移行は **(2) 今すぐ復旧し、4_7_1 結合試験の開始時に §9 の手順で止める**。
- Bastion 置換の原因: StagingStack の `cdk deploy`（CloudTrail `ExecuteChangeSet`、実行者 aws-cdk-yohira）。
  2026-10-19 13:24 JST（alphasyscdk PR #98 系のデプロイ）と 2026-10-22 16:25 JST（alphasyscdk PR #105 SES）。
  `latestAmazonLinux2023()` が AMI 更新を拾い（10/19 機 ami-05534a20c2195f7ab → 10/22 機 ami-0d6d9b11f5af70dfc）、
  CloudFormation が Bastion を置換・終了した（§7 の既知事象。恒久対応しない方針 2026-10-06）。10/20 のデプロイは AMI 不変で置換なし。
- 復旧（2026-10-22 17:08 JST、i-02b9da547de06014a）: 配布（`deploy.sh` 相当。手元に jq が無いため JSON 生成のみ node で代替、
  キットは変更なし）→ `setup_bastion.sh` → `/etc/alphadb-migration.env` 再作成（0640 root:postgres）→ `systemctl start` timer。
  enabled/active、次回 2026-10-23 01:00 JST。手動実行はしていない（日中の staging データを消さないため）。
  **2026-10-23 朝に CloudWatch で `RESULT: SUCCESS` を確認する。**

## 2026-10-22 公開順の変更依頼（4_7_1 を 0.2.6、OAuth を 0.2.7）— 組み直し案をユーザーに提示

- alphasystem-6b の決定（alphaexapi-aa の判断依頼への回答）: **4_7_1 を先に 0.2.6 で公開、OAuth は 0.2.7** に入れ替える。
  理由: OAuth を含む版では `MfOauthToken.mfProduct` の単独一意がなくなり、alphaexapi の既存 MF 認可処理がコンパイルできない。
  OAuth の公開・staging 適用は alphaexapi のユーザー単位 OAuth 実装に合わせる（適用の留意は変更なし）。
- 現状: #92・#93 は staging にマージ済み（両方入りの 0.2.7）。publish・staging 適用は未実施。
- 組み直し案（**ユーザー承認待ち**）: ① staging から OAuth 分（schema・migration `20261022090000_mf_oauth_token_per_user`・
  `alp_mf_oauth_token.md`）を外し版数を 0.2.6 に戻す PR → マージ後に publish（0.2.6 = 4_7_1 のみ）。
  ② OAuth を戻す PR を Draft で用意（migration は 4_7_1 より後の日付に付け直し、0.2.7）。alphaexapi 実装後にマージ。
- 段取り: 組み直しが決まるまで **`alphadb-publish` を実行しない**（今 publish すると OAuth 入りの 0.2.7 になる）とユーザーに依頼。
  決まり次第、公開順を alphasystem・alphaexapi-aa に連絡する。

## 2026-10-22 組み直し案をユーザーが承認 — 0.2.6 = 4_7_1 のみ、OAuth は 0.2.7 へ

- 承認: ユーザーが組み直し案を承認（「この案でお願いします」）。
- ①`feature/defer-mf-oauth-to-0.2.7`: staging から OAuth 分（schema の MfOauthToken・migration `20261022090000_mf_oauth_token_per_user`・
  `alp_mf_oauth_token.md`）を外し、版数を 0.2.6 に。確認: 本ブランチの schema は #92 前の schema に 4_7_1 の migration
  （`20261022100000_employee_change_request`）を足したものと一致（`prisma migrate diff` で照合）。`prisma validate`・`npm test` OK。
- ②OAuth を 0.2.7 として戻す Draft PR を ① の上に用意（migration は 4_7_1 より後の日付に付け直す）。
  **マージ・publish・staging 適用は alphaexapi のユーザー単位 OAuth 実装に合わせる**。
- 公開順: ① マージ → `alphadb-publish`（0.2.6）→ staging 適用 → … → ② は alphaexapi の準備ができてから。
- PR: ① **#96**（base: staging、0.2.6 = 4_7_1 のみ）、② **#97**（#96 の上に積む Draft。OAuth 0.2.7、migration `20261022120000_mf_oauth_token_per_user`）。
  #97 の schema は #92・#93 両方マージ後の staging（b19f321）と一致することを確認。alphasystem-6b・alphaexapi-aa に公開順を連絡。

## 2026-10-22 ＃96 と staging→main（＃95）がマージ済み — 0.2.6 の publish・staging 適用の段取り

- ユーザーが #96 と staging→main の #95 をマージ済み。main は 0.2.6 で、2026-10-22 のマイグレーションは
  `20261022100000_employee_change_request` のみ（OAuth なし）を確認。
- 「staging DB に適用」= CodeBuild `staging-prisma-merge-project-build` による `prisma migrate deploy`（＋アプリ用 DB ロール・権限の再設定）。
  このビルドの**ソースは main ブランチ**（sourceVersion=main）なので、適用前に main が意図した版であることを確認する。
- 段取り: ① `alphadb-publish`（0.2.6 を CodeArtifact へ）→ ② `staging-prisma-merge-project-build`（ユーザーが実行）→
  ③ alphadb が CodeArtifact の 0.2.6 Published/latest とビルド成功を確認し、alphasystem-6b・alphaexapi-aa に連絡。

## 2026-10-22 0.2.6（4_7_1）の publish・staging 適用完了

- ユーザーが `alphadb-publish`（17:27 JST）・`staging-prisma-merge-project-build`（17:30 JST）を実行。どちらも SUCCEEDED、
  ソースは main の 2fb8901（#95）。
- 確認: CodeArtifact で `0.2.6` が Published（17:28 JST）かつ既定版（latest）。ビルドログで
  `Applying migration 20261022100000_employee_change_request` → `All migrations have been successfully applied.`
- alphasystem-6b・alphaexapi-aa に 0.2.6 の publish・staging 適用完了を連絡。**alphadb 側の 4_7_1 対応は完了**（次は alphaexapi → alphasys）。
- 残: OAuth は #97（0.2.7、Draft）を alphaexapi のユーザー単位 OAuth 実装に合わせてマージ。
  2026-10-23 朝に夜間移行の CloudWatch `RESULT: SUCCESS` を確認（復旧後初回・0.2.6 適用後初回）。

## 2026-10-22 alphaexapi が 0.2.6 を取り込み完了／OAuth は 4_7_1 実装後に着手

- alphaexapi-aa: `alphadb@0.2.6` を取り込み、既存の MF 認可処理はそのままコンパイルでき全テスト pass。
- 段取り: OAuth（#97、0.2.7）は **alphaexapi の 4_7_1 実装が終わってから**ユーザー単位 OAuth に着手。staging デプロイの目処が立ったら
  alphaexapi-aa から連絡が来る。それまで #97 は Draft のまま待機。

## 2026-10-22 issue ＃99（未完了依頼の部分ユニーク索引）を受領 — 着手はユーザー判断待ち

- alphaexapi-aa がユーザー承認のうえ alphacmc/alphadb#99 を起票（alphaexapi PR #152 最終レビューの指摘）。
  アプリ側の「未完了があれば 409」は原子的でなく、同時2回の依頼で重複しうる。対応案: `(scode, change_type)` の部分ユニーク索引
  （`change_status IN (REQUEST, RECEPTION)` かつ承認ありの4項目。`CHANGE_MAIL` は対象外案）。
- 急ぎではない。**当面は alphasys の連打防止と、重複時は総務が片方を却下する運用**。着手時は alphaexapi の P2002→409 変換と合わせる（要連絡）。
- 着手の可否・時期はユーザー判断待ち（論点: Prisma schema で部分索引を表現できず migration の SQL のみになる点、既存データの重複有無の事前確認、版数）。

## 2026-10-22 alphaexapi から 0.2.7（OAuth）の先行 publish 依頼 — 方式をユーザーに確認中

- alphaexapi-aa: ユーザー承認のうえユーザー単位 OAuth に着手（alphaexapi Draft PR #155）。開発・テスト用に `alphadb@0.2.7` の先行 publish を依頼。
  staging DB への適用は alphaexapi の staging デプロイと**同時**（0.2.7 の alphaexapi は (mfProduct, userEmail) で検索するため）。
- 論点: 通常の publish は #97 を staging→main に入れて `alphadb-publish` を実行する。`staging-prisma-merge-project-build` も main を
  ソースにするため、main に OAuth のマイグレーションが入ると、以後の適用ビルド（#99 など他のスキーマ変更を含む）で OAuth も当たってしまい、
  「publish と DB 適用を切り離す」ことが運用ルール頼みになる。0.2.7 が latest になり、他の消費側の更新時にも入る。
- 選択肢（ユーザー判断待ち）: A. 通常どおり 0.2.7 を publish し、OAuth デプロイまで適用ビルドを止める／
  B. #97 ブランチから試験版 `0.2.7-oauth.0` を dist-tag `next` で publish（main・latest・適用ビルドに影響しない。正式 0.2.7 は
  デプロイ時に main 経由で publish）／ C. publish せず alphaexapi はローカル参照で開発。alphadb の推奨は B。
- alphaexapi-aa は B 案に同意（ユーザー確認待ち）。B の場合の段取り: #155 は開発中 `"alphadb": "0.2.7-oauth.0"`（完全一致）→
  正式 0.2.7（main 経由・latest）publish 後に `^0.2.7` へ切替・lock 作り直し・全テスト → staging デプロイと DB 適用を同時に実施。
  #155 は正式版へ切り替えるまで Draft のまま。4_7_1 の PR #152 は `^0.2.6` のままで #155 と独立。
- 失敗: マージ済みの #98 のブランチへ push してしまった（push 前のマージ確認漏れ）。未取り込みのコミットを Draft PR #101 に移した。
  以後、push のたびに対象 PR のマージ状態を確認する。

## 2026-10-22 0.2.7（OAuth）が正式 publish・staging 適用された（結果として A 案）

- ユーザーが #97・#101・staging→main（#102）をマージし、`alphadb-publish`（20:41 JST）・`staging-prisma-merge-project-build`（20:41 JST）を実行。
  どちらも SUCCEEDED、ソースは main の 41c28c6。
- 確認: CodeArtifact で `0.2.7` が Published かつ既定版（latest）。ビルドログで
  `Applying migration 20261022120000_mf_oauth_token_per_user` → 成功。staging の `alp_mf_oauth_token` は既存2行が削除され、
  (mfProduct, userEmail) の複合一意に変わった。試験版（B 案）は作っていない。
- 影響: staging で動いている現行 alphaexapi（製品単位前提）は、トークンの保存（mfProduct の単独一意を使う upsert／user_email なしの insert）が
  失敗する見込み。ただし staging の MF 認可は alphasys の中継が未実装で元々通せない状態で、既存トークンも削除済みのため、
  実害は「MF API 呼び出しが未認可」のまま変わらない程度と見ている。
- alphaexapi-aa・alphasystem-6b に連絡（#155 は試験版を経ず `^0.2.7` を直接指定できる。staging デプロイは急ぐ必要あり）。
- alphaexapi-aa 返信: #155 は `"alphadb": "^0.2.7"` を直接指定（設計書 10.4・会話記録も更新済み）。段取り: 実装計画 → alphasystem の了解 →
  実装 → ユーザーがマージ後すぐ staging デプロイ。デプロイの目処が立ったら連絡が来る。現行 alphaexapi がトークンを保存できない状態は
  #155 のデプロイまで続く（alphaexapi-aa からもユーザーへ伝える）。
