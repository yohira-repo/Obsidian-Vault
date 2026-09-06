# coopbatch 作業ログ

## 2026-07-22 CSVバッチ処理のログ出力見直し（提案）

### 背景
実データCSVでのテストは成功。ただしデバッグログが過多。以下4点の観点で見直しを依頼された。
1. 1レコード毎の成功ログを出さない
2. CSVファイル単位で入力件数・エラー件数・追加/更新件数を出す
3. エラー時はキー項目を表示する
4. CSVの移動・削除もログ表示する

### 調査結果（現状）
- `chunkSize: 1` が `step1_processContract` / `step2_processBill` / `step3_processEarlyBill` すべてに設定されており（`src/jobs/main-batch-job.ts`）、Writerの`write()`が1CSV行ごとに呼ばれる。そのため以下が実質「1レコード毎の成功ログ」になっている。
  - `src/batch/writers/upsert-item-writer.ts:73`
  - `src/batch/writers/upsert-bill-writer.ts:61`
  - `src/batch/writers/upsert-contract-writer.ts:32`
- `src/framework/step-executor.ts:107` の "Progress: Read X, Write X, Errors X" も `chunkSize(1) * 10` = 10行ごとに出力されており、大量データでは非常に多くなる。
- CSVファイル単位の集計ログは存在しない。現状は「1レコード毎」「Step単位（同一タイプの全ファイル合算）」「Job単位（全Step合算）」の3段階のみ。
- `StepExecution.errorCount` は `processor.process()` が例外をthrowした場合のみ加算される。実際の業務エラー（契約なし、重複、契約番号特定不可等）は `ErrorRecordCollector.add()` + `return null` で処理されており、`errorCount` にカウントされない（バグ気味）。
- エラー発生時、現在はコンソールに一切ログを出さず、`ErrorRecordCollector` に無言で蓄積し、Step終了後にエラーCSVとしてS3出力するのみ（`src/batch/writers/error-csv-writer.ts`）。
- CSV移動/削除は既に対応済み：`S3Service.moveFile`（`src/services/s3-service.ts:98`）がファイル単位で "S3 moved: src -> dest" を出力し、`FileCleanupTasklet` が集計ログも出力。`S3Service.deleteFile` は現状どこからも呼ばれていない未使用コード（削除操作自体が現パイプラインに存在しない）。
- `LoggingProcessor` / `ValidationProcessor` / `PrismaItemWriter`（`src/framework/`配下）はサンプル用途のみでexportされているだけで、実バッチでは未使用。

### 提案した修正方針
A. Writerの成功ログ（1行毎）を廃止し、件数のみ内部集計 → ファイル単位サマリーでまとめて出力。
B. `step-executor.ts` の Progress ログは廃止 or 頻度見直し（要ユーザー判断）。
C. ファイル単位サマリー実現のため:
   - `ItemReader` に任意メソッド `getCurrentFileName?()` を追加、`S3CsvReader` で実装。
   - `StepExecutor` がファイル切り替わりを検知し、Stepに追加する任意フック `onFileComplete?(fileName, counts)` を都度呼び出す。
   - `main-batch-job.ts` 側で `onFileComplete` を実装し、`errorCollectors` からそのファイル分のエラー件数を集計して `CSV[ファイル名] 入力:X件 追加・更新:Y件 エラー:Z件` を出力。
D. エラー時のキー項目表示:
   - `ErrorRecordCollector` にCSVタイプ別の「キー項目名リスト」を持たせ、`add()` 呼び出し時にキー項目のみ `console.warn`。フルレコードは従来通りエラーCSVに出力。
   - `ItemProcessor.process(item, fileName?)` にオプション引数を追加し、ファイル名をエラーログ・エラーCSVの両方に伝搬。
E. ファイル移動/削除ログは現状維持（要件を満たしている）。

### ユーザー承認内容（2026-07-22）
- 修正後のログ一覧案：承認
- Progressログ（10行毎）：不要（廃止）
- ファイル単位サマリーの設計（`getCurrentFileName?()` / `onFileComplete?` 拡張）：承認
- エラー時キー項目：契約=契約番号・需要家提示お客さま番号・連携種別／請求=契約番号・通し番号・請求年月・サービス種別／速報値=contractNumber・adjustYear・adjustMonth・stopFlag

