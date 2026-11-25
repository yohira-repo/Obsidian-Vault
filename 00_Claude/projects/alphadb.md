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

## 2026-10-28 alphasystemからの申し送り（INBOX_FROM_ALPHASYSTEM.md 取り込み）

- alphasystemで、alphasys課題表のうち設計が必要だった6件の設計がユーザー承認で確定した
  （設計書: alphasystem `docs/design/2026-10-28-alphasys課題表6件-設計.md`、PR #122。
  決定の記録: alphasystem `docs/conversations/2026-10-28.md`）。
- **alphadbの担当は5_4_3（インスタンスの定時起動・定時停止）**: 新しいテーブルを新設する。
  実行はalphaexapiのスケジューラ（1分ごと）が読む。
  - スケジュール: 種別（起動／停止）・時刻（HH:mm）・曜日・有効／無効。
    起動のデフォルトは月〜金8:45、停止のデフォルトは20:00（停止は複数設定可）。
  - 起動の対象インスタンス: インスタンス名（タグのName。IDは作り直しで変わるため名前で持つ）の
    一覧（複数選択可）。停止の対象は`client-*`/`server-*`の全インスタンス共通のため、
    対象の一覧は持たない（設定ごとの対象選択はしない。ユーザー承認済み）。
  - 祝日は起動しない（祝日の判定はalphaexapi側）。
  - 実行履歴（直近の取りこぼし補完・重複実行の把握用）を持つ。
  - 既存の`alp_extension_request`（instanceId・instanceName・stopTime）は、延長申請の
    停止予定時間にも停止を実行する形でalphaexapiが使う（定時停止ではなく延長の停止予定時間で
    止める。ユーザー承認済み）。変更の要否はalphaexapiと調整。
  - 実装の依存順: alphadb（このテーブル）→ alphacdk / alphasyscdk → alphaexapi → alphasys。
- テーブル設計はalphadbで行い、決まったらalphaexapiへ知らせる。設計の質問はalphasystemへ。
  実装計画は本セッションで立てる（未着手）。
- `INBOX_FROM_ALPHASYSTEM.md`は取り込み後に削除する運用（2026-10-20と同様）。

## 2026-10-28 5_4_3テーブル設計を提示・ユーザー承認、Draft PR作成

- 設計案（3テーブル）を提示: `AlpInstanceSchedule`（設定本体）、`AlpInstanceScheduleRun`/
  `AlpInstanceScheduleRunDetail`（実行履歴ヘッダ+明細、既存`MfJob`/`MfJobDetail`と同形）。
- ユーザー承認（3点とも私の推奨どおり）:
  - 曜日（daysOfWeek）は`DayOfWeek[]`（enum配列）で持つ。
  - 実行履歴はヘッダ+明細の2テーブル構成（1テーブル統合案は不採用）。
  - 起動対象インスタンス名は`AlpInstanceSchedule.targetInstanceNames`に`String[]`で直接持つ
    （中間テーブル案は不採用）。
- `alp_extension_request`自体は変更なしの前提で設計。
- 実装: `feature/instance-schedule-tables`ブランチで`alp_instance_schedule`・
  `alp_instance_schedule_run`・`alp_instance_schedule_run_detail`を追加
  （マイグレーション`20261028113219_add_instance_schedule`）。`prisma validate`・
  `prisma migrate dev`（ローカルDB適用）・`npm test`・`tsc --noEmit`で確認済み。
  version 0.2.7→0.2.8。Draft PR #105（base: staging）を作成。
- 設計が決まったらalphaexapiへ知らせる運用（申し送り原文の指示）。alphaexapi側セッションへの
  連携はPRマージ後に行う。

## 2026-10-29 5_4_3テーブルのドキュメント作成（レビューはドキュメントベースで実施）

- ユーザー指示: `prisma/doc/tables`配下の新規3テーブル分のドキュメントも作成する。**PR #105の
  レビューはドキュメントベースで行いたい**（コードではなくドキュメントを見て確認する）。
- 既存の`alp_mf_job`/`alp_mf_job_detail`・`alp_sales_email`（配列列は`V[]`表記）の形式に合わせ、
  `alp_instance_schedule.md`・`alp_instance_schedule_run.md`・`alp_instance_schedule_run_detail.md`
  を作成し、`table_design.md`のテーブル一覧にNo.31〜33として追加。PR #105に追加コミットで反映済み。

## 2026-10-29 PR ＃105マージ完了、package-lock.jsonのversion更新漏れを発見・修正

- ユーザーがPR #105を`staging`へマージ。PR #106（`staging`→`main`）も既にマージ済みで、
  `staging`/`main`は内容として同期済み（`main`側は過去の`staging`マージコミット群が
  履歴上余分に見えるだけで、差分なしと確認）。
- 確認の過程で、`package.json`は0.2.8に上げたが`package-lock.json`側の更新が漏れていたと判明
  （過去のバージョンアップでは常に両方揃えて更新していた慣行に反する）。`npm ci --dry-run`では
  この不一致によるエラーは出ないことを確認済み（実害は小さい）が、publish前に揃えるため修正。
- 対応: `fix/package-lock-version-0.2.8`ブランチで`package-lock.json`のversionを0.2.8に修正し、
  Draft PR #107（base: staging）を作成。`npm test`・`prisma validate`で確認済み。
- 次: PR #107マージ後、`alphadb-publish`で0.2.8をpublish、`staging-prisma-merge-project-build`で
  マイグレーション`20261028113219_add_instance_schedule`をステージングDBに適用（ユーザー実施）。

## 2026-10-29 5_4_3（インスタンス定時起動・停止）alphadb側対応の完了

- `alphadb-publish`と`staging-prisma-merge-project-build`は、どちらもソースブランチが`main`固定
  （`staging`ではない）と判明（alphasyscdk `PrismaMigrateConstruct`で`targetBranch`既定値`main`と
  明記。`alphadb-publish`もブランチ指定なしでデフォルトブランチ＝`main`参照）。そのため正しい順序は
  (1) PR #107を`staging`へマージ → (2) `staging`→`main`の同期PRも作成・マージ → (3) AWSでpublish・
  migration実行、とユーザーに確認。
- ユーザーが1〜3を完了。AWS CLIで実施結果を検証:
  - PR #107マージ・`staging`→`main`同期済み（`main`の`package.json`/`package-lock.json`とも0.2.8で一致）。
  - CodeArtifact: `alphadb`のdist-tags `latest`が`0.2.8`（2026-10-29 08:46〜08:48 JST、`alphadb-publish`
    ビルドSUCCEEDED）。
  - `staging-prisma-merge-project-build`もSUCCEEDED（同時刻、source: main）。マイグレーション
    `20261028113219_add_instance_schedule`をステージングDBに適用済みと確認。
- **alphadb側の対応完了**。5_4_3の3テーブル（`alp_instance_schedule`/`_run`/`_run_detail`）は
  ステージングで利用可能。alphasys/alphaexapiは`alphadb@0.2.8`を指定して取り込む（実装はそれぞれの
  セッションで実施。alphaexapiへは`~/git/alphaexapi/INBOX_FROM_ALPHADB.md`で申し送り済み・未取り込み）。

## 2026-10-29 夜間DBコピー失敗の原因調査

- ユーザー報告: 夜間DBコピーが失敗。「環境ファイル `/etc/alphadb-migration.env` の読み込みに失敗」。
- CloudWatch Logs（`/alphasys/staging/nightly-migration`）で確認: 10/25〜10/27は`RESULT: SUCCESS`、
  10/28・10/29は両日とも`STEP init`で同エラー、`RESULT: FAILED rc=1`。
