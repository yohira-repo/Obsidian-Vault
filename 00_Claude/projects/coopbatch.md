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

## 2026-09-08 ローカルSFTP環境（local/sftp/README.md）接続時にパスワードを聞かれる問題の調査

### 症状
`local/sftp/README.md`の手順通り環境構築後、動作確認の`sftp -i ./local/sftp/keys/id_sftp_test -P 2222 sftp-user@localhost`で、鍵のパスフレーズ入力後に`sftp-user@localhost's password:`と聞かれてしまい、公開鍵認証で接続できない。

### 調査の経緯（注意点）
ユーザーの実行環境はWindows（PowerShell、`C:\Users\yohira\git\coopbatch`）だが、本セッションのBashツールはmac（Darwin）側で動いており別環境。当初この違いに気づかず、mac側でコンテナを再作成して検証し「鍵設定は正しいはず」と回答したが、これはユーザーの実機の状態を反映しておらず無意味な検証だった。以降はユーザーに直接コマンド実行・結果貼り付けを依頼する形で切り分けを継続。

- `authorized_keys`とローカルの`.pub`ファイルの中身は完全一致（鍵の取り違え・マウント不具合ではない）
- `docker logs`に`Failed publickey`の記録が一切なく`Failed password`のみ→クライアントが鍵をサーバーに提示できていない
- `ssh-keygen -y -f ...`単体では正しいパスフレーズで復号成功（鍵ファイル自体は壊れていない）
- 最終的にユーザー自身が判明: SFTP接続時のパスフレーズ入力を、値（`coopcde-local-sftp-passphrase`）だと認識せず空Enterで飛ばしていたことが原因。空パスフレーズだと鍵の再試行なしに即座にpassword認証へフォールバックするため、この症状になっていた。

### 結論・対応不要の判断
`README.md`の動作確認セクションには元々「秘密鍵作成時に使用したパスフレーズ（`coopcde-local-sftp-passphrase`）を入力」とコメントで明記されており、ドキュメント自体に不備はなかった（読み落としが原因）。ユーザーより「README.mdをよく読めば読めばわかる話でした」との申し出があり、README修正は不要と判断。追記・修正は行わない。

## 2026-09-08 ローカルLocalStack環境でSecrets Managerが空になる問題の調査（本日中断・明日再開）

### 症状
`local/localstack/README.md`手順に沿って構築したが、`secretsmanager list-secrets`が常に空（`{"SecretList": []}`）で、`assets/`配下に秘密情報ファイルを配置しても解消しない。

### 調査で判明・解決した問題（3つ）
1. **README記載不備**: 「Secrets Manager用ファイルの配置」セクションが`coopcde-sftp-secret.txt`（1ファイル）とだけ書かれているが、実際の`docker-compose.yml`は`coopcde-local-sftp-secret.txt`と`coopcde-local-sftp-passphrase.json`の**2ファイル**（ファイル名も"local"抜けで不一致）を要求している。`git log`確認により、この機能を追加した最初のコミットから存在する長年のバグと判明。README修正は別途相談（未着手）。
2. **`init-aws.sh`のCRLF化**: リポジトリに`.gitattributes`が存在せず、Windows環境でのgitチェックアウト時にシバン行が`#!/bin/bash\r\n`に化け、`[Errno 2] No such file or directory`エラーに。ユーザー側でLF変換して解消。恒久対応として`.gitattributes`追加を提案中（未承認・未着手）。
3. **`Set-Content -Encoding utf8`のBOM付与**: Windows PowerShellの`-Encoding utf8`がUTF-8 BOMを付与し、シバン行破壊で`[Errno 8] Exec format error`に。`-Encoding ascii`に変更して解消。

### 未解決の問題
上記3点を解消後、`init-aws.sh`自体は正常に完走する（`[end] localstack:init-aws`まで到達、エラーなし）が、`secretsmanager list-secrets`は依然として空のまま。コンテナ内で`awslocal`コマンドを直接実行すると`exec /root/.local/bin/awslocal: exec format error`が発生。イメージ・実行環境のアーキテクチャは双方`amd64`で一致しており、イメージを削除して再取得しても再現するため、イメージ破損でもアーキテクチャ不一致でもない。一方、ホスト側からの`aws --endpoint-url=http://localhost:4566 ...`は正常に動作しており、LocalStack本体（APIサーバー）自体は正常。`awslocal`ラッパースクリプト固有の問題と推測し、コンテナ内で素の`aws --endpoint-url=...`コマンド（`awslocal`を介さない）が動作するか検証を依頼した直後に、ユーザーより本日はここで中断する旨の申し出があった。

### 次の一手（再開時にまず試すこと）
1. コンテナ内で`docker exec coopcde_localstack aws --endpoint-url=http://localhost:4566 secretsmanager list-secrets`（`awslocal`を使わない）が動作するか確認
2. 動作すれば、`init-aws.sh`内の`awslocal`呼び出しを`aws --endpoint-url=http://localhost:4566 ...`への書き換えに変更する対応を検討（要承認）

### ステータス
ユーザーより「本作業明日に送ります。本日これ以上、この問題に関わっている時間がありません」との申し出があり、`awslocal` exec format error自体の調査は本日中断・明日以降に持ち越し。

ただし`.gitattributes`追加（改行コードLF強制）についてのみ、ユーザーより「改行コードの件は、PR作成しておいてください」と承認があったため、`fix/add-gitattributes-lf`ブランチで対応しDraft PR #23作成済み。README修正・`init-aws.sh`書き換えは引き続き未承認・未着手。

## 2026-09-09 LocalStackからFlociへの移行を承認・実施（2026-09-08のawslocal未解決問題も解消）

### 背景・承認内容
ユーザーより「LocalStackは有料化されており使いづらい。またSecrets Managerが空振りする件もあり、Flociに変更したい」と相談があり、調査の上で以下を提示・承認を得た。
1. Dockerイメージは`floci/floci:latest-compat`（AWS CLI/boto3同梱、`awslocal`要件を満たす）を採用 → 承認
2. `local/localstack/` → `local/floci/` へディレクトリリネーム、npm scriptsも`localstack:*` → `floci:*`に改名 → 承認
3. review.md指摘済みの`.env.example`不存在・アセット名不一致（Medium項目）も今回まとめて修正 → 承認