### 実装内容
- `src/framework/types.ts`: `ItemReader.getCurrentFileName?()`、`ItemProcessor.process(item, fileName?)`、`Step.onFileComplete?()`、`FileProcessCounts`型を追加
- `src/framework/readers/s3-csv-reader.ts`: `getCurrentFileName()`を実装（現在読み込み中のS3ファイル名を追跡）
- `src/framework/step-executor.ts`: Progressログを削除。ファイル切り替わり検知でファイル単位の入力/書き込み件数を集計し`onFileComplete`を呼び出す
- `src/framework/error-record-collector.ts`: コンストラクタに`label`・`keyFields`を追加。`add()`時にキー項目のみ`console.warn`出力、`countForFile()`を追加
- `src/batch/processors/{bill,contract,early-bill}-processor.ts`: `fileName`をエラー登録まで伝搬
- `src/batch/writers/{upsert-item,upsert-bill,upsert-contract}-writer.ts`: 1件毎の成功ログを削除
- `src/jobs/main-batch-job.ts`: `errorCollectors`にラベル・キー項目を設定、各Stepに`onFileComplete`を追加してファイル単位サマリー（`CSV[ファイル名] 入力:X件 追加・更新:Y件 エラー:Z件`）を出力
- `src/batch/writers/error-csv-writer.ts`: エラーCSVに`source_file`列を追加

### 確認
- `npx tsc --noEmit` / `npm run build` ともにエラーなし
- プロジェクトに自動テスト基盤（test script）が存在しないため、テストコードの追加は行っていない

### ステータス
実装完了。PR #5 作成済み（https://github.com/alphacmc/coopbatch/pull/5 ）。

## 2026-07-24 契約CSVファイルが「未対応ファイル」として無処理スキップされる不具合を発見・修正

### 経緯
PR #5作成後、実データCSVで実行したところ以下の警告ログが出た。
```
Unexpected file type. filename: 110610997IF-K010_2026072319505801.csv
```

### 原因
`src/types/csv-types.ts`の`detectCsvFileType()`が契約ファイル判定に`sftpFileNameConstants.contractFile.prefix`（`UKETSUKE`）しか見ておらず、同オブジェクトに定義済みの`include`（`K010`）を一切参照していなかった。
`~/git/coop/document/csv_file/construct.csv.md`（仕様書）には契約ファイルの命名規則として以下の2パターンが明記されている。
```
110610997IF-K010_年月日時.csv   ← 本番想定パターン（includeのみ一致、prefixは不一致）
UKETSUKE-K010-日時.csv           ← prefixパターン
```
本番パターンの方は`include`判定が実装されていなかったため、`detectCsvFileType()`が`null`を返し、`sftp-service.ts:57-58`のガード（`if (fileType)`）で一覧に追加されず、**ダウンロード・S3アップロード・処理・移動のいずれも行われず完全にスキップ**されていた。

### 修正内容
`detectCsvFileType()`のCONTRACT判定を`prefix`と`include`のOR条件に変更（`src/types/csv-types.ts`）。PR #5に含めてコミット。

### ステータス
実装・型チェック完了。PR #5へ追加コミット済み。

## 2026-08-15 pinoロガー導入・本番クラッシュ対応・組合員番号null時のJob全体停止バグ調査

### pinoロガー導入（PR #14）
- 全ログの先頭にタイムスタンプが欲しいとの要望を受け、`console.log/warn/error`（約90箇所）をpinoベースの`src/logger.ts`に置換。ローカルは`pino-pretty`で整形出力、本番はJSON出力。
- 起動時ログに`package.json`のバージョンを表示する機能も追加（コンテナイメージ更新確認用）。
- **本番障害**: `NODE_ENV`で`pino-pretty`使用を分岐していたところ、本番イメージは`npm ci --omit=dev`で`pino-pretty`（devDependencies）を含めずビルドされるため、`NODE_ENV`未設定時に`Error: unable to determine transport target for "pino-pretty"`でクラッシュ。`require.resolve('pino-pretty')`で実際に解決可能かどうかで判定する方式に修正（PR #15、緊急対応）。
- 副次的に、`s3-recovery-tasklet.ts`に残っていた同種の`endsWith`部分一致バグ（H-5相当）も完全一致に修正。dotenvの広告tip出力も`quiet: true`で抑制。