- 原因: `nightly_automation.md` §7に既出の**Bastion置換問題**の再発。`alphasyscdk/docs/conversations/
  2026-10-27.md`（19:36 JST）によると、同日19:22 JSTの`deploy:staging`実行でBastionが置き換わり
  （新インスタンス`i-08f13fc70ac372bde`）、手動導入済みのPostgreSQL・`/opt/alphadb-migration`一式・
  `/etc/alphadb-migration.env`・systemdタイマーが消失。復旧手順（§7→§9.3）は記録上**未実施のまま**。
  AWS CLIで現在のBastionインスタンスIDが上記と同一（起動時刻も2026-10-27 19:22 JST）であることを
  確認し、以降一度も復旧されていないと判明。
- SSM経由でBastionに直接コマンドを実行しようとしたが、auto modeの権限で拒否されたため未実施
  （ファイル内容の詳細確認はできていない）。
- 対処方針（§7の既存手順どおり）: (1) 手元PCで`deploy.sh`実行 → (2) Bastionで`setup_bastion.sh`実行
  → (3) `/etc/alphadb-migration.env`を実値で再作成 → (4) `systemctl start alphadb-migration.timer`
  → (5) 翌朝`RESULT: SUCCESS`確認。ただし4_7_1の結合試験中は意図的にタイマーを止める運用（§9）との
  関係を要確認。ユーザーに実施可否を確認中（未着手）。

## 2026-10-30 5_4_3のalphadb側対応完了をalphasystemへ報告

- ユーザー指示で、`ListAgents`/`SendMessage`により稼働中のalphasystemセッション（alphasystem-6f）へ
  直接報告（PR #109完了記録・CodeArtifact/CodeBuild確認結果を踏まえ、conversations.mdのサマリ内容を
  要約して送信）。alphaexapiへはINBOXファイルで申し送り済み・未取り込みである旨も併せて伝達。

## 2026-11-15 alphadb を 0.5.0 に版上げ（本番環境構築のバージョン統一）

- 発端: alphasystem-62 から依頼（ユーザー承認「0.5.0 の統一でお願いします」、2026-11-15）。
  仕様: `alphasystem/docs/design/2026-11-10-本番環境構築-仕様.md` 3章の手順1。
- 対応: `feature/version-0.5.0` で `package.json`・`package-lock.json` を 0.2.8 → 0.5.0（スキーマ・マイグレーションの変更なし）。
  `npm test` 10件 pass。Draft PR（base: staging）を作成。
- 段取り（確定）: ① ユーザーが PR を `staging` にマージ → ② `staging` → `main` の同期 PR をマージ（**必須**。
  `alphadb-publish` はデフォルトブランチ `main` を読む）→ ③ `alphadb-publish` を実行 → ④ alphadb が CodeArtifact で
  0.5.0 の Published・`latest` を確認し alphasystem-62 に連絡（alphasys・alphaexapi の `^0.5.0` 化はこれを待って開始）。
  マージのタイミングはユーザーに確認する。マイグレーションの追加は無いので `staging-prisma-merge-project-build` は不要。
- 事前確認（2026-11-15）:
  - CodeArtifact の dist-tag `latest` は `0.2.8`。版は 0.0.1〜0.2.8 と 1.0.0。`npm publish` は新しく出した版に `latest` を付けるため、
    0.5.0 の publish 後は `latest` = 0.5.0 になる見込み（1.0.0 より小さいが、`latest` は semver 順ではなく最後の publish で決まる）。
    `^0.5.0` は 0.5.x のみに一致し 1.0.0 とは干渉しない。publish 後に `latest` の向き先を確認する。
  - `staging` と `main` は内容の差なし（main 側に同期のマージコミットがあるだけ）。alphadb の未マージ PR は無し。
    未着手の issue は #99（部分ユニーク索引、ユーザー判断待ち）のみ。
  - 夜間自動移行: 10/27 の Bastion 置換（i-08f13fc70ac372bde）で 10/28〜11/05 は `STEP init` で失敗していたが、
    11/06 16:34 JST の手動実行で `RESULT: SUCCESS`、以後 11/07〜11/15 は毎晩 SUCCESS（**復旧済み**）。
- 気づき: 10/28〜10/30 の記録が日付別ファイルではなくアーカイブの `conversations.md` に追記されている（README の運用と食い違い）。
  今回は日付別ファイルに記録。移すかどうかはユーザーに確認する。
- Draft PR **#114** を作成し、alphasystem-62 へ報告（PR・段取り・`latest` の見込み・staging の状況〈未マージ PR なし、0.2.6〜0.2.8 適用済み、
  夜間移行は 11/06 に復旧済み〉）。
- issue #99 は 0.5.0 に**含めない**前提で進める（ユーザー判断待ちのため。ユーザーに確認中）。
- alphasystem-62 返信: 仕様 3.5 の「進行中の作業」は alphadb 側は問題なし。順序は提案どおり（#114 → staging→main 同期 → `alphadb-publish`）で了承。
  マージのタイミングはユーザーに確認。0.5.0 が Published・`latest` 確認後に alphasystem-62 へ連絡する。
- **完了**: #114 は staging にマージ済み（03:32Z）、main も 0.5.0。CodeArtifact で 0.5.0 = Published、
  `npm view alphadb dist-tags` → `latest: '0.5.0'` を確認し、alphasystem-62 へ連絡（alphasys・alphaexapi の `^0.5.0` 化の開始可）。

## 2026-11-15 本番の夜間移行のロググループ名（alphasyscdk-ec から連絡）

- 内容: 本番の夜間移行のロググループは `/alphasys/prod/nightly-migration`（alphasyscdk PR #144。`ssm-ec2.ts` が staging 名を固定で持っていて
  本番 deploy が失敗したため環境別に修正）。本番 Bastion のロールの書き込み権限はこの名前のみ。staging は `/alphasys/staging/nightly-migration` のまま。
- 本番配備（仕様 6.4）の際は `/etc/alphadb-migration.env` の `LOG_GROUP` を `/alphasys/prod/nightly-migration` にする。
- alphadb の現状: `nightly_automation.md` の staging 名の記述（§7 表・§9.4 の確認コマンド）はすべて staging 向けで誤りではない。本番向けの手順はまだ無い。
  本番向けの記述（ロググループ名・`--profile` の違い）を追加するかはユーザーに提案中。

## 2026-11-15 本番の夜間移行の手順追加・issue ＃99・10/28〜10/30 記録の移動（ユーザー回答）

- **本番の夜間移行の手順**: ユーザー承認（「お願いします」）。`nightly_automation.md` に「10. 本番への配備」を追加
  （staging と本番の違いの表〈プロファイル・`DST_PGHOST`/`SECRET_ID` の CFN export・`LOG_GROUP=/alphasys/prod/nightly-migration`・
  S3 バケットポリシーへの本番ロール追加〉、仕様 6.4 の順序に沿った手順、翌朝の CloudWatch 確認、カットオーバー時に止める注意）。
  夜間移行キット（スクリプト・`nightly.env.example`）は変更しない。本番アカウントへの AWS 照会は権限で拒否されたため、本番の値は
  CFN export 名・プレースホルダーで記載（本番 Bastion のロール ARN は ProductionStack のデプロイ後に調べる）。
- **issue #99（部分ユニーク索引）**: ユーザー判断「そのまま残す。ただし実運用上はありえないと思われる」。
  **0.5.0 には含めず、issue は OPEN のまま残す**（着手しない）。