### 実施内容・実機検証結果
- `feature/replace-localstack-with-floci`ブランチで対応し、Draft PR [#24](https://github.com/alphacmc/coopbatch/pull/24) 作成済み。
- 実際に`docker compose -f local/floci/docker-compose.yml up -d`でコンテナを起動し、`init-aws.sh`（secretsmanager create-secret ×2、sqs create-queue、s3 mb）が全て成功、`aws --endpoint-url=...`での`list-secrets`/`get-secret-value`/`sqs list-queues`/`s3 ls`も正常に値が返ることを確認済み。
- **2026-09-08に中断した「`awslocal`がLocalStackコンテナ内で`exec format error`を起こし未解決」の問題は、Floci移行により解消したことを実機で確認**（Flociの`latest-compat`イメージに同梱される`awslocal`は正常動作）。あわせて、同日判明していた`init-aws.sh`のCRLF化（シバン行破壊・awslocalの引数崩れ）も今回LF化して修正済み。
- LOCALSTACK_AUTH_TOKENが不要になったため、関連する環境変数・`.env.example`・`.gitignore`/`.cursorignore`の記載も削除。

### 方針変更: 旧`local/localstack/`フォルダは削除せず参照用に残置
上記の初回対応では`git mv`で`local/localstack/`を`local/floci/`へリネーム（旧フォルダは消える形）していたが、ユーザーより「旧localstackのフォルダーはそのまま残してもらえませんでしょうか」と申し出があり、承認の上、以下を追加対応（同PR #24に追加コミット）。
- `local/localstack/`（docker-compose.yml・init-aws.sh・README.md・.env.example）を移行前と同一内容で復元
- `.gitignore`/`.cursorignore`の`local/localstack/`向け除外設定（assets等）も復元
- `local/floci/README.md`に「旧構成は参照用に残置」の一文を追記
- npm scripts（`localstack:*`）・ドキュメント本文の参照先はFloci側のままとし、旧フォルダ向けには復元していない（ユーザーへ確認済み、追加要望があれば対応）

### レビュー指摘への対応・承認事項
ユーザーが`local/floci/docker-compose.yml`をIDEで確認し、以下2点を指摘。
1. 「volumesのマウント先が`/etc/localstack/init/...`のまま残っているのは違和感がある」
2. 「外部から`aws --endpoint-url=http://localhost:4566 secretsmanager list-secrets`での確認を行っているか」

調査の結果、2点とも実際に問題があると判明。
- ②の再検証で、`local/floci/assets/`配下のファイルが存在しない状態だとDockerが黙って空ディレクトリをbind mountし、`init-aws.sh`が`create-secret --secret-string ""`で失敗、`list-secrets`が空振りする（＝当初の「Secrets Managerが空振りする」症状と同一の罠）ことを実機で再現・確認。
- さらに、①の対応（マウント先を`/etc/floci/init/ready.d/`ネイティブパスへ変更）を行った際、`init-aws.sh`内部の`cat`パスを追従修正し忘れると同様に空振りすることも実機で発見。

ユーザーに以下2点を確認し、承認・方針決定：
1. マウント先パスを`/etc/localstack/init/...`から`/etc/floci/init/...`（Flociネイティブパス）へ変更する → **承認**。`docker-compose.yml`・`init-aws.sh`双方を修正し、実機で`list-secrets`/`get-secret-value`等が正常動作することを再検証済み（PR #24に追加コミット `47b9742`）。
2. 「assetsファイルが無いと黙って空振りする」問題への対策（init-aws.sh側でのファイル存在チェック追加等） → **対策不要と判断**。README記載の手順（事前にassetsへファイルを配置）を守る前提でよいとの回答のため、追加対応はしない。

### 検証完了
ユーザーが`local/floci/assets/`配下の2ファイルを実ファイルに配置し直し（サイズ463/65バイト、以前のダミーとは別物と確認）、再検証を実施。`secretsmanager create-secret`×2・`sqs create-queue`・`s3 mb`が成功し、外部からの`aws --endpoint-url=... secretsmanager list-secrets`/`get-secret-value`（バイト長一致を確認、内容自体はチャットに非出力）/`sqs list-queues`/`s3 ls`も全て正常動作を確認。PR #24の内容は実ファイルでの実機検証済みの状態。

## 2026-09-11 `local/db/`配下にPostgreSQL用docker-compose.ymlを新規作成（承認済み設計）

### 背景
`prisma/schema.prisma`（`provider = "postgresql"`）・`src/config.ts`（`DATABASE_URL`または`DB_HOST`/`DB_PORT`/`DB_DATABASE`/`DB_USER`/`DB_PASSWORD`から接続文字列を組み立て）に対応するローカルDBコンテナが`local/`配下に存在しなかったため、`local/floci`・`local/sftp`と同じ体裁で新規追加する依頼があった。

### 設計方針（着手前に3点確認・承認取得）
1. **データ永続化方式**: Docker named volume（`coopcde-db-data`）を採用 → 承認。ただし「ボリューム削除手順もREADME.mdに追加してほしい」との追加要望があり、`docker compose -f local/db/docker-compose.yml down -v`での削除手順をREADMEに明記。
2. **接続情報（ユーザー名/パスワード/DB名/ポート）**: `local/db/.env`で上書き可能にする方式を採用（`${DB_USER:-coopcde}`等のデフォルト値付き変数展開）。
3. **Postgresイメージバージョン**: `postgres:16-alpine`を採用。

### 実施内容
- `local/db/docker-compose.yml`（Postgres 16-alpine、`coopcde_db`コンテナ、named volume `coopcde-db-data`）
- `local/db/README.md`（構築手順・接続情報のカスタマイズ方法・psql/Prisma Studioでの動作確認・ボリューム削除手順・トラブルシューティング）
- `package.json`に`db`/`db:start`/`db:down`スクリプトを追加（`floci`/`sftp`と同じ命名パターン）
- **`.env.example`という名前のファイルはツール側の権限設定（`.env`系ファイルの書き込み拒否ルール）で作成できなかったため、代替として拡張子なしの`local/db/env.example`を作成**（README上で`.env`へのコピー手順を明記）。`.gitignore`/`.cursorignore`は既存の`.env`パターン（拡張子なしの汎用マッチ）でカバー済みのため追加変更なし。

### 未検証事項
このセッションのBashツールから`docker compose --project-directory local/db up -d`を実行したところ、Docker Desktopの名前付きパイプ（`dockerDesktopLinuxEngine`）に接続できず失敗（`docker compose ... config`によるYAML構文検証は成功）。過去の`local/localstack`調査時と同様、Bashツールの実行環境とユーザーの実機Docker Desktopが一致していない可能性があるため、**実際のコンテナ起動・DB接続確認はユーザー側での実施が必要**。

### ステータス
PR #24（`feature/replace-localstack-with-floci`ブランチ、未マージ・Draft解除済み）に追加コミットする形で対応。実機での起動確認待ち。

## 2026-09-18 マージ済み`make-errorfix-csv-tasklet.ts`（`PrepareRecoveryFileTasklet`）のレビュー・修正を承認

### 背景
既にマージ済みの`src/batch/tasklets/make-errorfix-csv-tasklet.ts`（新人による「エラーCSVファイルをuntreatedフォルダーに配置」のtasklet）についてレビュー依頼があった。

### レビュー結果（提示内容）
- **HIGH**: `buildRecoveryFileName`のJSDoc（「日時部分を新しい日時に差し替える」）が実装（`_errorfixNN`連番の付与/インクリメントのみ、`now`引数は完全未使用）と食い違っている
- **HIGH**: マージ済みコードが自プロジェクトのPrettier設定に違反（`npx prettier --check`で実機確認済み: `var`使用・ダブルクオート・セミコロン抜け・`async execute`のインデント崩れ）
- **MEDIUM**: ファイル名`make-errorfix-csv-tasklet.ts`が、export先クラス名`PrepareRecoveryFileTasklet`のkebab-caseと対応しておらず、他tasklet（`file-cleanup-tasklet.ts`→`FileCleanupTasklet`等）の命名規約から外れている（ユーザーから「他のtaskletもconfigクラスをexportしている」との指摘があったが、これはConfig exportの是非の話ではなく、ファイル名とクラス名の1:1対応が崩れている点についての指摘である旨を訂正・再説明し、了承を得た）
- **MEDIUM**: `escape()`が`error-csv-writer.ts`の`escape()`と完全重複（DRY違反）
- **MEDIUM**: `groupBySourceFile`が`fileName`欠落レコードをログなしで握りつぶす（現状の呼び出し経路では実質到達しないが、異常系ログ省略なしの方針に反する）
- **MEDIUM**: ユニットテスト0件
- **LOW**: `_errorfixNN`連番が2桁（99）を超えると命名がずれる（コメントで既知の制約と明記済み）

### 承認内容
ユーザーより「全部まとめてfix/ブランチで修正しPR作成」と承認あり。

### 実施内容（`fix/prepare-recovery-file-tasklet-review`ブランチ、PR作成予定）
- ファイルを`prepare-recovery-file-tasklet.ts`にリネーム（`main-batch-job.ts`のimportパスも追従修正）
- `buildRecoveryFileName`から未使用の`now`引数を削除し、JSDocを実装（`_errorfixNN`連番付与）に合わせて修正
- `var`→`const`、ダブルクオート→シングルクオート、セミコロン付与、インデント修正（`npx prettier --write`適用）
- CSVエスケープ処理を`src/utils/csv-utils.ts`の`CsvUtils.escapeField`に切り出し、`error-csv-writer.ts`と本tasklet双方で共通化
- `groupBySourceFile`で`fileName`欠落レコードをスキップする際に`logger.warn`を追加
- `_errorfixNN`連番が`MAX_ERRORFIX_SEQUENCE`（99）を超える場合に`logger.warn`を追加
- 修正前後でファイル名生成ロジックの入出力が完全一致することをNode.jsで実機検証済み
- `npx tsc --noEmit`エラーなし、touchedファイルは`npx prettier --check`通過を確認

### 未対応（別途相談が必要と判断・今回のスコープ外）
ユニットテスト0件の指摘について、調査の結果**プロジェクト全体にテストフレームワークが一切導入されていない**（jest/vitest等なし、`package.json`に`test`スクリプトもなし）ことが判明。フレームワーク導入はプロジェクト全体に関わる設計判断のため、今回の`fix/`ブランチのスコープには含めず、別途ユーザーに相談する。

### ステータス
PR #26は2026-09-24にマージ済み（ユーザー報告・`gh pr view`で確認）。テストフレームワーク導入の要否は上記の通り未相談のまま残っている。

## 2026-10-05 Step4（PrepareRecoveryFileTasklet）追加に伴う、errors/・temporary振り分けの設計相談・決定

### 背景・相談内容
Step4追加後、以下2点の運用上の論点についてユーザーから相談があった。
1. `untreated/errors/`配下に残るエラーCSV（Step2完了時に`ErrorCsvWriter`が書き出す全エラーの監査ダンプ）について、Step4が再投入ファイル（`_errorfixNN.csv`）を`untreated/`直下に作成した際、`errors/`配下のデータをどうすべきか（「残しておくと後で悪さしそう」という懸念）
2. エラー発生したCSVファイルは`temporary/`に置かれるが、どのタイミングで`treated/`へ移すべきか（現状は元ファイルが`temporary/`に入ったきり永久に残り、`_errorfixNN`という別ファイルがtreatedに着地しても元ファイルとは紐付かない）

### 提示した選択肢
- ①: A.丸ごと削除／B.再投入対象の行だけ除いて書き直す／C.再投入対象reasonはそもそも`errors/`に書かない
- ②: A.現状維持（元ファイルは`temporary`に永久保持）／B.元ファイルの全エラーが再投入対象reasonだった場合のみ`temporary→treated`へ自動移動／C.`_errorfixNN`の最終成功と連動して親子関係ごと移動

### 決定
- **①B採用**: `errors/`CSVは再投入した行（reason=`契約番号に紐づく契約情報なし`）だけを除いて書き直す（他reasonの行が残っていれば保持、空になれば削除）。理由: 「Cだと複数のステップに手が入ることになり、Step4は独立させておきたい（今後の拡張性を考慮）」とのこと。
- **②B採用**: 元ファイルの全エラーが再投入対象reasonだった場合のみ、Step4が`temporary→treated`へ自動移動する。それ以外（他reasonのエラーが混在）の元ファイルは、解決した時点で人手による移動とする。

### 実装方針（着手前メモ）
- `context`に`errorCsvKeys`（Step2のafterStepフックが書き込んだ`errors/`CSVのS3キー）を追加し、Step4がそのキーを参照できるようにする（`main.ts`/`worker.ts`/`main-batch-context.ts`を変更）
- `PrepareRecoveryFileTasklet`に`s3SuccessPrefix`（treated）を追加配線し、ソースファイル単位で「全エラーが再投入対象reasonか」を`earlyBillErrorCollector.countForFile()`と比較して判定し、該当すれば`temporary→treated`へ移動
- `errors/`CSVの再書き込みは、S3からの再パースではなく、メモリ上の`earlyBillErrorCollector.getRecords()`から非該当reasonのみ抽出し`ErrorCsvWriter`で書き直す方式とする（CSV再パースの脆さを避ける）

### 運用プロセスに関するフィードバック
ユーザーより「相談時点でconversations.mdに記載してほしい。すぐに結論が出ないケースもある」との指摘があり、今後は結論を待たずに相談があった時点で記録する運用に変更（`~/.claude`配下のメモリに保存済み: `record-conversations-at-consultation-time`）。

### 実装・ステータス
`feature/step4-errors-cleanup-and-treated-promotion`ブランチで実装し、Draft PR [#27](https://github.com/alphacmc/coopbatch/pull/27)を作成済み。`npx tsc --noEmit`エラーなし、分岐ロジックはNode.jsで簡易シミュレーションし期待通りの挙動を確認。マージ・Draft解除はユーザー側で実施予定。

### リリース・試験予定
PR #27は2026-10-05にマージ済み（ユーザー報告・`gh pr view`で確認）。同日、ステージング環境へリリース実施。**試験は翌日（2026-10-06）に実施予定**。

## 2026-10-13 Step4（PrepareRecoveryFileTasklet / PR ＃27）の本番リリース完了

### 経緯
2026-10-05の設計決定（`errors/`CSVの再投入行除去＝①B、全エラーが再投入対象reasonの場合のみ`temporary→treated`自動移動＝②B）に基づき実装したPR [#27](https://github.com/alphacmc/coopbatch/pull/27)について、ステージングリリース（2026-10-05）後の一連の作業が完了した。

### 結果
- **2026-10-06 の試験: 問題なし（合格）**（ユーザー報告）
- **本番環境へのリリース完了**（ユーザー報告）

これにより、2026-10-05に起票したStep4追加に伴う`errors/`・`temporary`振り分けの対応は一連完了とする。

## 2026-10-20 coop からの申し送り: 会話記録を日付別ファイルへ切り替え

### 申し送り内容（INBOX_FROM_COOP.md より取り込み）
coop で、alphasystem 配下で決まった運用規則を coop 系にも適用することが決定（詳細: coop の `conversations/2026-10-20.md`「alphasystem の運用規則を coop 系に適用」、`coop/CLAUDE.md`）。coopbatch への依頼は以下。

1. リポジトリ直下に `conversations/` ディレクトリと `README.md` を作る（ひな形: `coop/conversations/README.md`）。
2. 今後の記録は `conversations/YYYY-MM-DD.md` に書く（見出しは `## YYYY-MM-DD タイトル` のまま）。
3. 既存の `conversations.md` は過去分のアーカイブとして残し、**追記しない**。
4. 通常の規約でブランチを作り Draft PR にする（base は main。staging は無い）。Stop フックは全リポジトリ共通なので、`conversations/` を作れば書き先が自動で切り替わる。

あわせて決まったこと（参考）:
- 設計の決定は coop に、実装計画以降のやり取りは各プロジェクトに記録する。結合試験は coop（設計者）が担当する。
- セッション間の連携は SendMessage を使う。相手が未起動なら、相手リポジトリ直下に未追跡の `INBOX_FROM_<送り元>.md` を置く。
- ブランチ運用（main/staging の 2 本立て）は coop 系では採用しない（従来どおり main をベースにする）。

### 対応
- `conversations/README.md`（coop のひな形に準拠）と本ファイルを作成。
- 既存の `conversations.md` は coop と同様に無変更のままアーカイブとして残す（以降は追記しない。README に明記）。
- 取り込み後、`INBOX_FROM_COOP.md` を削除。

## 2026-10-23 Node.js・Prisma 等のバージョンアップ方針（承認済み）

### 背景
ユーザーから「Node.js・Nest.js・Prisma などのバージョンアップを行いたい」と依頼。

### 調査結果
- **coopbatch は Nest.js を使っていない**。Nest.js を使っているのは coopcdebatch（Nest 9 / Prisma 4 / Node 18）・coopcdealert（Nest 9）・coopcdeinput（Nest 10 / Prisma 5 / Node 18）。
- coopbatch は Node 20（`Dockerfile` の `node:20-alpine`）で、**2026-04 に EOL 済み**。
- coop の `conversations/2026-10-22.md` では、統一先は「おそらく Node 24、最終決定は coop」、coopbatch はインターネット非公開のため「後日対応」、定期的なバージョンアップのスケジュールは coop で組む（未定）とされている。
- 依存ライブラリ（`npm outdated`、2026-10-23 時点）:
  - Prisma 5.22 → 最新 7.10。7 は DB 接続方式が変わる大きな変更（schema の url を `prisma.config.ts` へ移し、`@prisma/adapter-pg` を導入）。6 は小さな変更で済む。
  - AWS SDK / pino / pino-pretty / prettier / iconv-lite は互換性を壊さない範囲の更新のみ。
  - ssh2-sftp-client 10 → 12（Node >=18.20.4）、dotenv 17 → 18、TypeScript 5.9 → 7（Go 版）。
  - dotenv-expand 13 → **1000.0.0**（2026-07 に突然出た不自然な番号）。中身を確認するまでは上げない。
  - `npm audit --omit=dev`: csv-parse に moderate が1件（GHSA-8cw4-87c7-c6xx）。ただし **csv-parse はコードから使われていない**（使っているのは csv-parser）。

### 決定事項（ユーザー承認）
1. **対象は coopbatch のみ**。Nest.js を使う側（coopcdebatch 等）は今回扱わない。
2. **Node は 24 で今すぐ進める**（coopcdeweb と同じ `node:24-alpine3.24`）。coop での正式決定前だが先行して対応し、coop には事後に申し送る。
3. **Prisma は 6 に上げ、7 は別 PR** に切り出す。

### 実施方針
- ブランチ `feature/upgrade-node24-prisma6`、Draft PR #30（base は main）。
- コミットを分ける: (a) Node 24 化（Dockerfile、@types/node 24 系）と互換性を壊さない更新、使っていない csv-parse の削除 (b) Prisma 6 化。
- 今回見送るもの: Prisma 7、TypeScript 7、dotenv-expand 1000.0.0。ssh2-sftp-client 12・dotenv 18 は変更内容を確認してから判断する。
- 確認: `npm run build`、ローカル DB・floci での動作確認、Docker イメージのビルド。その後、stg での確認はユーザーが実施。

### 実施結果
- コミット (a) `29bd9d3`: Dockerfile を `node:24-alpine3.24` へ、@types/node を 24 系へ、未使用の csv-parse を削除、`npm update` で互換範囲の更新。
- コミット (b): Prisma / @prisma/client を 5.22.0 → 6.19.3。schema に Bytes 型・多対多リレーション・予約語のモデル名が無いことを確認しており、Prisma 6 の互換性を壊す変更の影響は無い。
- 据え置いたもの:
  - ssh2-sftp-client は 10 系のまま。12.0.0 で接続失敗時の自動リトライが削除されており（v10 は既定で再接続あり）、異常時の挙動が変わるため。
  - dotenv は 17 系のまま。dotenv-expand 13 が dotenv ^17 を前提にしているため。
- 確認したこと（2026-10-23、ローカル）:
  - `npm run build` 成功。`docker build` 成功（イメージ内は Node v24.22.1、@prisma/client 6.19.3、エンジンは `linux-musl-openssl-3.0.x` を同梱）。
  - ローカル DB（`local/db`、Postgres 16）に対し、イメージ内から Prisma 6 で Contract の create / update / findUnique / `$transaction` 経由の delete を実行し、Decimal・DateTime も含めて正常に動くことを確認。
- 残っている注意点:
  - Prisma 6 の CLI が依存する deepmerge-ts に high の脆弱性（GHSA-ggr8-5vv4-36mx）。prisma CLI は @prisma/client の任意の peer 依存として `npm ci --omit=dev` でも本番イメージに入る（main の Prisma 5 でも同じ構造）。CLI の設定処理でしか使われないため実行時の影響は無い。Prisma 7.10.1 で解消されるので、Prisma 7 の PR で対応する。
  - `prisma/migrations` には `users` テーブルを作る `20240101000000_init` しか無く、今の schema（contract 等）と食い違っている（今回の変更とは無関係の既存の問題）。動作確認では、ローカル DB にだけ `prisma db push` で今の schema を反映した。
- 未実施: SFTP・floci を含めたバッチ全体の実行、stg での確認（ユーザーが実施）。

## 2026-10-23 PR ＃30 の残課題への回答と、stg 確認の段取り

### 決定事項（ユーザー回答）
1. **deepmerge-ts の脆弱性（prisma CLI 経由）は Prisma 7 の PR で対応する** → OK（承認）。PR #30 では対応しない。
2. **`prisma/migrations` と schema の食い違いは考えなくてよい**（対応しない）。
3. **次の作業は stg での確認**。coop への申し送り（Node 24 化）と Prisma 7 の PR はその後。

### stg 反映前の注意（調査結果）
- ECR リポジトリ `coop-batch` は stg・prd で共用（`cf/ecr-cf.yaml` はアカウントに1回だけデプロイ）で、`ImageTagMutability: MUTABLE`。
- buildspec はイメージタグを package.json の version から決める。PR #30 時点の version は 1.0.2（prd で稼働中のタグ）。
- **version を上げずにビルドすると prd の `coop-batch:1.0.2` が Node 24 版で上書きされ、stg 確認前に prd の次回実行が新イメージで動いてしまう**。stg 用のビルド前に必ず version を上げる。
- **version は 1.1.0 にして PR #30 に含める**（ユーザー承認）。実行環境が変わる（Node 24・Prisma 6）ためマイナーを上げる。stg のイメージタグは `coop-batch:1.1.0` になり、prd の 1.0.2 は上書きされない。

### stg 確認の段取り（実行順。日時は未定、実施はユーザー）
1. stg の CodeBuild（`coopcde-stg-batch-codebuild`）を実行する。既定では main を取ってくるので、マージ前に試すなら `--source-version feature/upgrade-node24-prisma6` を付ける。ログの `Resolved IMAGE_TAG ... -> 1.1.0` と ECR の `coop-batch:1.1.0` を確認する。
2. stg の ecs-batch stack を ImageTag `1.1.0` で更新する（prd の stack は 1.0.2 のまま）。
3. ecs-batch-ondemand か定期実行でバッチを動かす。
4. CloudWatch Logs で確認する: Prisma エンジンの読み込みエラー（libssl / openssl）が無いこと、`SFTP connected to ...` からダウンロードまで進むこと、S3・SQS・DB の処理がこれまでどおり終わること、終了コード 0。

## 2026-10-23 PR ＃30（Node 24 / Prisma 6、version 1.1.0）マージ

- PR #30 をユーザーがマージ（2026-10-23 15:58 JST、マージコミット `8d486fb`）。main の version は 1.1.0。
- stg の CodeBuild は main を取ってくるので、`--source-version` の指定は不要になった。以降は「stg 確認の段取り」の 1〜4 をユーザーが実施する（日時は未定）。
- stg 確認の後に残っている作業: coop への申し送り（coopbatch を Node 24 に先行して更新したこと）、Prisma 7 の PR（deepmerge-ts の脆弱性の解消を含む）、prd への反映。

## 2026-10-23 coopcdeweb から共有: Prisma 6 のサポート終了と Prisma 7 対応のノウハウ

- **受信**: coopcdeweb のセッション（coopcdeweb-0b）から `SendMessage` で共有（ユーザーの依頼による）。詳細は coopcdeweb の `conversations/2026-10-22.md`・`2026-10-23.md`。coopcdeweb は Prisma 7 対応を 1.8.0 として着手中で、終わったら結果を追送してくれる。
- **Prisma 6 は 2026-11-19 でサポート終了**（公式 https://www.prisma.io/docs/orm/release-status）。coopbatch は PR #30 で 6.19.3 にしたばかりなので、**Prisma 7 対応が必要**。時期・進め方は下の「Prisma 7 対応の進め方」のとおり承認済み。

### Prisma 7 で必要になること（coopcdeweb が公式の upgrade ガイドと手元での生成で確認）
- Node 20.19 以上、**TypeScript 5.4 以上**。coopbatch は実体が 5.9.3 で満たしているが、package.json の範囲が `^5.3.0` なので `^5.4` 以上に上げる。
- generator は `prisma-client-js`（非推奨）から `provider = "prisma-client"` へ。**`output` が必須**（node_modules の外に生成）で、import 先を生成先に変える。
- **`moduleFormat = "cjs"` で CommonJS のまま生成できる**（ESM 化は必須ではない）。生成物は client.ts / browser.ts / enums.ts / models/ などの TS ソース。
- `prisma generate --generator <名前>`・`--config <path>` が使える（1 つのスキーマに複数の generator を書いて、選んで生成できる）。
- **ドライバーアダプターが必須**: `@prisma/adapter-pg` の `PrismaPg` を `new PrismaClient({ adapter })` に渡す。コンストラクタ引数の `datasources` / `datasourceUrl` は廃止。
- **接続タイムアウトの既定が変わる**（v6 は 5 秒、pg は既定で無制限）。`connectionTimeoutMillis` を明示する。
- スキーマの `datasource.url` は非推奨で、`prisma.config.ts`（`defineConfig`）へ移す。**`.env` は自動で読まれない**（coopbatch は `src/config.ts` で dotenv を読んでいるが、CLI 用に prisma.config.ts 側でも読み込みが必要）。
- CLI: `db push` / `migrate dev` の `--skip-generate` は廃止、`migrate dev` は自動で seed しない、`db execute` の `--schema` / `--url` は廃止。
- Rust のエンジンが無くなるので、**`binaryTargets` と Dockerfile の `apk add openssl`（OpenSSL 判定の回避策）は不要になる**。
- 廃止: `$use`（middleware）は `$extends` へ。metrics も廃止。

### SSL（重要）
- stg の Aurora（15.15、`rds.force_ssl=0`）で `pg_stat_ssl` を見たところ、**Prisma 6（Rust エンジン）の接続は TLS 1.3 で暗号化されていた**（証明書の検証はしていない見込み）。
- **pg ドライバーは指定しないと暗号化しない**ので、そのまま Prisma 7 にすると平文に下がる。coopcdeweb では RDS の CA 証明書を入れて、検証付きで暗号化する方針。**Aurora の CA は `rds-ca-ecc384-g1`**（stg・prd とも）。
- coopbatch の `src/` には SSL の指定が無い（2026-10-23 に grep で確認）。今は Rust エンジンの既定に任せて暗号化されている状態とみられる。DB は coopcdebatch・coopinf と共用（`cf/ecs-batch-cf.yaml` のコメント）なので、同じ Aurora の CA が使える見込み。

### Node 24 / npm 11 まわり（coopcdeweb で踏んだもの）
- Node 24 に同梱の **npm 11 は、インストール時のスクリプト（postinstall 等）を既定で実行しない**。そのため `@prisma/client` の postinstall による自動生成が起きない。`prisma generate` は明示的に実行する必要がある（coopbatch の Dockerfile は明示済みなので問題ない）。
  - coopbatch でも PR #30 の作業中に `npm warn allow-scripts` が出ており、ssh2・cpu-features のネイティブビルドも実行されていない。どちらも任意のネイティブ高速化で、無くても JS 実装で動く。Docker イメージでの DB 接続・CRUD は確認済み。SFTP は stg で確認する。
- push 前に **node:24 のコンテナで CI と同じ手順（install → generate → lint → build → test）を流す**と、Docker ビルドだけでは見つからない失敗を事前に拾える（coopbatch には lint / test が無いので、generate → build が該当）。
- `eslint-plugin-prettier` 4 は prettier 3 で動かない（`resolveConfig.sync` が無い）ので 5 系にする（coopbatch は ESLint 未導入なので該当なし）。
- `npm audit fix` が依存の下に別のメジャーを入れて、二重に読み込まれることがある（coopcdeweb では @typescript-eslint の v5 と v8 が二重になり ESLint が停止）。
- CloudFormation で ECS サービスのスタックを更新すると、タスク数がテンプレートのパラメータ値に戻る（coopbatch は EventBridge からの RunTask で常駐サービスではないので、直接は該当しない）。

### Prisma 7 対応の進め方（Claude の提案 → ユーザー承認済み）
- 順序: stg で 1.1.0（Node 24 / Prisma 6）の確認が終わってから着手し、2026-11-19（Prisma 6 のサポート終了）より前に prd へ反映する。
- 中身: `moduleFormat = "cjs"` で CommonJS のまま生成、`@prisma/adapter-pg` で接続、SSL は Aurora の CA（`rds-ca-ecc384-g1`）で検証付きの暗号化、`connectionTimeoutMillis` を明示、`binaryTargets` と `apk add openssl` を削除、typescript の範囲を `^5.4` 以上へ。
- 着手は、coopcdeweb からの Prisma 7 対応結果の追送を待ってからにする案。
- **2026-10-23 ユーザー承認**（「進め方問題ありません」）。この順序と中身で進める。次の起点は、stg での 1.1.0 確認の結果と、coopcdeweb からの Prisma 7 対応結果の追送。

## 2026-10-26 coopcdeweb から追送: Prisma 7 対応の結果（stg で確認済み）

- **受信**: coopcdeweb のセッション（coopcdeweb-0b）から `SendMessage` で追送（2026-10-23 のノウハウ共有の続き）。詳細は coopcdeweb の `conversations/2026-10-24.md`、PR alphacmc/coopcdeweb#125。
- **coopcdeweb の状況**: Prisma 7 対応（1.8.0、prisma / @prisma/client / @prisma/adapter-pg 7.10.1）を stg で動作確認まで完了。
- 承認済みの進め方（2026-10-23）では、この追送を待って coopbatch の Prisma 7 対応に着手する。残る前提は、stg での 1.1.0（Node 24 / Prisma 6）の確認（実施はユーザー）。

### 構成
- generator `prisma-client` を 2 つ（1 つのスキーマから frontend 用と backend 用を生成）。backend 用は `moduleFormat = "cjs"` で CommonJS のまま（NestJS は書き換え不要）。`prisma generate --config <prisma.config.ts> --generator <名前>` で個別に生成。
- 生成物は TS ソース（`src/generated/prisma` 配下）。アプリのビルド（tsc）で dist に入るので、**実行用イメージでの `prisma generate` も `apk add openssl` も不要**になった（エンジンが無いため）。生成物は .gitignore に入れ、lint の対象からも外す（`ignorePatterns`）。
- `prisma.config.ts` の `datasource.url` は `process.env.DATABASE_URL ?? ''` にしておくと、DB に接続しない generate でも落ちない。

### DB 接続（PrismaPg）
- `new PrismaClient({ adapter: new PrismaPg({ host, port, user, password, database, connectionTimeoutMillis: 5000, ssl }) })`。項目ごとに渡せば、パスワードの URL エスケープは不要。
- **SSL**: stg・prd は `ssl: { ca: <RDS の CA 証明書束>, rejectUnauthorized: true }`、local は `false`。CA 束は https://truststore.pki.rds.amazonaws.com/ap-northeast-1/ap-northeast-1-bundle.pem（Root CA ECC384 G1 を含み、Aurora の `rds-ca-ecc384-g1` に対応）。coopcdeweb では `.gitignore` の `*.pem` に例外を足す必要があった。
- stg で `pg_stat_ssl` を確認し、1.8.0 の接続は TLS 1.3（`ssl=t`）。SSL に対応していない DB には「The server does not support SSL connections」で接続を拒み、平文に落ちないことも手元で確認済み。
- pg の Pool は、使っていない接続を既定 10 秒で閉じる。`pg_stat_ssl` で確認するときは、処理を流しながら見ないと接続が見えない。

### つまずいた点
- adapter なしの `new PrismaClient()` は Prisma 7 では作れない（coopcdeweb では、使っていない provider に残っていたので削除）。
- `Decimal` は `@prisma/client/runtime/library` からではなく、生成物の `Prisma.Decimal` を使う。
- Next.js（Turbopack）で生成物を読むと `import './enums.js'` が解決できないため、generator に `importFileExtension = ""` を指定（バッチは Next を使わないので関係ない見込み）。
- TypeScript は 5.4 以上が必須（coopcdeweb は 5.9.3）。
- `prisma db push` の `--skip-generate` は廃止（付けるとエラーになる）。
- 参考: 停止した旧タスク（Prisma 6 のエンジン）の接続が DB 側に idle で残っていた（いずれ切れる見込み）。

### coopbatch に当てはめた場合（2026-10-26 に確認）
- `src/db.ts:10-11` が `new PrismaClient({ datasources: { db: { url: config.database.url } } })`。**`datasources` は Prisma 7 で廃止**なので、PrismaPg の adapter に置き換える。`src/config.ts` は `DB_HOST` 等の個別の値を持っているので、項目ごとに渡す方式にできる。
- `Prisma.Decimal` は `src/batch/master-data-cache.ts` で生成物の `Prisma` 経由で使っており、`runtime/library` からの import は無い。import 先を生成物に変えるだけで済む見込み。
- `.gitignore` に `*.pem` は無いので、CA 束を置いても除外されない（例外の追加は不要）。
- `$use`・`--skip-generate` の使用は無い（`src`・`package.json`・`Dockerfile`・`README.md`・`local` を grep）。
- generator は 1 つ（バッチ用）で足りる。生成物の置き場所は `src/generated/prisma` にそろえ、.gitignore に追加する。Dockerfile の実行ステージから `apk add openssl` と `.prisma` の COPY を外せる。

## 2026-10-26 coopcdeweb から情報連携: 電気の単価表示の修正（1.8.1）と、denki_bill のデータの形

- **受信**: coopcdeweb のセッション（coopcdeweb-0b）から `SendMessage` で共有（ユーザーの依頼による）。詳細は coopcdeweb の `conversations/2026-10-26.md`、PR alphacmc/coopcdeweb#129（単価の修正）。

### coopcdeweb の現状
- prd: 1.7.0（Node 24、Next 16、NestJS 11、Prisma 6）。
- stg: 1.8.1（1.8.0 の Prisma 7 ＋ 単価の修正）。1.8.0 は prd に出さない決定。1.8.1 の prd 反映時期は未定（改定後の単価は 2027-01 請求から表示されるので、12 月中が目安。1.8.1 を出せば Prisma 6 のサポート終了〔2026-11-19〕も解消する）。
- GitHub に 1.4.0〜1.8.0 のタグを付けた（1.4.1 以降は CodeBuild が実際にビルドしたコミット）。

### 単価の修正（coopcdeweb 1.8.1）
- 単価（電気単価 1・2・3、再エネ賦課金）は **web の表示だけ**の値（coopcdeweb の `apps/backend/src/members/members.const.ts` の表）。DB・CSV に単価の項目は無く、**coopbatch の取り込みには影響しない**（coopbatch の対応は不要）。
- 新単価: 2026-11-01 実施の料金改定（https://energy.coopdeli.coop/mirai/denki_news/4100/ ）。12 月検針分・2027-01 請求から、第 1 段階 29.90→29.95、第 2 段階 36.50→36.55、第 3 段階 40.19→40.24 円/kWh。
- バグ: 「11 月中に解約した場合は、12 月検針分（1 月請求）でも見直し前の単価」への配慮が無かった。単価を「請求年月 − 1」で選んでいたため。→ **使用期間の終了日（usage_end_date）の年月**で選ぶように変更した。再エネ賦課金（5 月検針分から切り替え）で 4 月中に廃止したケースも同様に直った。

### denki_bill のデータの形（stg、約 232 万件、2023-11〜2026-10 請求を読み取りのみで集計）
- **meter_read_date ＝ usage_end_date ＋ 1 日**（全件、例外なし）。
- 請求年月 − 検針年月 ＝ 1 が 99.8%。ずれる行（約 4,800 件）は、大半が**契約の最後の請求（廃止）**で、使用日数が短く月の途中で終わる。
- **検針日が 1 日の請求（1,178 件）はすべて最後の請求**（月末の廃止。usage_end_date が月末、meter_read_date が翌月 1 日）。通常の請求で検針日が 1 日のものは無い。
- 請求年月 − 使用終了月 ≥ 2 で、その後にも請求が続く行が 57 件（遅れて請求されたもの）。
- CSV の「料金年月」列は取り込んでいない（web の画面の月は請求年月 − 1）。coopbatch の `denki_bill` には `usage_end_date`・`meter_read_date`（どちらも VarChar(8)）があり、上の判定に使える。

### 調査で踏んだこと（stg の DB を調べるとき）
- stg の DB へは coop-stg-manage から SSM で、`PGOPTIONS="-c default_transaction_read_only=on"` を付けて読み取りのみで接続（一時ビューの作成も拒否される）。
- 契約ごとに「後の請求があるか」を相関サブクエリで数えると、232 万件で 9 分以上かかった。SSM を取り消し、DB 側も `pg_cancel_backend` で取り消した。ウィンドウ関数（`max(...) over (partition by member_code, contract_number)`）で書き直すと数十秒。
- SSM の AWS-RunShellScript では、SQL の `$re$` などのドル記号がシェルに展開される。SQL を base64 で送ってファイルにし、`psql -f` で実行する。

## 2026-10-26 stg での 1.1.0（Node 24 / Prisma 6）の確認

### 状態（AWS で読み取りのみで確認）
- ECR `coop-batch:1.1.0` は 2026-10-23 16:26 JST に push 済み。`coop-ecs-batch-stg` は 2026-10-23 16:28 JST に ImageTag 1.1.0 で更新済み（タスク定義 `coop-stg-batch:4`）。prd（`coop-ecs-batch-prd`）は 1.0.2 のまま。
- stg の定期実行 `coop-stg-batch-schedule` は DISABLED。最後の実行は 2026-10-11（1.0.2）で、**1.1.0 はまだ一度も実行されていない**。
- stg の Aurora `coopcde-stg-db-cluster` は available。

### 決定（ユーザー承認）
- **Claude がオンデマンドの Step Functions `coop-stg-batch-ondemand` を起動して確認する**。順序は (1) `{"sftpCheckOnly": "true"}` で SFTP の接続と一覧だけを確認（ダウンロード・DB・S3 には触れない）→ (2) 問題が無ければ通常の実行（stg の SFTP のファイルを stg の DB・S3 に取り込む）。結果は CloudWatch Logs `/ecs/logs/coop-stg-batch-loggroup` で確認する。
- その後、Prisma 7 の変更案をまとめてユーザーに提示する（着手は了承を得てから）。
- (1) の `sftpCheckOnly` 実行を 2026-10-26 16:56 JST に起動（実行名 `b461399c-baf9-474c-a09f-ac0e1b468c65`）。結果は確認後に追記する。
- (1) の結果: **SUCCEEDED**（16:56:58〜16:56:59 UTC+9）。ログに `Version: 1.1.0`、`SFTP connected to 10.16.20.94:50022`、一覧は `/OUT/AGREEMENT` に `IF-P046_2026100307001801.csv` が 1 件、`/OUT/INVOICE`・`/OUT/EARLY` は 0 件、`completed successfully`。Node 24 での起動と、ssh2（npm 11 でネイティブ部品が未ビルド）での SFTP 接続に問題なし。
- (2) の通常の実行を 2026-10-26 16:57 JST に起動（実行名 `e9723540-bc3f-4ca9-8cf5-c8c58d27a0ee`）。結果は確認後に追記する。
- (2) の結果: **SUCCEEDED**（16:58:10〜16:59:04 JST、約 54 秒）。`Database connected successfully`（Prisma 6 で stg の Aurora に接続）、SFTP から `IF-P046_2026100307001801.csv` をダウンロードして S3 `untreated/` へ、契約マスタ 107,778 件を読み込み、**EARLY_BILL を Read 3,737 / Write 3,737 / Errors 0** で登録・更新、ファイルを `treated/` へ移動、`Total Errors: 0`、`Main Batch Job (one-shot) completed successfully`。WARN 以上のログは 0 件。
- **stg での 1.1.0（Node 24 / Prisma 6）の確認は完了**（問題なし）。prd への反映（`coop-ecs-batch-prd` の ImageTag を 1.0.2 → 1.1.0）はユーザーが判断・実施する。

## 2026-10-26 Prisma 7 対応の変更案（version 1.2.0）を承認

### 決定（ユーザー承認）
- 以下の変更案で着手する。**SSL は A 案**（既定で CA 証明書による検証付きの暗号化。ローカルだけ `.env` に `DB_SSL=false` で外す。CloudFormation の変更は不要）。B 案（既定は無効、stg・prd の CloudFormation に `DB_SSL=true`）は、書き忘れると平文の接続が黙って通るので採らない。

### 変更案
- package.json: prisma / @prisma/client を 7.10.1、@prisma/adapter-pg 7.10.1 を追加、typescript を `^5.9.0`。version を 1.2.0。
- prisma/schema.prisma: generator を `prisma-client`（`output = "../src/generated/prisma"`、`moduleFormat = "cjs"`）。`binaryTargets` と datasource の `url` を削除。
- prisma.config.ts（新規）: `import 'dotenv/config'`、`datasource.url` は `process.env.DATABASE_URL ?? ''`。
- src/db.ts: `datasources` をやめて `new PrismaPg({...})` を adapter に渡す。`connectionTimeoutMillis: 5000`（Prisma 6 の既定と同じ）。
- src/config.ts: 接続先を項目のまま持つ（パスワードの URL エスケープが不要になる）。ローカルで `DATABASE_URL` を指定したときはそれを使う。SSL の設定を追加。
- `Prisma` を import している 8 ファイル: import 先を生成物（`generated/prisma/client`）へ。
- certs/（新規）: RDS の CA 証明書束（ap-northeast-1-bundle.pem）。
- Dockerfile: ビルドステージで generate → build。実行ステージから `apk add openssl` と `.prisma` の COPY を外し、CA 証明書をコピー。
- .gitignore: `src/generated/` を追加。

### 確認方法
- ローカル: Docker イメージのビルド、ローカル DB での CRUD。SSL を有効にしたまま SSL 非対応のローカル DB に接続し、平文に落ちずに拒否されることを確認。
- stg: `sftpCheckOnly` → 通常の実行。`pg_stat_ssl` で暗号化を確認（coop-stg-manage から読み取りのみ）。
- 期限: Prisma 6 のサポート終了（2026-11-19）より前に prd に出せるようにする。

### 実施（ブランチ `feature/upgrade-prisma7`）
- 変更案のとおり実装。version 1.2.0。CA 証明書束は https://truststore.pki.rds.amazonaws.com/ap-northeast-1/ap-northeast-1-bundle.pem から取得して `certs/rds-ap-northeast-1-bundle.pem` に置いた（Root CA RSA2048 / RSA4096 / ECC384 G1 の 3 つ。stg・prd の DB インスタンスはすべて `rds-ca-ecc384-g1` であることを AWS で確認）。
- **変更案からの追加（挙動を保つため）**: ドライバーアダプター経由では `$connect()` の時点で DB に接続しないため、接続できなくても `Database connected successfully` が出てしまう。Prisma 6 と同じく `connect()` の時点で接続の失敗を検知するよう、`src/db.ts` の `connect()` で `SELECT 1` を実行するようにした。
- `.env.example` は権限設定（`.env` 系のファイルの読み書き拒否）で編集できないため、`DB_SSL=false` の説明は `local/db/README.md` に書いた。**`.env.example` への `DB_SSL=false` の追記と、各自のルートの `.env` への追記はユーザー側で必要**。
- `.dockerignore` に `src/generated` を追加（ビルドステージで生成し直すため）。

### ローカルでの確認（2026-10-26）
- `npm run build`・`docker build` 成功。
- イメージ内のアプリ本体（`dist/db.js`）でローカル DB に接続し、Contract の create / interactive `$transaction` 内の update / findUnique / delete を確認（Decimal・DateTime も正しい）。項目ごとの接続（ECS と同じ）と `DATABASE_URL` の両方で確認。
- SSL が既定で有効なまま SSL 非対応のローカル DB に接続すると、`connect()` で「The server does not support SSL connections」により `Database connection failed`、終了コード 1（平文に落ちない）。
- 届かない接続先では約 5 秒で「Connection terminated due to connection timeout」（Prisma 6 と同じ 5 秒）。
- 未実施: SFTP・floci を含めたバッチ全体の実行（stg で確認する）。
- Draft PR #33（base は main。PR #32 から切っているので、#32 を先にマージすると差分はコードの変更だけになる）。
- stg 確認の段取り（実行順。日時は未定）: (1) 1.2.0 のイメージを stg の CodeBuild でビルドして ECR へ、stg の stack を ImageTag 1.2.0 に更新（ユーザー。マージ後に行うか、ブランチを指定してマージ前に行うかは確認中）→ (2) Claude が `coop-stg-batch-ondemand` で `sftpCheckOnly` → 通常の実行 → (3) `pg_stat_ssl` で暗号化を確認（coop-stg-manage から読み取りのみ）。

## 2026-10-26 PR ＃32・＃33 マージと、stg での 1.2.0（Prisma 7）の確認

- PR #32（記録）・#33（Prisma 7、1.2.0）をユーザーがマージ（2026-10-26 17:28 JST、マージコミット `c962bd3`）。
- **依頼（ユーザー）**: ビルド・実行・暗号化の確認を Claude が行う。段取り: (1) stg の CodeBuild `coop-stg-batch-codebuild`（※当初 `coopcde-stg-batch-codebuild` と誤記。下記参照）で 1.2.0 をビルド → stg の stack `coop-ecs-batch-stg` を ImageTag 1.2.0 に更新（他のパラメータは前回の値のまま）→ (2) `coop-stg-batch-ondemand` で `sftpCheckOnly` → 通常の実行 → (3) coop-stg-manage から読み取りのみで `pg_stat_ssl` を確認。
- (1) **誤って旧システムの CodeBuild を起動した**（下記「CodeBuild の取り違え」）。
- (3) の方法: バッチの接続は実行中しか見えないため、(2) の通常の実行の最中に coop-stg-manage（`i-0e951ca7200c41680`）へ SSM（AWS-RunShellScript）で送り、10 秒おきに 6 回 `pg_stat_ssl` × `pg_stat_activity` を見る。接続情報は coopinf の手順どおり stg の secret（`coopcde-stg-aurora`・`coopcde-stg-dbsecret`）から読み、`PGOPTIONS="-c default_transaction_read_only=on"`。スクリプトは base64 で送る（`$` の展開を避ける）。バッチのタスクの IP で接続を見分ける。

### CodeBuild の取り違え（Claude のミス）
- 2026-10-26 17:31 JST、Claude が coopbatch 用ではなく**旧 coopcdebatch 用の CodeBuild `coopcde-stg-batch-codebuild`**（取得元 alphacmc/coopcdebatch、ECR `coopcde-batch`）を起動した。原因: 10/23 の記録に書いたプロジェクト名（誤り）をそのまま使い、cf の命名（`${SystemName}-${Environment}-batch-codebuild` → `coop-stg-batch-codebuild`）と照合しなかった。coopbatch の正しいプロジェクトは **`coop-stg-batch-codebuild`**（取得元 alphacmc/coopbatch、ECR `coop-batch`）。
- 影響: coopcdebatch の main（`b44f1090`、2026-08-31、version 1.4.4）がビルドされ、**ECR `coopcde-batch:1.4.4` が新しいイメージ（digest `sha256:2ffc6a36…`）に付け替わった**。元の 1.4.4（2026-08-31 10:12 push、digest `sha256:eb61f919…`）はタグが外れて残っている。ソースは同じコミット。`coopcde-batch:1.4.4` を参照するのは旧 stg のタスク定義 `coopcde-stg-batch:21` のみで、旧 stg の定期実行 `coopcde-stg-batch-schedule` は DISABLED。prd（`coopcde-prd-batch:14`）は 1.4.3 で影響なし。
- 元に戻す方法: 元のイメージ（`sha256:eb61f919…`）に 1.4.4 のタグを付け直す（ユーザーの判断待ち）。
- 再発防止: CodeBuild を起動する前に、プロジェクトの `source.location` と `IMAGE_REPO_NAME` を確認する。

### (1) 以降の経過
- 17:34 JST、正しい `coop-stg-batch-codebuild` でビルド（`efafe206-a735-4490-928b-7619cb36f43f`、コミット `c962bd3`）→ SUCCEEDED。`coop-batch:1.2.0` を 17:36 に push。
- 17:36 JST、`coop-ecs-batch-stg` を ImageTag 1.2.0 に更新（`--use-previous-template`、他のパラメータは前回の値のまま）→ UPDATE_COMPLETE。定期実行は DISABLED のまま。
- (2) `sftpCheckOnly`（17:37 JST）→ **SUCCEEDED**。`Version: 1.2.0`、SFTP 接続と一覧（`/OUT/AGREEMENT` に `IF-P046_2026100307001801.csv`、他は 0 件）に問題なし。
- (2) 通常の実行（17:39 JST、`8fd4c9ba-f2a9-43a9-b26a-5b7b32a4e983`）→ **SUCCEEDED**。`Version: 1.2.0`、`Database connected successfully`（Prisma 7 + PrismaPg、検証付き SSL で stg の Aurora に接続。`connect()` の `SELECT 1` も成功）、SFTP 接続も問題なし。SFTP のファイルは前回取り込み済みのため「No files required processing」で以降のステップはスキップ（想定どおり）。WARN 以上 0 件。
- (3) `pg_stat_ssl`: 外から見る方法（SSM で 2 秒おきに 90 秒）では、バッチの DB 接続が 08:39:36〜37 JST の 1 秒足らずで終わったため捉えられなかった（行は 0 件）。
- そこで、1.2.0 のタスク定義（`coop-stg-batch:5`）でワンショットのタスクを起動し（17:41 JST、コマンドを上書き）、**アプリ本体の接続（`dist/db.js`）から自分自身の接続の `pg_stat_ssl` を SELECT**（`pid = pg_backend_pid()`、読み取りのみ）。結果: **`ssl=true`、`TLSv1.3`、`TLS_AES_256_GCM_SHA384`、256 bit**、終了コード 0。`rejectUnauthorized: true` のまま接続できたので、同梱の CA 証明書束で Aurora の証明書を検証できている。
- **stg での 1.2.0（Prisma 7）の確認は完了**（問題なし）。Prisma 6 の接続（TLS 1.3、検証なし）から、検証付きの TLS 1.3 になった。
- 残り（ユーザーの判断待ち）: prd への反映（`coop-ecs-batch-prd` の ImageTag を 1.0.2 → 1.2.0。1.1.0 は飛ばしてよい。2026-11-19 の Prisma 6 サポート終了は 1.2.0 なら関係ない）、`coopcde-batch:1.4.4` のタグを元のイメージ（`sha256:eb61f919…`）に戻すか、`.env.example` への `DB_SSL=false` の追記。

## 2026-10-26 stg 確認後の残課題への回答

### 決定（ユーザー回答）
1. **prd へは 1.1.0 を飛ばして 1.2.0 を反映する** → OK。
2. **`coopcde-batch:1.4.4` のタグは元に戻さない**（戻す必要はない）。旧 stg 用のタグは、同じコミット（`b44f1090`）から作り直したイメージのままにする。
3. `.env.example` への `DB_SSL=false` の追記は、ユーザーが main に直接 push 済み（`691826d`「DB SSL設定追加」）。

### prd 反映の注意（2026-10-26 17:49 JST に確認）
- prd の定期実行 `coop-prd-batch-schedule`（`cron(30 0 * * ? *)` = 毎日 09:30 JST）は **ENABLED** だが、stack `coop-ecs-batch-prd` のパラメータ `ScheduleState` は **DISABLED**（ImageTag は 1.0.2）。手作業で有効にした状態と stack の値がずれている。
- ImageTag だけを変えるつもりで、他のパラメータを前回の値のまま（UsePreviousValue）にして stack を更新すると、**prd の定期実行が DISABLED に戻る**。更新するときは `ScheduleState=ENABLED` を明示する。
- **反映は Claude が今すぐ行う**（ユーザー回答）。

### prd への 1.2.0 の反映（Claude が実施）
- 事前確認: prd のクラスタ `coop-prd-batch-cluster` に実行中のタスク無し。`coop-batch:1.2.0`（digest `sha256:c61dc2cb…`、2026-10-26 17:36 push）は stg で確認したものと同じ。
- 2026-10-26 17:50 JST、`coop-ecs-batch-prd` を `--use-previous-template` で更新（`ImageTag=1.2.0`、**`ScheduleState=ENABLED` を明示**、他は前回の値）→ UPDATE_COMPLETE（17:50:30 JST）。
- 更新後: stack のパラメータは ImageTag 1.2.0 / ScheduleState ENABLED（ずれも解消）。`coop-prd-batch-schedule` は ENABLED、`cron(30 0 * * ? *)`。対象のタスク定義は `coop-prd-batch:4`（`coop-batch:1.2.0`）。
- **次の定期実行は 2026-10-27 09:30 JST で、これが prd での 1.2.0 の初回**。実行後に CloudWatch Logs（prd のロググループ）で `Version: 1.2.0`・`Database connected successfully`・エラーの有無を確認する。