### 組合員番号（memberCode）が空の契約CSV行でJob全体が停止するバグ（対応済み）

#### 経緯
旧バッチ(coopcdebatch)では組合員番号が空の契約行があると、以下のように行単位のエラーとして処理される。
```
WARN 組合員番号:null / 契約情報:912779729 / TypeError: Cannot read properties of null (reading 'toString')
LOG  取得情報総件数:45 / 正常件数:44 / 異常件数:1
LOG  S3 file moved to temporary/ folder: ...
ERROR DB保存に失敗しました。
```
coopbatchでは同じ状況で「情報が一切残らず、そのStepで終わり、後続Step（請求・速報値）も実行されない」という報告を受けた。

#### 原因（review.md M-2と同根、実データで顕在化）
- `contract-processor.ts`の更新系メソッド（`processUpdateContractWithoutModifySupplyStartDate`等）は、他フィールドが`row.x ?? oldValidContract.x`（既存契約の値へフォールバック）なのに対し、**`memberCode`だけ`row.memberCode ?? ''`（空文字固定）**になっている（例: `contract-processor.ts:172`）。
- この空文字がPrisma updateのwhere句（複合キー`contractNumber_memberCode`）に使われ、実DBレコードとマッチせず`P2025`（Not Found）がWriter内で発生。
- `step-executor.ts`の`executeChunkStep`は**Processorの呼び出しのみ**try/catchで保護しており、**Writerの`write()`呼び出しは無防備**。そのため例外がStep/Jobの外まで伝播し、`errorCollector`に一切記録されないままJob全体が失敗、`for`文の中断により後続Stepが実行されない。
- 旧バッチも実は同型の`.toString()`クラッシュを起こすが、行単位のtry/catchで握りつぶして次行へ継続するため症状が軽微に見えていた。

#### 実装内容（両方とも対応）
1. **主因の修正**: `ContractProcessor.process()`の契約番号チェック直後に、組合員番号のバリデーションを追加（`src/batch/processors/contract-processor.ts`）。
   ```ts
   if (!normalized.memberCode) {
     this.errorCollector.add(row, '組合員番号を特定できません', fileName);
     return null;
   }
   ```
   契約番号チェックと同じパターンで、該当行のみスキップしエラーCSVに記録、残りの行・後続Stepは継続する。
2. **保険的な修正**: `step-executor.ts`の`executeChunkStep`（`writePendingChunk`）でWriterの`write()`呼び出しをtry/catchで保護。失敗時は`stepExecution.errorCount`に書き込み失敗分を計上してJobを継続する（Job全体が落ちなくなる）。`fileCounts.write`は書き込み成功時のみ加算するよう変更。

#### 確認
- `npx tsc --noEmit` / `npm run build` エラーなし
- Writerが例外を投げるケースをモックしたスモークテストで、Stepが`COMPLETED`のまま継続し（`errorCount`加算、`writeCount`は成功分のみ）、`onFileComplete`も正しい件数で呼ばれることを確認

#### ステータス
実装・確認完了。review.md M-2に対応済みマーク。PR #18作成・マージ済み。

## 2026-08-17 解約(04/05)時の組合員番号NULL許容（仕様変更）

### 経緯
PR #18マージ後、ユーザーより仕様変更依頼。「契約情報CSV（xxx_K010_xxx）で解約データ(連携区分=04,05)の場合は、組合員番号=NULLのケースでもエラーとせず、契約テーブル（contract）の組合員番号を採用したい。警告ログ（組合員番号がNULLのためcontractよりXXXXXを適用）を表示したい」との要望。

### 実装内容
- `ContractProcessor.process()`から組合員番号の一律バリデーションを削除し、各連携種別メソッド側でチェックするよう変更
- 新規契約(02/06)・名義変更(91)・その他変更(93): 組合員番号が空なら引き続き即エラー（`組合員番号を特定できません`）。フォールバック先がない、または解約以外は仕様上厳格に扱うべきため
- 解約(04/05・`processCancelContract`)のみ: `resolveMemberCode()`ヘルパーを新設し、CSVの組合員番号が空の場合は契約マスタの組合員番号を採用。ログ`[CONTRACT] 組合員番号がNULLのためcontractより${memberCode}を適用 (契約番号=...)`を出力し、エラーには計上しない。契約マスタ側にも値がない場合のみエラー
- `docs/coop/contract.md`を新仕様に合わせて更新