- **10/28〜10/30 の記録**: ユーザー指示「日付ごとのファイルに移す」。アーカイブ `conversations.md` から
  `conversations/2026-10-28.md`（2 件）・`2026-10-29.md`（4 件）・`2026-10-30.md`（1 件）へ移動（内容は変更なし、差分で一致を確認）。

## 2026-11-16 本番 DB の確認と本番の夜間移行（alphasystem-62 から依頼、調査・計画）

- 発端: alphasystem-62 から依頼。ユーザー本人が「本番の DB と夜間移行」を最優先に指示した（2026-11-16）。本番は 0.5.0 で起動済み。
  **まず調査と計画のみ。本番への書き込み・設定変更は、計画をユーザーに示して了解を得てから**。
- 依頼側の提供情報: 本番 Bastion `i-09831ef844ed1f96f`、ロール
  `arn:aws:iam::938812705475:role/ProductionStack-SsmEc2BastionInstanceRole3094ABFF-sE0qGlDsifd4`、
  ロググループ `/alphasys/prod/nightly-migration` は本番に存在（alphasystem-62 が読み取りで確認）。
  初回デプロイでマイグレーションが `onCreate` で自動実行済み（CodeBuild `prod-prisma-merge-project-build`、実行 ID 9a2076e9…）。
- 本番アカウントへの AWS 照会は、この session では読み取りでも権限で拒否される（2026-11-15）。そのため本番の状態は
  **未実測**で、CDK・リポジトリから見た見込みを返した:
  - `prod-prisma-merge-project-build` は alphadb `main`（0.5.0）を `prisma migrate deploy`（16 本、最後は `20261028113219_add_instance_schedule`）
    → アプリ用ユーザーへの GRANT。seed は実行しない → 全 33 テーブルが空の見込み。マスタ類は夜間移行の 14 テーブルで入る。
  - 確認方法（読み取りのみ）: CodeBuild の buildStatus とログ → Bastion から psql で `_prisma_migrations`（16 行・全 finished・
    rolled_back 無し、checksum をリポジトリの migration.sql と照合）→ 全テーブルの件数。
- 本番の夜間移行の段取り（`nightly_automation.md` §10、実施はユーザーの了解後）:
  ① 旧システム側（アカウント alphacmc）`alpha-conbackup` のバケットポリシーに本番ロールを追加（staging 分は残す）→
  ② `AWS_PROFILE=prod bash nightly/deploy.sh` → ③ Bastion で `setup_bastion.sh`・`/etc/alphadb-migration.env`
  （`prod-alphasys-db-endpoint`、`prod-alphasys-db-master-secret-arn`、本番の `DB_NAME`、`LOG_GROUP=/alphasys/prod/nightly-migration`）→
  ④ 手動で 1 回実行して `RESULT: SUCCESS` と CloudWatch を確認 → ⑤ `systemctl enable --now alphadb-migration.timer` → 翌朝 CloudWatch で確認。
- カットオーバーの計画との関係: 本番にも毎晩入れる決定（2026-11-10）とは矛盾しない。ユーザー判断が要る点として次を挙げた:
  実在の社員が本番にログインできるようになり個人情報が載る / 本番で入力した 14 テーブルの内容は毎晩 1:00 に消える /
  本番 SES から実在の社員にメールが届く / カットオーバーの最後の投入を夜間移行で行うかはデータ移行の計画（仕様 7-4）で決める。
- alphasystem-62 へ回答済み。ユーザーに次の 3 点を確認中:
  ① この session から `--profile prod` で読み取り照会してよいか、② S3 バケットポリシーの適用者と手順（staging のときはユーザーが適用）、
  ③ 本番に業務データを入れ始めてよいか。
- alphasystem-62 返信:
  - 本番のマイグレーションのビルドは alphasystem-62 が読み取りで確認済み。`prod-prisma-merge-project-build` 9a2076e9… は SUCCEEDED、
    ソースは main の d006337、16 本すべて Applying migration（最後は `20261028113219_add_instance_schedule`）→ **マイグレーションは成功**。
  - Bastion からの psql 確認（`_prisma_migrations`・件数）はマスターシークレットを使うため、ユーザーの了解後に alphasystem-62 か alphadb が行う（決まったら連絡が来る）。
  - 夜間移行は、S3 バケットポリシーの実施者と a〜d の 4 点のユーザー判断が先（alphasystem-62 がユーザーに確認する）。
    **それまで本番への書き込み・設定変更は行わない**。

## 2026-11-16 本番の夜間移行の配備をユーザーが承認（alphasystem-62 経由）

- ユーザー本人が alphasystem のセッションで承認（2026-11-16）:
  - a〜d の 4 点を確認・了承し、**夜間移行を本番に配備してよい**。d（カットオーバーの最後の 1 回の扱い）はデータ移行計画（仕様 7-4）で決める。
  - 旧システム側 S3 バケットポリシーは、staging と同様に**ユーザーが JSON を受け取って適用する**。
  - Bastion の psql での読み取り確認（`_prisma_migrations`・件数）は **alphasystem-62 が行う**（alphadb は不要）。
- 対応: `alpha-conbackup-bucket-policy.json` に本番用 Statement `AllowProdBastionReadNightlyDump`
  （`arn:aws:iam::938812705475:role/ProductionStack-SsmEc2BastionInstanceRole3094ABFF-sE0qGlDsifd4`）を追加（staging 分は残す）。
  `nightly_automation.md` §10.2 の 3 に適用手順（`get-bucket-policy` で現状確認 → `put-bucket-policy` → 確認、プロファイル `alphacmc`）を記載。Draft PR #120。
- 段取り（確定）: ① ユーザーがバケットポリシーを適用 → ② alphadb が alphasystem-62 に `deploy.sh` 以降の段取りを連絡 →
  ③ 本番への書き込み手順（`deploy.sh` → `setup_bastion.sh`・env → 手動 1 回 → タイマー有効化）は **1 つずつ結果を報告**しながら進める。
- 注意: この session からの本番アカウントへの AWS 操作は権限で拒否される。③ を alphadb で行うには、ユーザーがこの session で許可する必要がある（ユーザーに確認中）。

## 2026-11-16 alpha-conbackup のバケットポリシーに本番ロールを適用（ユーザー実施）

- ユーザーが旧システム側（プロファイル `alphacmc`）で `put-bucket-policy` を実施。`get-bucket-policy` で Statement が 2 つ
  （`AllowStagingBastionReadNightlyDump`・`AllowProdBastionReadNightlyDump`）になったことを確認。
- 1 回目は、alphadb が作業フォルダを #119 のブランチに切り替えたままだったため、staging 分だけの旧 JSON が適用された（内容は適用前と同じで影響なし）。
  #120 のブランチに戻して再適用した。
- 次は段取り ③ の ①（`AWS_PROFILE=prod deploy.sh`）。この session からは本番を操作できないため、実行者をユーザーに確認中。

## 2026-11-16 本番の夜間移行 ① deploy.sh 完了（ユーザー実施）

- 本番での実行者: **ユーザーが手元で実行する**（この session には本番の権限を付けていない）。alphadb がコマンドを示し、結果を確認して alphasystem-62 に 1 つずつ報告する。
- ① `AWS_PROFILE=prod bash prisma/doc/migration/nightly/deploy.sh` → `target: i-09831ef844ed1f96f`、`Status: Success`、
  `/opt/alphadb-migration/{nightly,queries}` 一式を確認。alphasystem-62 に報告済み。
- 次: ② `setup_bastion.sh` → ③ `/etc/alphadb-migration.env`（値は CFN export `prod-alphasys-db-endpoint`・`-db-port`・`-db-master-secret-arn`、
  `DST_PGDATABASE=alphasys`〈`.env.prod` に `DB_NAME` が無く共通の `.env` の値〉、`LOG_GROUP=/alphasys/prod/nightly-migration`）→ 中身の確認 → ④ 手動 1 回実行 → ⑤ タイマー有効化。

## 2026-11-16 本番の夜間移行 ② setup_bastion.sh・③ env 完了（ユーザー実施）

- ② `setup_bastion.sh`: postgresql16-server 16.15 を導入・initdb・enable。`alphadb-migration.timer` は enable 済み（start は未）。
- ③ `/etc/alphadb-migration.env`: `DST_PGHOST=prod-alphasys-db-cluster.cluster-cysskdrslk30.ap-northeast-1.rds.amazonaws.com`、`DST_PGPORT=5432`、
  `DST_PGDATABASE=alphasys`、`SECRET_ID` 設定済み、`LOG_GROUP=/alphasys/prod/nightly-migration`。alphasystem-62 に報告済み。
- 次: ④ 手動 1 回実行（`systemctl start alphadb-migration.service`。本番 Aurora の 14 テーブルに旧システムのデータが入る）→ ⑤ タイマー有効化。

## 2026-11-16 本番の夜間移行 ④ 手動 1 回実行 SUCCESS（ユーザー実施）

- `sudo systemctl start alphadb-migration.service` → 10:43:59 JST `RESULT: SUCCESS`、`check.sql` は `NOTICE: check ok`、シーケンス不整合 0。
  alp_users 120 件（男性 86・女性 34）、既定値の補完は email ダミー 51・join_cmp 番兵 26・birthday 番兵 28・user_name_kn 空 33・退職者 62。
- CloudWatch `/alphasys/prod/nightly-migration` にストリーム `nightly-20261116-104354` を確認（本番ロググループへの書き込み OK）。
- **本番 Aurora の移行対象 14 テーブルに旧システムのデータが入った**（2026-11-16 10:43 時点のダンプ）。alphasystem-62 に報告済み。
- 次: ⑤ タイマーを start → 11/17 JST 1:00 が最初の自動実行 → 11/17 朝に CloudWatch で `RESULT: SUCCESS` を確認。

## 2026-11-16 本番の夜間移行 ⑤ タイマー有効化・配備完了（ユーザー実施）

- `sudo systemctl enable --now alphadb-migration.timer` → enabled・active、NEXT `Mon 2026-11-16 16:00:00 UTC`（= 11/17 01:00 JST）。
  **本番への夜間移行の配備（仕様 6.4）完了**。alphasystem-62 に報告済み。
- 段取り（確定）: 11/17 01:00 JST が最初の自動実行 → 11/17 朝に CloudWatch `/alphasys/prod/nightly-migration` で
  `nightly-20261117-…` の `RESULT: SUCCESS` を確認（§10.3）。
- 残課題: 本番の毎日目視の運用にするか（仕様 9-2）、カットオーバー時の最後の 1 回の扱いとタイマー停止（仕様 7-1・7-4）。
  Bastion 置換時の復旧は §7 と同じ（`AWS_PROFILE=prod deploy.sh`）。

## 2026-11-16 本番の夜間移行の運用（ユーザー決定）

- **確認期間中は本番も毎日 CloudWatch Logs（`/alphasys/prod/nightly-migration`）を目視確認する**（仕様 9-2 への回答「OK」）。
- **リリース時は本番の夜間移行を停止する**（仕様 7-1。止め方は `nightly_automation.md` §9.2 と同じく `disable --now`、`--profile prod`）。
- **本番データを staging へ持っていく運用は、個人情報のマスキングも考慮して今後検討する**（今は決めない）。
- `nightly_automation.md` §10 の注意書き・§10.3 の「未決」を上記の決定に更新。alphasystem-62 に連絡。

## 2026-11-21 alphasystem からの申し送り：受領請求書（MF 債務支払）の申請番号を請求に持たせる

- 発端: `INBOX_FROM_ALPHASYSTEM.md`（2026-11-21、改訂版）と alphasystem-24 からの連絡。取り込み後にファイルを削除した。
- 背景: 仕入（債務支払）の請求は、2024/09 から証憑が MF クラウド債務支払の電帳法書類にあり、`bill_doc_id` は空。
  債務支払 CSV の「申請番号」（例 `AP1286`）を取り込み時に保存し、MF 債務支払 API の電帳法書類一覧
  （`ex_transactionable_number` が申請番号）から e_doc ID（例 `3452`）を引いて証憑を表示する。1請求に1申請。
  順序は alphadb → alphaexapi → alphasys。
- **ユーザーの決定**（alphasystem `docs/conversations/2026-11-21.md`「申請番号の持たせ方：請求に列を追加（B）」）:
  申請番号は **`alp_bill_recipt` に列を追加する（案B）**。ただし移行期間中は請求IDと申請番号の対応を一時テーブルで保持し、
  夜間移行の際に戻す。先に届いた「独立表 `alp_bill_recipt_payable`」の案は**採用しない**（旧版の申し送りは破棄）。
- 後続（alphadb の公開後）: 公開した版を alphaexapi-61・alphasys-bb に知らせる。alphaexapi は CSV 取り込みで申請番号を保存し、
  e_doc ID を引いてファイルを中継する API。alphasys は仕入の請求情報画面にプレビュー。staging で確認してから本番。
  CSV の取り込み直し（ADD モード）は、alphaexapi を本番に入れたあとユーザーが実施。

## 2026-11-21 申請番号の列追加と夜間移行の退避・復元：方式をユーザーが承認

- ユーザー承認「B を含めて、1〜5 の方針で進めてください」。確定した方式:
  1. 申し送りを本ファイルに取り込み、`INBOX_FROM_ALPHASYSTEM.md` を削除。
  2. スキーマ: `alp_bill_recipt` に nullable の `payable_application_no` VarChar(32)・`payable_e_doc_id` Int を追加。索引は付けない
     （申請番号から請求を逆引きする要件が無いため）。版は **0.5.0 → 0.5.1**（alphaexapi・alphasys は `^0.5.0` のまま取り込める）。
     `extract.sql`・`load.sql` は列を名前で指定しているため変更なし（入れ直した直後は 2 列とも NULL）。
  3. 夜間移行: 退避テーブル `nightly.bill_recipt_payable_keep`（別スキーマ。Prisma 管理外・FK なし。主キー bill_no、契約番号・請求日・
     申請番号・e_doc ID）を夜間移行のスクリプトが `CREATE ... IF NOT EXISTS` で作る。既存の 1 トランザクションの中で
     `keep_payable.sql`（退避）→ `clear.sql` → ロード → `restore_payable.sql`（復元）→ `verify.sql` → `check.sql` の順に実行。
     - 退避: 申請番号または e_doc ID が入っている行を追加・更新。
     - **B（ユーザー提案から採用）**: 退避と bill_no・契約番号・請求日が一致する請求で、いま 2 列とも NULL なら、日中に空にしたと
       みなして退避から削除する（アプリから申請番号を空にできるようにするため）。
     - 復元: bill_no が同じで、契約番号・請求日も一致する行だけ戻す。戻した件数・不一致件数・行が無い件数をログに出し、
       不一致の bill_no は最大 20 件ログに出す。不一致があっても失敗にはしない。
     - 失敗時はトランザクションごとロールバックされ、退避テーブルも元のまま。
  4. 後片付け: 旧システム停止で夜間移行を止めるときに `DROP SCHEMA nightly CASCADE`。手順を `nightly_automation.md` に書き、
     cutover 計画への追記を alphasystem に依頼する。
  5. 反映の順序: staging・本番それぞれ、**マイグレーションの適用（`staging-`/`prod-prisma-merge-project-build`）を先に**、
     その後に `deploy.sh` でスクリプトを配布する（逆だと、列が無いためその晩の夜間移行が失敗する）。