### 確認
- `npx tsc --noEmit` / `npm run build` エラーなし
- スモークテストで、解約(04)・組合員番号空のケースが契約マスタの値で正常継続（エラー0件、警告ログ出力）、その他変更(93)・組合員番号空のケースは引き続きエラーになることを確認

### ステータス
実装・確認完了。PR #19作成済み。

### 2026-08-18 レビュー指摘対応（PR #19差し戻し）
ユーザーより指摘: `!oldValidContract`分岐（有効契約が無く、解約連携済とみなすケース＝再度の解約日連携等）で、組合員番号が空の場合に`getAnyContractByContractNumber()`で**契約番号のみ**をキーに契約マスタを検索していたが、名義変更履歴がある契約番号は複数の組合員番号のレコードが存在し得るため、対象レコードを一意に特定できず誤ったレコードを更新する恐れがある、との指摘。

#### 修正内容
- `!oldValidContract`分岐では契約マスタへのフォールバックを廃止し、組合員番号が空の場合は素直にエラー（`組合員番号を特定できません`）とするよう変更
- フォールバックは`oldValidContract`が存在する分岐（有効契約は契約番号につき1件の前提があり一意に確定できる）のみに限定
- 不要になった`getAnyContractByContractNumber()`ヘルパーを削除
- `docs/coop/contract.md`を再修正

#### 全体レビュー結果
他の連携種別（新規02/06・名義変更91・その他変更93）は、いずれも`getOldValidContractByContractNumber`（有効契約は1件の前提）または組合員番号込みの完全PK（`getOldContractByPk(contractNumber, row.memberCode)`、row.memberCodeは事前ガードで必須化済み）でのみ検索しており、契約番号のみのあいまいな検索は行っていないことを確認。問題があったのは`processCancelContract`の`!oldValidContract`分岐のみ。

#### 確認
- `npx tsc --noEmit` / `npm run build` エラーなし
- スモークテスト3パターンで確認: ①有効契約あり+組合員番号空→フォールバック成功、②有効契約なし+名義変更履歴あり+組合員番号空→エラー（修正前は誤ったレコードを更新するリスクがあった）、③有効契約なし+組合員番号明示→従来通り成功

#### ステータス
実装・確認完了。PR #19へ追加コミット済み。

## 2026-08-21 「処理済みファイルが大量に再処理される」不具合の調査（review.md M-1が本番実害として顕在化）

### 経緯
ユーザーから、SFTPサーバーに残っていた既処理済みファイルが再処理される不具合の相談。実際のワークフロー：本番が3ファイルを正常処理→その3ファイルをSTG環境のSFTPサーバーへコピー→STGでcoopbatchを実行→新規3ファイル以外にも多数のファイルが処理された。ユーザーはS3タイムスタンプの影響を疑い、DBを戻し、SFTPサーバーから新規3ファイルのみ残して削除の上、再実行して事象を切り分けた。

### 調査の過程（誤った仮説を含む）
AWS CLI（`coop`プロファイル）で本番・STGの実バケット（`coopcde-prd-batch-csv-backup` / `coopcde-stg-batch-csv-backup`）を直接調査。
1. **仮説1（誤り）**: 本番からSTGへのS3同期タイミングとSTGバッチ実行の競合。S3バージョニングで削除マーカーの履行を確認したが、ユーザーからの指摘（名義変更で複数組合員番号のレコードが同一契約番号で存在し得る、という別件の指摘と類似の鋭い反論）で不十分と判明。
2. **仮説2（誤り）**: 本番はエラーの都度対応してtreatedへ移動しているはずで、STGだけが先行処理していたとは考えにくい、との指摘を受け再検証。
3. **真因**: `S3Service.listFiles()`（review.md M-1で既知指摘）が`ListObjectsV2`を1回しか呼んでおらず、最大1000件しか返さない。STGの`treated/`が本番同期で2286件に増えたことでこの上限に達し、辞書順で1000件目より後ろに来る`UKETSUKE-K010_*`ファイルが一覧から漏れ、「未処理」と誤判定されて再ダウンロード・再処理されていた。
4. ユーザーからの追撃「ファイル名は1/Uで始まり、Uは常に後方に来るはず。本番でも同じことが起きていないのは納得できない」を受け、本番バケットで直接検証 → **本番でも`UKETSUKE`系ファイルは1回のAPI呼び出しで1件も見えないことを確認**。本番でも同様の再処理（重複エラーとして日々のエラーCSVに紛れていた可能性）が発生していたと判断。
5. `coopcdebatch`（レガシー）のコードも確認したところ、**全く同じ実装**（`ListObjectsV2`を1回だけ呼ぶ）だった。症状が本番で目立たなかったのは、3年かけて緩やかに件数が増えたため一度に大量の対象ファイルとぶつからなかっただけ、という程度の説明しかできず、これも完全な説明ではない。