- 割り切り（ユーザー了承）: 新システムで作った請求（旧システムに無い）は毎晩行ごと消えるため、その申請番号は戻らない
  （旧システムにある請求を更新した場合は戻る）。手動フロー（`load.ps1`）は退避・復元しない。

## 2026-11-21 申請番号の列追加：Draft PR ＃123 作成とリリースの段取り

- 実装: Draft PR **#123**（base: staging、0.5.1）。`npm test` 10 pass、`test_lib.sh` ALL PASS。PGlite で全 17 マイグレーションの適用と
  退避・復元の 6 ケースを確認。Docker が無いため `integration_local.sh` は未実施（staging の手動 1 回実行で初確認）。
- リリースの段取り（確定）: ① #123 を staging にマージ → ② staging→main 同期 PR をマージ → ③ `alphadb-publish`（0.5.1）→
  ④ `staging-prisma-merge-project-build` で staging DB に列を追加 → ⑤ **④の後に** staging Bastion へ `deploy.sh` →
  ⑥ 本番は `prod-prisma-merge-project-build` → `AWS_PROFILE=prod deploy.sh`（時期はユーザー判断）。
  ③の後、alphadb が 0.5.1 の Published・`latest` を確認し、alphaexapi-61・alphasys-bb に版を知らせる。
- alphasystem-24 へ PR を報告し、cutover 計画に「夜間移行停止後、staging・本番で `DROP SCHEMA nightly CASCADE`」の追記を依頼。
- #122（11/16 の記録）と `nightly_automation.md` の末尾が隣接。#122 を先にマージしたら #123 側で staging を取り込んで解消する。

## 2026-11-22 0.5.1 の反映状況（申請番号の列）

- #122・#123・#124（staging→main）はマージ済み。0.5.1 は CodeArtifact に Published。
- `staging-prisma-merge-project-build` は 11/22 14:30 JST に SUCCEEDED（main e0bcf67）。staging DB に 2 列が入った。
- alphasystem-24 の確認（11/22）: staging・本番の Bastion に 0.5.1 のスクリプト（`keep_payable.sql`・`restore_payable.sql`・
  `nightly_migrate.sh`・`lib.sh`）が配布済み（origin/main とハッシュ一致）。本番のマイグレーション（0.5.1）はユーザーが適用済みと報告。

## 2026-11-22 payable_e_doc_id を VarChar(40) に変更：方式をユーザーが承認

- 発端: alphasystem-24 からの依頼（alphasystem でユーザー承認済み。記録は alphasystem `docs/conversations/2026-11-22.md`）。
  MF 債務支払の e_doc の `id` は 22 文字の文字列（例 `vSXUguKk1Ib1fm-o_aQCDg`）で、Int では持てない。既存の値は空。
- **ユーザー承認**「この方式でお願いします」。確定した方式（版は **0.5.2**）:
  1. マイグレーション `20261122100000_bill_recipt_payable_e_doc_id_varchar`:
     `ALTER COLUMN payable_e_doc_id SET DATA TYPE VARCHAR(40) USING payable_e_doc_id::text`。`schema.prisma` は `String? @db.VarChar(40)`。
     `payable_application_no` は変更しない。
  2. 退避テーブルは**作り直さない**。`keep_payable.sql` の CREATE を varchar(40) にし、続けて毎回
     `ALTER TABLE nightly.bill_recipt_payable_keep ALTER COLUMN payable_e_doc_id TYPE varchar(40) USING ::text` で既存の表も型を合わせる
     （既に varchar(40) なら書き換えは起きない）。`restore_payable.sql` は型に依存しないので変更しない。
  3. `nightly_automation.md` §11、`alp_billrecipt.md` の 13 行目を更新。
- **反映の段取り（0.5.1 より厳しい）**: staging・本番それぞれ、**マイグレーションの適用と `deploy.sh` を同じ日中
  （01:00 JST の夜間移行より前）に続けて**行う。片方だけだと型が合わず、その晩の夜間移行が `STEP load` で失敗する
  （ロールバックされデータは変わらない。揃えればその晩から戻る）。PR のマージ・適用は夜間移行の時間帯を避ける。
  alphasystem-24 が段取り・cutover 計画・仕様に反映する。
- 型の影響: 0.5.2 は `^0.5.0` にも入り、`payableEDocId` が number → string になる。alphasystem-24 が alphaexapi-61・alphasys-bb に伝える。
  公開後、alphadb から alphaexapi-61 と alphasystem-24 に版を知らせる。
- 確認: PGlite で全 18 マイグレーション、0.5.1 の int 退避テーブルが varchar(40) に変わり値が文字列で残ること、
  退避・復元の各シナリオ（ALL OK）。`npm test` 10 pass、`test_lib.sh` ALL PASS、`prisma validate` OK。

## 2026-11-22 VarChar(40) 化：Draft PR ＃125 作成とリリースの段取り

- 実装: Draft PR **#125**（base: staging、0.5.2、ブランチ `feature/bill-recipt-edoc-varchar`）。マージ済みの
  `feature/bill-recipt-payable` はローカルから削除。
- リリースの段取り（確定）: ① #125 を staging にマージ → ② staging→main 同期 PR をマージ → ③ `alphadb-publish`（0.5.2）→
  ④ staging: `staging-prisma-merge-project-build` と Bastion への `deploy.sh` を**同じ日中（01:00 JST より前）に続けて** →
  ⑤ 本番: `prod-prisma-merge-project-build` と `AWS_PROFILE=prod deploy.sh` を同じく同じ日中に続けて（時期はユーザー判断）。
  マージ・適用は夜間移行の時間帯を避ける。
- ③の後、alphadb が 0.5.2 の Published・`latest` を確認し、alphaexapi-61・alphasystem-24 に版を知らせる。
- alphasystem-24 へ #125 を報告済み。

## 2026-11-22 0.5.2 のリリース（①〜⑤実施）と確認

- ユーザー報告: ① #125 マージ、② 同期 PR #126 マージ、③ `alphadb-publish`、④⑤ staging・本番ともマイグレーション適用と `deploy.sh` を実施。
- alphadb の確認（staging）: 0.5.2 Published・CodeArtifact の既定版 0.5.2。`staging-prisma-merge-project-build` 17:02 JST SUCCEEDED（main 07a2c01、
  ログに `Applying migration 20261122100000_bill_recipt_payable_e_doc_id_varchar`）。staging Bastion（i-08f13fc70ac372bde）の
  `keep_payable.sql`・`restore_payable.sql`・`nightly_migrate.sh`・`lib.sh` は origin/main とハッシュ一致（配布 16:52 JST）。
- 本番は prod プロファイルが使えないため、ユーザーに確認コマンドを渡して結果待ち。
- alphaexapi-61 に 0.5.2（`payableEDocId` が string）を通知、alphasystem-24 に報告。
- 次の確認: 11/23 01:00 JST の夜間移行（staging・本番）で `RESULT: SUCCESS` と `payable keep`/`payable restore` の NOTICE。
- alphaexapi-61 の返答: 現在は lockfile で 0.5.1 固定、`payableEDocId` には null を入れるだけなので型エラーにならない。
  0.5.2 へは e_doc ID を引く処理を作るときに上げる（alphaexapi 側で方式のユーザー了承待ち）。
- 本番の確認（ユーザー実行の結果を alphadb が確認）: `prod-prisma-merge-project-build` 17:05 JST SUCCEEDED（main 07a2c01、
  `Applying migration 20261122100000_bill_recipt_payable_e_doc_id_varchar`・`All migrations have been successfully applied.`）。
  本番 Bastion（i-09831ef844ed1f96f）の 4 スクリプトは origin/main とハッシュ一致。**staging・本番とも 0.5.2 の反映完了**。

## 2026-11-23 0.5.2 反映後の初回夜間移行（11/23 01:00 JST）

- staging（alphadb が確認）: `nightly-20261123-010017` で `RESULT: SUCCESS`（01:00:24）。
  `payable keep: upserted=0 cleared=0`・`payable restore: restored=0 mismatched=0 missing=0`（申請番号はまだ未投入のため 0 件）。
  varchar(40) に変えた `keep_payable.sql` が本番相当の流れで通ることを確認。
- 本番（ユーザー実行の結果を alphadb が確認）: `nightly-20261123-010036` で `RESULT: SUCCESS`（01:00:43）。
  `payable keep: upserted=0 cleared=0`・`payable restore: restored=0 mismatched=0 missing=0`。**staging・本番とも 0.5.2 後の夜間移行は正常**。

## 2026-11-23 staging で債務支払 CSV（2024/10）を追加モードで取り込み：申請番号の保存を確認

- ユーザーが staging で債務支払 2024/10 CSV を追加モードで取り込んだ（18:16〜18:17 JST）。
- alphadb の確認（staging DB、読み取りのみ）: 請求日 **2024-08-31** の請求 52 件に `payable_application_no`・`payable_e_doc_id` が
  両方入った（申請番号 36 種類。例 bill_no 12034 = `AP90` / `1588Zr_gT-TwvzgNTPUOqQ`）。申請番号あり・e_doc ID 空は 0 件。
  2024-10-31 の請求（106 件）には入っていない。ユーザー回答: 取り込み画面の年月設定が誤りで、CSV は **8 月計上分**（想定どおり）。
- 退避テーブルは現在 0 件。次の確認: **11/24 01:00 JST の staging 夜間移行**で `payable keep: upserted=52`・
  `payable restore: restored=52 mismatched=0 missing=0` と、DB で 52 件が戻っていることを alphadb が確認する。

## 2026-11-23 記録コミットを origin/staging に直接 push：そのまま残すとユーザーが決定

- #127 のマージ後、ユーザーがローカルを staging に切り替え・`docs/record-052-release` を削除していたのに気付かず、alphadb が
  記録コミット e08d9d1（`conversations/2026-11-23.md` の追記のみ）を staging でコミットし、PR を通さず origin/staging に push した。
- **ユーザー決定: revert せず、このまま staging に残す**（次の staging→main 同期 PR で main に入る）。
- 再発防止: コミット・push の直前に `git branch --show-current` で現在ブランチを確認する。

## 2026-11-23 staging で債務支払 CSV を全件取り込み：2024/08 以降の仕入請求を確認

- ユーザーが staging で債務支払の全 CSV を投入（更新は 18:16〜19:09 JST）。
- alphadb の確認（staging DB、読み取りのみ。仕入 = `alp_contract.order_contract IS NOT NULL`）:
  - 2024-08〜2026-09 の仕入請求 1,799 件のうち **1,731 件に申請番号と e_doc ID が両方入った**（申請番号ありで e_doc ID 空は 0、
    e_doc ID はすべて 22 文字、1 つの e_doc ID が複数の申請番号に付いた例なし）。
  - 売上（受注契約）の請求・2024-07 以前の請求に申請番号が入った例はない。
  - 申請番号が無い仕入請求は 68 件（各月 0〜7 件、`bill_doc_id` も空）。CSV に無い（手動登録など）か、取り込みでスキップされたかを
    alphaexapi の取り込みログ（「契約番号…がalphadbに存在しないためスキップ」等）と照合するのが次の確認。
- 11/24 01:00 の staging 夜間移行の期待値は `payable keep: upserted=1731`・`payable restore: restored=1731 mismatched=0 missing=0` に更新。
- **ユーザー判断: 申請番号の無い 68 件は問題なしとし、追加調査はしない**（MF クラウドの債務支払データには仕入勘定ではないものも
  若干含まれるため、件数の差は想定の範囲）。alphaexapi のログ照合・一覧の作成は行わない。

## 2026-11-23 申請番号・e_doc ID を staging から本番へ SQL で写す：方式をユーザーが承認

- 背景: 本番で債務支払 CSV を全件取り込み直すのは時間がかかる。staging と本番の請求は同じ旧システムのダンプから毎晩入るので、
  請求番号・契約番号・請求日は一致する。
- **ユーザー承認「その方式で進めてください」**。方式:
  - staging の 1,731 件（請求番号・契約番号・請求日・申請番号・e_doc ID）を SQL に固めて、本番 Bastion から Aurora に 1 トランザクションで流す。
  - 3 つが一致し、本番で 2 列とも空の請求だけを更新する（既存の値は上書きしない）。
    `payable copy: src= updated= already_set= mismatched= missing=` をログに出す。
  - 退避テーブル（`nightly.bill_recipt_payable_keep`）には直接入れない。`keep_payable.sql` が「2 列とも空＝日中に空にされた」として
    消してしまうため、`alp_bill_recipt` に入れ、翌晩の夜間移行で退避させる。
  - SQL・スクリプトはリポジトリに入れない一回限りのもの（alphadb のスクラッチパッド `payable_copy/`）。
- staging での確認（いずれも ROLLBACK）: そのまま流すと `updated=0 already_set=1731`。同じトランザクション内で値を空にしてから流すと
  `updated=1731 mismatched=0 missing=0`。Bastion へ送った SQL と手元のハッシュの一致も確認。
- 段取り: ① 11/24 01:00 の staging 夜間移行で 1,731 件の退避・復元を確認 → ② ユーザーが本番で `bash run_payable_copy.sh prod dry`
  （期待値 `updated=1731 mismatched=0 missing=0`）→ ③ 期待どおりなら `bash run_payable_copy.sh prod commit`（01:00 前後は避ける）→
  ④ 翌晩の本番夜間移行で `payable keep: upserted=1731`・`restored=1731` を確認。
- ユーザー回答: staging で取り込んだ MF の事業所は本番と同じ（e_doc ID はそのまま本番で使える）。本番での取り込みの有無は ②の
  `already_set` で確かめる。
- 本番 dry run（ユーザー実行）: `src=1731 updated=1602 already_set=0 mismatched=0 missing=129`（ROLLBACK）。
- alphadb の調査（staging）: missing の 129 件は、CSV 取り込みで staging に**新規作成された請求**（bill_no 15468〜15596。旧システムに
  同じ契約・同じ請求日の請求が無い）。本番には無く、staging でも毎晩の入れ直しで消える（新システムで作った請求は戻らない、の割り切り）。
  - 2026-04-30: 旧システムに仕入請求が **0 件**（75 件すべて新規作成）。
  - 2026-08-31: 旧システム 31 件、新規作成 50 件。
  - 残り 4 件（2024-08・2024-10・2024-12・2025-02）は、同額の旧システム請求が別の契約番号にある（MF 側と旧システムで契約番号が違う疑い。
    例 MF 契約 4838 / 旧 4884 の 101,888 円）。