### 方針決定
- **現行coopcdebatch**: 影響が本番のみで緊急度が高いため、暫定対応として1回のAPI呼び出し上限を2000件相当に引き上げる方針。対応は別担当（新人）が実施するため、本セッションでは着手しない。
- **次期coopbatch**: 案B（ファイル単位の`HeadObject`存在確認方式）を採用。運用上のファイル残存数は「請求日7件+その他6日×3件＝最大25件程度」で、1件ずつの存在確認への変更でコスト増は無視できる。ブランチを切ってPR作成まで対応。

### 実装内容（ブランチ: `fix/s3-treated-check-avoid-list-truncation`）
- `S3Service`に`fileExists(key): Promise<boolean>`を新設（`HeadObjectCommand`、404は`NotFound`例外を捕捉してfalse）
- `SftpDownloadTasklet.isProcessTargetFile`（一覧取得+ローカルフィルタ）を`filterProcessTargetFiles`に置き換え、SFTP側の各ファイルごとに`fileExists()`で直接存在確認する方式に変更
- `collectS3WorkingFiles()`も同様に、事前取得した`treatedFileKeys`配列を受け取る方式から、`s3SuccessPrefix`を受け取ってファイルごとに`fileExists()`を呼ぶ方式に変更（`s3-recovery-tasklet.ts`の呼び出し側も追随）
- review.md M-1に対応済みマーク（本番実害の確認内容を含めて追記）

### 確認
- `npx tsc --noEmit` / `npm run build` エラーなし
- **本番の実バケットに対して`fileExists()`を実行し、修正前は一覧取得で見えなかった`UKETSUKE-K010_2026081919510301.csv`が正しく`true`（存在する）と判定されることを確認**。既存の可視ファイル・存在しないファイルについても期待通りの結果を確認

### ステータス
実装・実データ検証完了。PR作成予定。coopcdebatch側の暫定対応（1000→2000件）は別担当が対応するため対象外。

## 2026-09-02 エラーデータ復旧（データタイミング起因）のための準備ロジック検討

### 背景
現在手作業で行っているエラーデータの抽出・再配置の自動化について、新人向けのヒント出しを依頼された。データ抽出自体は既に`ErrorRecordCollector`/`ErrorCsvWriter`により自動化済みであることをまず確認。

### 対象範囲の確定
検討の過程でユーザーが対象を2種類に切り分け：
1. **送信元バグによるデータ誤り**（例: 契約データで連携種別`02`が来るべきでないケースを`91`に修正）: 修正すれば当日中に解消できるため`BATCH_RECOVERY_MODE=true`（`S3RecoveryTasklet`）で臨時対応するもの。発生頻度は稀で、今回のヒント出しの対象外。
2. **データタイミングによるエラー**（例: 速報値データ提出時点でまだ契約データが未登録）: データ自体に誤りはなく、翌営業日以降に契約データが揃ってから通常のSFTPバッチ走行で自然に再処理されれば良いだけ。**データ編集は不要**で、対応が必要なのは以下2点のみ：
   - 文字コード変換（UTF-8→Shift_JIS）
   - パイプラインのファイル種別判定ルールに合致する出力ファイル名の生成
   → エラーCSVの余分な列（`error_reason`、`source_file`）を残したままでも`csv-parser`側の挙動に影響しないことを実データ形式で検証済み（ヘッダーあり/なし双方のCSVで確認）。