- これにより、11/24 01:00 の staging 夜間移行の期待値は `payable keep: upserted=1731`・`payable restore: restored=1602 mismatched=0 missing=129`
  に修正。1,799 件・68 件の集計にも新規作成の 129 件が含まれていた。
- **ユーザー報告: 本番で `run_payable_copy.sh prod commit` を実行し確定**（1,602 件）。
- ユーザー回答: 2026-04-30 の仕入請求 0 件は旧システム側の取り込み漏れ。2026/08 分も同様。**本番側で取り込み直した**。
  → alphadb から確認中: 「本番側」が新システム（alphaexapi の CSV 取り込み）なら、旧システムに無い請求として作られるため、
  夜間移行が続く間は毎晩の入れ直し（clear.sql）で請求ごと消える。旧システムへの登録か、取り込み先の確認が必要。
- ユーザー回答: **新システムの本番では何もしていない**（取り込み直しは旧システム側）。→ 新システムで作った請求が夜間に消える問題は無い。
  旧システムに登録した 2026/04・2026/08 の仕入請求は、次の夜間移行（11/24 01:00）で staging・本番に入る。申請番号はまだ空なので、
  入った後にその 2 か月分の申請番号を付ける必要がある（方法はユーザーと相談）。

## 2026-11-24 11/24 01:00 夜間移行（staging）：旧システムでの再登録で請求番号が変わり、申請番号が一部戻らず

- staging `nightly-20261124-010017`: `RESULT: SUCCESS`。`payable keep: upserted=1731 cleared=0`、
  `payable restore: restored=1491 mismatched=129 missing=111`。
- 原因: 旧システムでの取り込み直しで、2026-04-30（75 件、新規）・2026-08-31（81 件。既存 31 件も番号が変わった）・
  2026-09-30（80 件。旧 約15391〜15467 → 15624〜15703）の仕入請求が新しい bill_no で入った。
  - missing 111 = 消えた旧 bill_no（08 月 31 + 09 月 80）。mismatched 129 = staging で新規作成した bill_no（15468〜）が別の請求に使われた
    （照合で弾かれ、誤復元なし）。
  - 04・08・09 月の仕入請求は申請番号 0 件。退避テーブルには 1,731 件（契約番号・請求日付き）が残っている。
- 本番も同様と見込む（本番の退避は 1,602 件のみで、04 月 75 件・08 月 50 件は本番の退避に無い）。本番ログはユーザーに確認依頼。
- 付け直し方をユーザーに提示（未決定）: A 3 か月分の CSV を staging・本番で取り込み直す / B staging の退避テーブルから
  契約番号＋請求日（各 1 件）で突き合わせる一回限りの SQL を staging→本番に流す。あわせて、restore を契約番号＋請求日でも
  照合する恒久対策の要否、09 月も旧システムで登録し直したかをユーザーに確認中。
- 本番 `nightly-20261124-010036`（ユーザー実行の結果を alphadb が確認）: `RESULT: SUCCESS`。`payable keep: upserted=1602 cleared=0`、
  `payable restore: restored=1491 mismatched=0 missing=111`。見込みどおり（08 月 31 + 09 月 80 の旧 bill_no が消えた分）。
  本番も 04・08・09 月の仕入請求は申請番号なし。

## 2026-11-24 付け直しは B（SQL）、恒久対策は契約番号＋請求日での照合：ユーザー決定

- **ユーザー決定**: ① 付け直しは **B**（staging の退避テーブルから契約番号＋請求日で突き合わせる一回限りの SQL）。
  ② 旧システムでは「しばしば訂正が入る」ので、夜間移行の復元を**契約番号と請求日でも照合して戻す**ようにする。
- B の実施（staging、alphadb）: 退避 1,731 件（契約番号＋請求日はすべて一意）を元に、組の請求がちょうど 1 件・2 列とも空のものだけ更新。
  試行 → 確定とも `payable relink: src=1731 updated=236 already_set=1428 ambiguous=63 nomatch=4`、`RESULT: COMMITTED`。
  04 月 75/75・08 月 81/81・09 月 80/80 に申請番号あり、全体 1,727 件。nomatch 4 件は MF と旧システムで契約番号が違う 4 件。
  スクリプト: alphadb スクラッチパッド `payable_relink/run_payable_relink.sh`（SQL は同フォルダの `apply_payable_copy.sql`）。
- 恒久対策: Draft PR **#130**（`feature/nightly-payable-relink`、base staging。スクリプトのみ、版・マイグレーションなし）。
  - restore に ② relinked（組の請求 1 件・未復元の退避行 1 件・請求が空のときだけ）、ambiguous（組の請求が 2 件以上）を追加。
  - keep に superseded（付け直し済みの旧 bill_no 行を消す）と、付け直した請求を空にした場合の「空にされた」扱いを追加
    （PGlite のテスト作成中に、付け直した翌日に空にすると値が戻る抜けに気付き、対処）。
  - staging Aurora で keep→restore を ROLLBACK 付きで試行: `upserted=1727 superseded=236`、`restored=1727 mismatched=0 missing=0`。
- **段取り（順序が重要）**: 本番は ③ `bash run_payable_relink.sh prod dry`（期待値 `updated=236`）→ ④ `prod commit` → ⑤ #130 をマージ →
  ⑥ staging・本番に `deploy.sh`（マイグレーション不要。01:00 は避ける）。**付け直し（④）より前に #130 を本番に配布しない**
  （「空にされた」判定の拡張で、付け直されていない 236 件相当が退避から消えるため）。staging は付け直し済みなので #130 マージ後すぐ配布してよい。

## 2026-11-24 本番の付け直し・＃130 マージ完了、スクリプト配布の段取り

- ユーザー報告: ③④ 本番で `run_payable_relink.sh prod dry` → `prod commit` を実施（出力は未共有）。⑤ #130 をマージ（main 同期 #131 済み）。
- ⑥ 配布の段取り（確定）: `deploy.sh` は手元の作業ツリーを固めて送るため、alphadb の作業ツリーを main（a1259b6）にそろえ、
  配布が終わるまでブランチを切り替えない。ユーザーが Git Bash で `bash prisma/doc/migration/nightly/deploy.sh`（staging）→
  `AWS_PROFILE=prod bash prisma/doc/migration/nightly/deploy.sh`（本番）を実行。01:00 前後は避ける。
  配布確認は Bastion の sha256（keep_payable.sql `41b19815…cc6e`、restore_payable.sql `87402faf…6f50`。nightly_migrate.sh・lib.sh は変更なし）。
  staging は alphadb、本番はユーザーが確認コマンドを実行。
- 次の確認: 11/25 01:00 の夜間移行。staging は `superseded=236`・`restored=1727 relinked=0 mismatched=0 missing=0` の見込み。
  本番は `mismatched=0 missing=0`（restored は付け直し結果次第で約 1,727）。
- ⑥ 完了: ユーザーが staging・本番に配布し、本番の配布後確認も問題なし（ユーザー報告）。staging Bastion は alphadb が確認し、
  keep_payable.sql・restore_payable.sql・nightly_migrate.sh・lib.sh とも main とハッシュ一致（配布 07:34 JST）。

## 2026-11-24 alp_usercost の賞与の重複登録：2024/07・2026/12 を削除すると決定

- 確認（staging DB、11/24 01:00 の夜間移行時点。本番も同じ旧システムから入るので同じ内容のはず）:
  給与（SALARY）は 2023/07〜2026/02（32 か月・1,679 件）。賞与（BONUS）は 2023/12（23 件）・2024/06（31）・2024/07（31）・
  2025/12（16）・2026/12（16）。
- 2024/07 は 2024/06 と、2026/12 は 2025/12 と、全員（31 人・16 人）の金額の列がすべて同じ（ym・作成日・更新日以外）。
- **ユーザー判断: 2024/07 と 2026/12 の賞与は入力誤りで、削除が必要。**
- `alp_usercost` は夜間移行で毎晩旧システムから入れ直すため、削除は旧システム側で行う（新システムで消しても翌朝戻る）。
  **ユーザーが現行（旧システム）側で削除を実施する**（11/24 ユーザー回答「現行側で実施します」）。
  削除後の夜間移行で staging・本番に反映される。反映後、alphadb が staging で 2024/07・2026/12 の BONUS が 0 件になったことを確認する。

## 2026-11-25 MfJobType に DC_CSV_IMPORT を追加（0.5.3）：方式をユーザーが承認

- 発端: alphasystem-a1 からの依頼（11/24）。DC加入者コードCSV取込の仕様が確定
  （alphasystem `docs/design/2026-11-24-DC加入者コードCSV取込-仕様.md`、Draft PR #167）。alphadb の作業は enum の追加と publish のみ。
- **ユーザー承認**「その方式で進めてください」。確定した方式（版は **0.5.3**）:
  1. `schema.prisma` の `MfJobType` の末尾に `DC_CSV_IMPORT` を追加（表・列の変更なし）。
  2. マイグレーション `20261125090000_add_mf_job_type_dc_csv_import`: `ALTER TYPE "MfJobType" ADD VALUE 'DC_CSV_IMPORT';`
     （`prisma migrate diff` の出力と一致。2026-10-22 の `EMPLOYEE_CSV_IMPORT` と同じ形）。
  3. `alp_mf_job.md` のジョブ種別に追記。`package.json` を 0.5.3 に。
- 夜間移行への影響なし（`alp_mf_job` は入れ直し対象外、退避・復元にも無関係）。`deploy.sh` は不要で、
  0.5.2 のような「適用と deploy.sh を同じ日中に」の制約もない。
- リリースの段取り: ① PR を staging にマージ → ② staging→main 同期 PR をマージ → ③ `alphadb-publish`（0.5.3）→
  ④ `staging-prisma-merge-project-build` → ⑤ `prod-prisma-merge-project-build`（時期はユーザー判断）。
  マージ・適用は夜間移行の時間帯（01:00 JST 前後）を避ける。③の後、alphadb が 0.5.3 の Published・既定版を確認し、
  alphaexapi・alphasys・alphasystem-a1 に版を知らせる（`MfJobType` を網羅した `Record`/switch は型エラーになる旨も伝える）。
- 確認: PGlite で全 19 マイグレーション適用、enum の末尾が `DC_CSV_IMPORT`。`prisma validate` OK、`npm test` 10 pass。
- 実装: Draft PR **#136**（base: staging、ブランチ `feature/mf-job-type-dc-csv-import`）。alphasystem-a1 に PR・段取り・型エラーの注意を報告済み。

## 2026-11-25 0.5.3（DC_CSV_IMPORT）の公開と通知

- ユーザー報告: ①〜③ 完了（#136 マージ、staging→main 同期、`alphadb-publish`）。
- alphadb の確認: origin/main に `DC_CSV_IMPORT`・マイグレーション `20261125090000_add_mf_job_type_dc_csv_import`・版 0.5.3 が入っている。
  CodeArtifact（alphacmc/alphadb-npm）で 0.5.3 が Published（09:24 JST）、既定版 0.5.3。
- alphaexapi-61・alphasys-bb に 0.5.3 を通知（`MfJobType` を網羅した Record/switch が型エラーになる旨、適用前の DB に
  `DC_CSV_IMPORT` のジョブを書くと失敗する旨）。alphasystem-a1 に報告。
- 残り: ④ `staging-prisma-merge-project-build`、⑤ `prod-prisma-merge-project-build`（ユーザー実施、本番の時期はユーザー判断）。
  実施後、alphadb が staging のビルドログで `Applying migration 20261125090000_add_mf_job_type_dc_csv_import` を確認する。
- ユーザー報告: ④⑤ 完了（staging・本番の `prisma-merge-project-build`）。
- alphadb の確認（staging）: `staging-prisma-merge-project-build` 09:25〜09:26 JST SUCCEEDED（main 5ee81e8）、ログに
  `Applying migration 20261125090000_add_mf_job_type_dc_csv_import`・`All migrations have been successfully applied.`。
  staging DB の `MfJobType` の末尾に `DC_CSV_IMPORT`。本番は prod プロファイルが使えないため、ユーザーに確認コマンドを渡して結果待ち。
- 本番の確認（ユーザー実行の結果を alphadb が確認）: `prod-prisma-merge-project-build` 09:28 JST SUCCEEDED（main 5ee81e8）、
  `Applying migration 20261125090000_add_mf_job_type_dc_csv_import`・`All migrations have been successfully applied.`。
  **staging・本番とも 0.5.3 の反映完了**（ログの `role "***" already exists` は staging と同じで、ビルドは成功）。

## 2026-11-25 11/25 01:00 夜間移行が users の email 重複で失敗：抽出で一意化する（案B）をユーザーが承認

- 結果: staging・本番とも `RESULT: FAILED (STEP load) rc=3`。`loading 05 users...` で
  `duplicate key value violates unique constraint "alp_users_email_key"`。1 トランザクションなので全体がロールバックされ、
  両環境とも 11/24 01:00 時点のデータのまま（新システム側のデータも無事）。直すまで毎晩同じ所で失敗する。
- 原因: 旧システムで再入社した 2 人が新しい scode で登録され、退職前の行と同じ email を持っている
  （scode 76→141、107→140。旧システムは email の重複を許す）。旧 alp_user は 120→123 人（140・141・142 を追加）。
  新システムの `alp_users.email` は UNIQUE（`user_id` は UNIQUE ではないので問題なし）。
- ロールバック前の NOTICE で付け直しの効果は確認: `payable keep: upserted=1727 cleared=0 superseded=…`（本番 111、staging 236。見込みどおり）。
- 案A（旧システムで退職前の行の email を空にする）と案B（alphadb の抽出で一意化）を提示。**ユーザー承認「案Bでお願いします」**。
  実 email を残す行は提案どおり **scode が最大の行**（今回の 2 人はどちらのルールでも再入社後の行になる）。
- 実装: `queries/extract.sql` の 05 users の email を
  `CASE WHEN NULLIF(email,'') IS NULL OR scode < max(scode) OVER (PARTITION BY NULLIF(email,'')) THEN 'retired-'||scode::int||'@invalid' ELSE email END`
  に変更。`overview.md` の email 行に規則を追記。
- 確認（staging Bastion、今朝のダンプ）: 抽出 123 行・email 123 種類（ダミー 53 = 空 51 + 重複 2）、76・107 がダミー、140・141 が実 email。
  extract.sql を差し替えた夜間移行の全手順を check の後に例外を入れてロールバックで通し、全 14 テーブルの投入・
  `payable restore: restored=1727 relinked=0 ambiguous=0 mismatched=0 missing=0`・`check ok` まで通過。staging DB は変わらず（users 120）。
- 反映の段取り: PR を staging にマージ → staging→main 同期 → main の作業ツリーで staging・本番に `deploy.sh`
  （**今夜 01:00 より前**に配布すれば今夜から通る）。スキーマ変更・publish は不要。配布後、alphadb が staging Bastion の
  extract.sql のハッシュを確認し、11/26 01:00 の夜間移行の結果を確認する。