### 成果物の位置づけ（重要な認識合わせ）
上記2点のロジックは`scripts/prepare-recovery-file.ts`のコード骨子（チャット上での提示のみ、ファイル未作成）として提示。ユーザーからの確認により、これは**独立した実行スクリプトを私が作成するものではなく**、新人がバッチの最終ステップに組み込む際の実装ヒント（ロジックの骨子）という位置づけであることが判明。組み込み自体（バッチのどのステップにどう実装するか）は新人に一任し、本セッションでのファイル作成・追加対応は不要と判断。

### ステータス
設計ヒントの提示で完了。実装（バッチへの組み込み）は新人が別途対応するため、これ以上のコード対応は行わない。

## 2026-09-04 エラーデータ再処理準備Taskletの参例作成（ブランチ: `feature/prepare-recovery-file-reference`、PR ＃21）

### 経緯
9/2は「実行ソースは新人が作成するので対応不要」と判断したが、スケジュールの都合で参例として別ブランチに作成する方針に変更（マージ前提ではない）。

当初、独立実行スクリプト（`scripts/prepare-recovery-file.ts`、エラーCSVをダウンロードして手元で変換しS3へ再アップロードする方式）として実装したが、ユーザーから「単独走行のスクリプトではなく、現在のバッチ処理の最終ステップにtasklet形式で組み込み、直接untreatedフォルダーに格納したい」との指摘があり、フレームワーク組み込み版に作り直した。

### 実装内容（最終版）
`src/batch/tasklets/prepare-recovery-file-tasklet.ts`を新規作成し、`createMainBatchJob()`（[main-batch-job.ts](src/jobs/main-batch-job.ts)）の最終ステップ`step4_prepareRecoveryFile`として組み込み:
1. Step1〜3で`ErrorRecordCollector`にメモリ上蓄積済みのエラーレコードから、対象理由のみ抽出（S3上のエラーCSVを読み直す必要はない）
2. **対象は速報値（EARLY_BILL）のみ**、理由文字列`契約番号に紐づく契約情報なし`（[early-bill-processor.ts:24](src/batch/processors/early-bill-processor.ts#L24)）に限定。請求情報(BILL)は対象外（ユーザー確認済み）。無条件対象化すると送信元バグ由来のエラーまで無限リトライしてしまうための絞り込み。
3. 元ファイル名（`ErrorRecord.fileName`）ごとにグルーピングし、日時部分のみ新しい日時に差し替えたファイル名を生成（プレフィックスは元ファイル名を引き継ぐため`detectCsvFileType`・`file-type-utils`の日時抽出ロジック双方にそのまま合致）
4. Shift_JISへ変換（`iconv-lite`。`S3CsvReader`の読み込みと逆方向で、コードベース中に前例なし）
5. S3のuntreatedフォルダへアップロード

`SftpDownloadTasklet`・`S3RecoveryTasklet`いずれもuntreatedフォルダの手動配置ファイルを合流させる仕組み（`collectS3WorkingFiles`）を持つため、`BATCH_RECOVERY_MODE`指定不要の次回通常走行で自動的に拾われる。

### 実装過程での認識整理（重要）
1. 実装前、私が誤って「S3のuntreatedフォルダへ直接アップロードしても`BATCH_RECOVERY_MODE=true`で走らせない限り拾われない」と主張したが、これは誤り。実際は`SftpDownloadTasklet`（通常走行）も`collectS3WorkingFiles`経由でuntreatedフォルダの手動配置ファイルを処理対象へ合流させる仕組みを持つ（[sftp-download-tasklet.ts](src/batch/tasklets/sftp-download-tasklet.ts)L68-84、旧バッチ(coopcdebatch)からの移行仕様）。ユーザー指摘により訂正。
2. 当初、独立実行スクリプトとして実装したが、ユーザーの意図は「バッチの最終ステップにtasklet形式で組み込み」だったため作り直し。
3. 対象ファイルタイプについて、当初BILL/EARLY_BILL両方を対象にしていたが、ユーザーより「速報値データのみ対象」と指摘があり、EARLY_BILLのみに修正。

### 確認状況
- `npx tsc`型チェックOK
- ファイル名生成・Shift_JISエンコードの各ロジックはNode単体で動作確認済み（サンドボックスの制約でS3アップロードを含むE2E実行は未実施）

### ステータス
実装・PR更新（Draft）完了。マージ前提ではなく、実運用への組み込み（本番投入時のリトライ上限・エスカレーション等）は新人が別途対応する。
