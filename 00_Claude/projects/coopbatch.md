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
1. stg の CodeBuild（`coop-stg-batch-codebuild`。※当初 `coopcde-stg-batch-codebuild` と誤記していた。そちらは旧 coopcdebatch 用。2026-10-26 訂正）を実行する。既定では main を取ってくるので、マージ前に試すなら `--source-version feature/upgrade-node24-prisma6` を付ける。ログの `Resolved IMAGE_TAG ... -> 1.1.0` と ECR の `coop-batch:1.1.0` を確認する。
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

## 2026-10-28 1.2.0 の本番リリース完了と、prd での初回実行の確認

- **報告（ユーザー）**: 「全てマージし、1.2.0 を本番リリースした」。
- **prd の状態（AWS で読み取りのみで確認、2026-10-28 06:33 JST）**: `coop-ecs-batch-prd` は ImageTag 1.2.0 / ScheduleState ENABLED（2026-10-26 17:50 JST に Claude が更新したまま）。`coop-prd-batch-schedule` は ENABLED。
- **prd での 1.2.0 の初回実行（2026-10-27 09:30 JST の定期実行）: 正常終了**。ログ（`/ecs/logs/coop-prd-batch-loggroup`、`coop-prd/coop-prd-batch/112e9839540449129827e99dd3d473ce`）:
  - `Version: 1.2.0`、`Database connected successfully`（Prisma 7 + 検証付き SSL で prd の Aurora に接続）、SFTP 接続も正常。
  - SFTP から 3 ファイル（契約 2・速報値 1）を取り込み。契約 Read 56 / Write 56、速報値 Read 3,517 / Write 3,517、`Total Errors: 0`、`Main Batch Job (one-shot) completed successfully`（09:30:39〜09:31:44）。WARN 以上 0 件。
- これで Node 24 / Prisma 7（1.2.0）への更新は prd まで完了。Prisma 6 のサポート終了（2026-11-19）の影響は無くなった。

### 記録のコミットが main に直接入っていた件（Claude のミス）
- 2026-10-26 17:49・17:52 JST の記録のコミット 2 件（`4e50a2a`「残課題への回答と prd 反映の注意を記録」・`64e35b2`「prd への 1.2.0 反映を記録」）が、**ブランチではなく main に直接 push されていた**。ユーザーが `.env.example` の追記（`691826d`）を main に push した際に作業ツリーが main に切り替わっており、Claude が現在のブランチを確認せずに commit・push したため。
- そのため、stg 確認の記録（PR #34 のコミット 5 件）は「全てマージ」の時点で未マージのまま残っていた。2026-10-28 に PR #34 のブランチを main に合わせ直し、`conversations/2026-10-26.md` を時系列どおりにまとめ、10/23 の記録のプロジェクト名の訂正とあわせて 1 コミットで入れ直した。
- 再発防止: commit の前に `git branch --show-current` で現在のブランチを確認する（ユーザーが同じ作業ツリーで操作することがある）。

## 2026-10-28 coop へ申し送り: Node 24 / Prisma 7（1.2.0）への更新と prd 反映

- **依頼（ユーザー）**: coop への申し送り（2026-10-23 に「事後に申し送る」とした件）。
- coop のセッションが起動していなかったため（ListAgents で確認）、取り決めどおり coop の直下に未追跡の `INBOX_FROM_COOPBATCH.md` を置いた（coop の記録へ取り込んだら削除してもらう）。
- 申し送った内容:
  - coopbatch は Node 24（`node:24-alpine3.24`）/ Prisma 7.10.1 / 検証付き SSL の 1.2.0 になり、prd まで反映済み（2026-10-27 09:30 JST の定期実行で正常終了）。coop の正式決定前に先行して対応した事後報告。Node の統一表で残りは coops3view（22）と coopcdealert（22）。
  - prd の定期実行の設定ずれ（実体は ENABLED、stack の `ScheduleState` は DISABLED）を、1.2.0 の反映時に解消したこと。
  - 旧 coopcdebatch の ECR `coopcde-batch:1.4.4` を誤って付け替えた件（ユーザーの判断で戻さない）。

## 2026-11-16 ガス・でんき請求データで同一契約番号・同一請求年月が複数ある場合の挙動確認（調査のみ、修正なし）

### 質問
同じ契約番号で請求年月が同じデータが複数入るとどうなるか。ユーザーの予想は「最初のデータで挿入、以降はエラー」。

### 調査結果（現状の動き）
- キーは 組合員番号+契約番号+請求年+請求月（`src/batch/processors/bill-processor.ts`）。
- 1件目は create。2件目以降は DB を `findUnique` で検索し、
  - 通し番号（serialNumber）が保存済み以下 → エラーCSV（`ガス請求情報重複` / `でんき請求情報重複`）、DB は変わらない
  - 通し番号が保存済みより大きい → update で上書き（エラーにならない）
- 請求ステップ `step3_processBill` は `chunkSize: 1` のため、1行ごとに書き込みまで終わり、同じファイル内でも別ファイルでも上の判定が効く。
- `docs/coop/bill.md`「3. 新規 / 更新の判定と重複排除」の記載と一致。

### 論点（未決・相談として提示）
1. **chunkSize を 2 以上にした場合の潜在リスク**: `chunkSize: 1` は `// TODO: 仮値`。上げると同じチャンク内の重複行がどちらも create になり、2件目が一意制約違反になる。書き込み部の例外は `step-executor.ts` で受け止められてログと errorCount 加算のみとなり、エラーCSVには出ない。そのチャンクの以降の行も書き込まれない。chunkSize 変更時はチャンク内重複の対策がセットで必要。
2. **ドキュメントのずれ**: `docs/coop/bill.md` は「マスタデータキャッシュを検索」とあるが、実装は DB を直接 `findUnique` で検索している。結果は同じ。
3. **旧システム（coopcdebatch）との突き合わせ**: 同じ判定をしているかは未確認。必要なら確認すると提示済み。

いずれも対応するかどうかはユーザー判断待ち。

## 2026-11-16 利用年月を「請求年月-1」から「料金年月」に変えるべきかの相談（以前からの課題）

### ユーザーからの問題提起
- 今の仕様では「請求年月 - 1」を利用年月として表示している。そのため、同じ請求年月のデータが複数あることを想定していない。
- CDE（エネルギー供給会社）に「同じ請求年月のデータが複数ある場合、料金年月を使えないか」と質問済みだが、回答がない。
- 滞納や手続きの遅れで、同じ請求年月に複数の利用年月のデータが入ってくるのではないかと推測している。
- 本システムは請求ではなく利用年月別に表示するものなので、料金年月を使うのが正しかったのではないか。
- ただし、検針日以降に解約した場合は残りが翌月請求になるが、料金年月は当月になっているように見える。
- 依頼: 現行の直近数か月分の請求データを確認してほしい。

### 確認できたこと
- 仕様書 `coop/document/csv_file/bill.csv.md` では、請求年月は使用、料金年月は未使用（必須・使用欄が空）。コードも `料金年月` はコメントアウト（`src/batch/types/csv-row-bill.ts:26`）。
- DB（gas_bill / denki_bill）には料金年月を保存していないため、DB からは判断できない。元の請求CSV（S3 `treated/` の K020 ファイル）を見る必要がある。
- 手元（~/git, Downloads, Documents）に K020 の請求CSVは無かった。

### 止まっていること
- Claude からの本番 AWS（S3）参照は、権限の自動判定で拒否された。回り込みはせず、ユーザーにデータ提供方法を確認中。

### 決定: データの入手方法
- ユーザーは「1. このセッションに S3 読み取りを許可する」を選んだ。
- 提案した許可ルール（このリポジトリの `.claude/settings.local.json`）: `Bash(aws s3 ls:*)` と `Bash(aws s3 cp s3://:*)`。rm / mv / sync / アップロードは含めない。`settings.local.json` は今の `.gitignore` の対象外なので、追加を推奨した。
- 段取り: ① 許可設定を入れる（ユーザー、または「作って」の指示で Claude） → ② `coop` プロファイルでバケットを確認 → ③ 直近数か月分の K020 ファイルを scratchpad にダウンロード → ④ 重複・料金年月と請求年月の関係・解約ケースを集計。

### ① 完了: 許可設定
- ユーザーの指示で Claude が `.claude/settings.local.json` を作成（上記 2 ルールのみ）。
- `.gitignore` は変更せず、ローカル専用の `.git/info/exclude` に追加した（コミット・PR 不要）。
- `aws s3 ls --profile coop` が通ることを確認。請求CSVの置き場の候補: `coopcde-prd-batch-csv-backup`（本番）、`coopcde-stg-batch-csv-backup`、`coop-batch-csv-backup`（環境不明）。
- ②以降に進むことと、対象を本番 `coopcde-prd-batch-csv-backup` にすることは、ユーザーの返事待ち。

### ②〜④ 完了: 本番の請求CSV（2026-07〜11、5系統・25ファイル・439,788行）の集計結果
- 対象: `s3://coopcde-prd-batch-csv-backup/treated/` の K020（担当店 110610997 / 122128300 / 122128318 / 122128326 / 122128334）。scratchpad にダウンロードして集計（リポジトリには置いていない）。
- **料金年月の意味**: 使用期間終了日の月（≒検針月）と 99.8% 一致。「請求年月 - 1 = 料金年月」は 99.96%（439,610 行）。
- **同じ契約番号+請求年月+サービス種別が複数ある: 5か月で 56 件（訂正を除く）**。3つの型。
  1. でんきの遅れ請求: 前月分が請求されず、翌月に2か月分（料金年月が違う、通し番号はどちらも 0001）が来る。今は後の行が「でんき請求情報重複」で落ち、**当月分が捨てられ、古い月の値が「請求年月-1」の月として表示される**。本番エラーCSVで確認（2026-10: 5件、2026-11: 18件）。
  2. ガスの解約精算: 通常の請求（発行種別 01）と解約時の最終請求（発行種別 02・日割 1）が同じ請求年月に来る。最終請求が「ガス請求情報重複」で落ちる（2026-11: 14件）。
  3. ガスの訂正: 元の請求（0001）、取消（削除サイン 1・マイナス金額・0001）、再計算（0003）。取消は重複エラーで落ち、0003 で上書きされるので、結果は正しい値になる（エラーCSVには取消行が出る）。
- **料金年月をキーにした場合も重複する: 111 件**。ほぼ全部がガスの解約精算で、最終請求は翌月に請求されるのに、料金年月は通常請求と同じ月になっている（ユーザーの懸念どおり）。
- **一意になるキー**（削除サイン 1 を除き、訂正は通し番号最大を残した場合）: 「契約番号+サービス種別+料金年月+発行種別」「契約番号+サービス種別+使用期間終了年月日」「請求番号」はいずれも重複 0。
- 対象バケットはユーザーが `coopcde-prd-batch-csv-backup` と指定した。
- 方針（キーや表示月の変更）は未決。ユーザーと相談中。ガス解約時の最終請求を「利用年月別の表示」で通常分と合算するか、別の行にするかの画面仕様の判断が要る。
  - → ユーザー回答: **ガス解約時の最終請求は、利用年月を翌月（通常分の次の月）にすることで仕様時点で合意済み**。合算はしない。
  - これを踏まえた試算（訂正を除いた有効行で）:
    - 現行（請求年月-1）: 重複 56。翌月に請求される最終請求は合意どおり翌月になるが、通常分と同じ請求年月で来る最終請求とでんきの遅れ請求で重複する。
    - 料金年月: 重複 111（翌月に請求される最終請求が通常分と同じ月になり、合意に反する）。
    - 案「料金年月を使い、発行種別=02 かつ使用期間開始月=料金年月のときだけ +1 か月」: **重複 0**。現行と表示月が変わるのは 59 行で、問題のケースだけ（でんきの遅れ請求 29、ガス最終請求 29 など）。
  - 発行種別の定義: **01 = 定期、02 = 解約（設計時の受領資料で確認済み。2026-11-16 に coop から連絡）**。当初ここに「データからの推定」と書いていたが、確認済みの扱いに訂正した。採用するかは未決（その後 24 か月分で検証）。
  - ユーザー回答（3点への返答）: ① 1年分くらいで追加検証してほしい ② この案ならDB項目は何が最適か ③ **過去データ（取り込み時に捨てられた分の補正）は一旦考慮外とする**。
  - ① 結果（2025-12〜2026-11、60ファイル、1,073,105行）: 現行 請求年月-1 は重複 145、料金年月は重複 301、**案は重複 0**。案で表示月が現行と変わるのは 159 行（ガス最終請求、でんき遅れ請求など問題のケースのみ）。毎月 5〜32 件の重複が現行では出ている。
  - ② 画面側の確認: coopcdeweb `members.service.ts` が bill_year/bill_month から -1 か月して利用年月を作っている（convertBillYear/convertBillMonth）。速報値（early_bill）との「最新確定請求年月以降」の比較にも請求年月を使っている。DB項目の提案は Claude から提示済み（下記の次の見出し参照）。
  - ② DB項目の提案（未決・相談中）:
    - 推奨 B: gas_bill / denki_bill に `usage_year` / `usage_month`（利用年月、バッチが案のルールで算出）を追加し、主キーを (member_code, contract_number, usage_year, usage_month) に変更。`bill_year` / `bill_month` は実際の請求年月のまま非キー列として残す。追跡用に `fee_year_month`（料金年月）と `issue_type`（発行種別）も保存。画面側は利用年月の算出と並び順を新列に切り替える。速報値との比較は bill_year/bill_month のままでよい。
    - 代替 A: 列は変えず、bill_year/bill_month に「利用年月+1」を入れる（画面変更なし）。ただし列の意味が実際の請求年月とずれ、速報値との比較もずれうるため非推奨。
  - ユーザーの質問: 既存データの usage_year/usage_month はどうするか、単純に bill_year/bill_month - 1 か月か。
    - Claude の回答（未決・相談中）: **単純に -1 か月でよい**。今の画面表示と完全に同じになり、今の主キーが一意なので -1 しても一意。fee_year_month / issue_type は既存行は NULL（列は NULL 可にする）。
    - 切り替えのシミュレーション（既存=現行ロジックで取り込み済み、切替月以降を案ルールで取り込み）: 切替月にだけ、過去に捨てられたデータの影響で 1 件程度の重複エラーが出うる（例: でんき 912510784）。それ以降に残るエラーはすべて取消行（削除サイン 1、通し番号 0001）で、直後の再計算行（0003）で正しく上書きされるため問題なし。
    - 別論点: 取消行は今も「請求情報重複」としてエラーCSVに出ている。削除サイン 1 の行はエラーにせず読み飛ばす扱いにするか。
      - → **決定: 今のままでよい（エラーCSVに出す）。運用側で解決した時点で削除する。** 読み飛ばしの変更はしない。
  - ユーザー依頼: ① 画面は過去2年分を表示しているので、過去2年分で再検証したい ② 過去2年分の重複分を直すとしたら、どんな方策があるか（段階的でもよい）。
    - 旧システム coopcdebatch も同じ判定（先に来た行を残し、通し番号が大きければ上書き）だった（`app.service.ts:225-267`）。そのため今の DB はファイルを順に処理すれば推定できる。
    - ① 結果（2024-12〜2026-11、120ファイル、2,200,629行）: 現行 請求年月-1 は重複 324（毎月 5〜36 件）、料金年月は 699、**案は重複 0**。案で表示月が変わるのは 355 行。
    - 今の DB（推定）と、案のルールで取り込んだ「あるべき状態」の比較結果（2024-12〜2026-11 のファイル）: 直す必要がある行は **451 行（343 契約）**。内訳は 追加（取り込み時に捨てられた）339、更新（別の請求の中身が入っている）85、削除（あるべき状態に無い月）27。毎月 10〜30 行程度。明細は scratchpad/k020_out/fix_candidates.csv。
      - 推定の前提: 契約マスタ紐付け（組合員番号）、PL121/PW010 除外、手修正（_fix）、2024-11 以前の DB の状態は考慮していない。正確な件数は本番 DB との突き合わせが必要。
    - ② 修正方策の提案（未決・相談中）:
      - 段階0（前提）: 新しい列（usage_year/usage_month）とバッチ・画面の変更を先にリリースし、既存行は請求年月-1 で埋める。これ以降の新しいずれを止める。同じ請求年月の2件を別の行として持てるのは新しい主キーだけなので、過去分の修正もこの後になる。
      - 段階1: 修正リストを確定。S3 の元CSV（2年分）から「あるべき状態」を作り、本番 DB の抽出と突き合わせて、追加・更新・削除のリストを作る。レビューする。
      - 段階2: 適用。案A（推奨）差分だけを当てるスクリプト（バックアップ → dry-run → 適用 → 検証）。案B 影響した契約の行だけを元CSVから抜き出し、その契約の対象期間の行を消してからバッチのリカバリーモードで月順に再取り込み。案C 2年分を全部消して再取り込み（約220万行、重く影響が大きいので非推奨）。
      - 段階的に進めるなら、直近の月から（利用者がよく見る範囲）、または種類別（でんきの遅れ請求 → ガス最終請求）に分けて当てる。
      - ユーザーに確認中: ① 段階0（スキーマ・バッチ・画面の変更）の方式案を先に出す順番でよいか ② 段階1の本番 DB 抽出を、Claude が直接つなぐか、抽出ファイルをもらうか。
      - → **決定: ① OK（段階0の方式案を先に出す）。② 当初「本番 DB に直接つなぐ」だったが、Claude が本番 DB の日次ダンプ（リレーバケット `coop-migration-relay-725011976834/db-copy-to-stg/latest.dump`、2026-11-16 01:00 時点、coopinf の backup-prd-db.sh が作成）を見つけて提案し、ユーザーが「日次ダンプを使う」を選んだ。本番 DB には接続しない。**
      - ダンプは scratchpad に置き、手元の PostgreSQL には復元せず（開発データを上書きしないため）、`pg_restore --data-only` で gas_bill / denki_bill をテキストで取り出して突き合わせる。
      - 段階1 結果（本番 DB 2026-11-16 01:00 時点 vs 元CSV 2024-12〜2026-11 を案ルールで取り込んだ状態）: DB 行数 gas 753,680 / denki 2,390,961。一致 2,193,838 行。**直す必要がある行 445 行（340 契約）**: 追加 335（ガス最終請求 258、でんき遅れ請求 71、でんき発行02 6）、更新 85（大半はでんきの通常月に遅れ請求の古い月の中身が入っているもの 66）、削除候補 25。推定（451 行）とほぼ一致し、推定の前提（契約マスタ紐付け等）の影響は小さい。同じキーに組合員番号が複数あるものは 0。
      - 修正リスト: scratchpad/k020_out/fix_list_vs_db.csv（DB の行と CSV の行を並べたもの）。適用はまだしない（段階0のリリース後）。

## 2026-11-16 coop へ申し送り: 請求データの同一請求年月の重複と仕様書の修正依頼

- **依頼（ユーザー）**: 事の顛末と仕様書の修正を coop に依頼する。
- coop のセッションが起動していなかったため（ListAgents で確認）、coop の CLAUDE.md の取り決めどおり、coop の直下に未追跡の `INBOX_FROM_COOPBATCH.md` を置いた（コミットしない。coop が記録へ取り込んだら削除する）。coop には既存のユーザーの未コミット変更があったが、触っていない。
- 申し送った内容: 経緯、分かった事実（料金年月の意味、3つの重複の型、料金年月にも重複があること、本番エラーCSVでの確認、過去2年の推定修正件数）、決まったこと（ガス最終請求は翌月、取消行はそのまま、段階0の方式案を先に出す、日次ダンプで突き合わせ）、検討中の案（利用年月の決め方、DB の列）。
- 依頼した内容: ① 経緯の記録 ② 仕様書の修正（`document/csv_file/bill.csv.md` の料金年月・発行種別・削除サインの注記と訂正の流れ、`document/database.md` は方式案の決定後に反映、画面仕様の文書があれば注記） ③ CDE への問い合わせに「発行種別の定義」「ガス最終請求の料金年月が通常分と同じ月になる理由」を追加するかの検討。
- **coop からの返信（coop-c6 より SendMessage、2026-11-16）**:
  - 発行種別の定義は設計時の受領資料で確認済み（01 = 定期、02 = 解約）。データからの推定ではない。→ 利用年月の案（発行種別 02 で、使用期間の開始月 = 料金年月のときだけ翌月）の前提が一つ固まった。
  - INBOX_FROM_COOPBATCH.md は coop の記録（coop の conversations/2026-11-16.md）に取り込み、削除済み。coop の PR は alphacmc/coop#34。
  - coop の `document/csv_file/bill.csv.md` の発行種別の備考を「01 = 定期、02 = 解約（設計時の受領資料で確認済み）」にした。
  - CDE への問い合わせから「発行種別の定義」は外す。追加を検討するのは「検針日以降に解約したガスの最終請求で、料金年月が通常分と同じ月になる理由」の1点だけ（追加するかはユーザーの判断待ち）。
  - → **決定（ユーザー）: 質問だけは CDE に投げておく。ただし回答は待たない。** CDE は担当者がよく変わり、これまでの質問にも回答がない。おそらく「そういうもの」という回答になる。現実のデータがそうなっている以上、それを前提に進める。
  - coop に共有し、coop が CDE への問い合わせ一覧 `support/cde_inquiries.md` を新規作成して載せた（alphacmc/coop#34、コミット 0d62d21）。#1 同じ請求年月が複数ある場合に料金年月を使えないか（回答を待たない・回答なし）、#2 ガス最終請求の料金年月が通常分と同じ月になる理由（質問は送るが回答は待たない）。発行種別の定義は「問い合わせない（確認済み）」。
  - ユーザーに確認中だった3点（元の質問）: ① この案の方向で進めるか（進めるなら過去分（S3 に 2023 年分から）での追加検証から） ② 直すのは取り込み側（coopbatch）だけか、画面側（coopinf 等）も「請求年月-1」で計算していて直す必要があるか（Claude が横断確認できる） ③ 取り込み時に捨てられた分（2026-10・11 のエラーCSVの 39 件）の補正方法。コード修正には未着手。
- ユーザーへの確認事項: 2026-11-16 12:01 に `122128326IF-K020_2026110609272401_errorfix00.csv`（契約番号 912531098、料金年月 202610）が `treated/` に入っている。通し番号が同じなので今の仕組みでは重複エラーになるはず。DB 側の手当ての有無を確認中。

## 2026-11-16 請求データ重複の対応: この後の作業の順番（提示・ユーザーの了承待ち）

ユーザーの「この後の作業を教えてください」に対して提示した順番。

1. 段階0の方式案を作る（Claude）: DB の列（usage_year/usage_month・料金年月・発行種別の追加、主キーを利用年月に変更、既存行は請求年月-1 で埋める）、本番 DDL の当て方（coopinf の手順に乗せるか確認）、coopbatch の取り込み変更とテスト、coopcdeweb の利用年月の計算と並び順の切り替え、壊れないリリースの順番（主キー変更で今のバッチが動かなくなる点が最大の注意点）。
2. 方式案の承認（ユーザー）。
3. 実装: coopbatch はこのセッション（ブランチ＋Draft PR）、coopcdeweb はそのセッションへ申し送り、DDL 適用が coopinf 担当なら coopinf へ申し送り。
4. stg で確認 → 本番リリース。
5. 段階1のやり直し: リリース直前の最新ダンプで修正リストを作り直し、ユーザーがレビュー。
6. 段階2: 修正リストを DB に当てる（案A: バックアップ → dry-run → 適用 → 検証）。実行の可否はユーザー判断。
7. coop の database.md への反映（方式案の決定後）。

並行の片付け（提示）: 記録のコミット（main なので記録用ブランチ＋Draft PR）、scratchpad の本番データ（請求CSV 2年分・DB ダンプ、個人情報を含む）を残すか消すか（ユーザーに確認中）、`.claude/settings.local.json` の S3 読み取り許可は手順5まで残す想定。

- → **ユーザー回答: ① 進めてよい ② （本番データは今後使うかの質問に、Claude が「使わない。作業5は最新を取り直す」と答えたうえで）「消して」**。scratchpad の本番データ（請求CSV 2年分 1.7GB、DB ダンプと取り出したテキスト 900MB、エラーCSV、集計結果）を削除。個人情報を含まない集計用スクリプト（scratchpad/scripts）だけ残した。
- 記録のコミット: ブランチ `feature/record-bill-duplicate-investigation`、Draft PR https://github.com/alphacmc/coopbatch/pull/36 （base は main。coopbatch に staging ブランチは無い）。

## 2026-11-16 段階0の方式案（提示・ユーザーの承認待ち）

調べて分かったこと:
- coopbatch で請求テーブルを触るのは `bill-processor.ts`（DB 検索）と `upsert-bill-writer.ts`（書き込み）だけ。CSV の型では 料金年月・発行種別・削除サインがコメントアウト（`csv-row-bill.ts:24,26,33`）。テストの仕組み（jest 等）は無い。
- coopbatch に prisma の migrations は無い。coopinf の手順書で「stg へ prisma migrate は流さない」、coopcdeweb の記録で「DB 構造は batch 側が管理」。本番の DB 変更の前例は coopinf の `backfill-gas-option-fee-code.sh`（manage サーバ上でユーザーが実行、dry-run → --execute、実行前に pg_dump 退避）。
- coopcdeweb は `members.repository.ts` で組合員番号＋契約番号の請求を全件取り、請求年月の新しい順に並べる。`members.service.ts` で利用年月を請求年月-1 で作り、速報値は「最新の請求の請求年月より後」を出す。スキーマは `packages/common-types/prisma/schema.prisma`（他の写しとそろえる必要あり）。
- K020 は毎月 4〜7 日に届く（S3 のファイル名から）。

方式案:
- **DB（gas_bill / denki_bill 共通）**: `usage_year` varchar(4)・`usage_month` varchar(2)（利用年月）、`fee_year_month` varchar(6)（料金年月、NULL 可）、`issue_type` varchar(2)（発行種別、NULL 可）を追加。主キーを (member_code, contract_number, usage_year, usage_month) に変更。bill_year / bill_month は非キー列として残す。
- **DDL は2段に分ける**:
  - DDL-1（壊れない変更）: 4列を NULL 可で追加し、既存行の usage を請求年月-1 で埋める。今のバッチ・画面はそのまま動く。
  - DDL-2（壊れる変更）: 直前にもう一度 usage が空の行を埋めてから、usage を NOT NULL にし、主キーを差し替える。**新しいバッチと同時に出す**（古いバッチは usage を入れないため、DDL-2 の後は動かない）。
  - SQL は coopbatch に置き（DB 構造はバッチ側の管理）、実行は前例どおり manage サーバ上でユーザーが行う（stg → prd、実行前に pg_dump 退避、dry-run あり）。置き場所・実行者はユーザー確認。
- **coopbatch**: CSV の型で 料金年月・発行種別を有効にする。利用年月を計算する関数を新設（料金年月。発行種別 02 で使用期間の開始月 = 料金年月なら翌月）。bill-processor の DB 検索キーと writer の複合キーを利用年月に変える。新しい4列を保存する。通し番号の判定は今のまま。docs/coop/bill.md を更新。計算関数には Node 標準のテスト機能（node:test）でテストを付ける（依存を増やさない）。
- **coopcdeweb**（そのセッションへ申し送り）: スキーマ（common-types と写し）に4列を追加。並び順を利用年月に。利用年月は新しい列を使い、空なら請求年月-1 にフォールバック（DDL-1 の後ならいつ出しても動く）。速報値の比較は bill_year / bill_month のまま。過去2年分の絞り込みがどこで行われているかは coopcdeweb 側で確認。
- **リリースの順番**: ① DDL-1（stg → prd） ② 画面（フォールバック付き） ③ DDL-2＋新バッチを同じ日に。K020 が届かない日（毎月 8 日〜翌月 3 日）に行う。④ その後に段階1のやり直し → 段階2。
- 確認事項: SQL の置き場所と実行者、リリース日程、coopcdeweb への申し送りのタイミング（方式案の承認後）。
- → **決定（ユーザー）: ① 方式案 OK ② DDL の SQL は coopbatch に置く。実行はユーザーが行う ③ リリースは 11 月中（2026-11-30 まで。K020 が届く 12/4〜7 より前）**。
- 次の段取り: coopcdeweb へ申し送り → coopbatch の実装（新しいブランチ＋Draft PR）→ stg 確認 → DDL-1（stg → prd）→ 画面 → DDL-2＋新バッチを同じ日に（11 月中）。

### 進捗（2026-11-16）
- **coopcdeweb へ申し送り**（coopcdeweb-1a が起動していたので SendMessage）。coopcdeweb からの共有（実装計画は coopcdeweb のユーザー承認待ち）:
  1. **画面（②）は各環境で DDL-1 の後に出す必要がある**（Prisma は schema の列を SELECT するので、列が無いと請求の取得がエラーになり会員画面が出なくなる）。
  2. ②では @@id を請求年月のまま、usage を String?（NULL 可）で追加する。coopcdeweb は findMany だけなので DB の主キー変更の影響は無い。NOT NULL＋@@id(利用年月) へのそろえは DDL-2 の後に小さな PR で行う。
  3. 「過去2年分」の絞り込みとカレンダーは frontend で、すでに bills の usageYear/usageMonth 基準。backend が利用年月の降順で返せば frontend の変更は不要。
  4. 速報値との比較は「並び順の先頭行」ではなく「その契約の行の中で最大の bill_year/bill_month」と比べる案を coopcdeweb のユーザーに提示中。
  - coopbatch から 4 点とも了解と返信（列名・型をそろえること、PR #37 の場所を伝えた）。
- **coopbatch の実装**: ブランチ `feature/bill-usage-month`、Draft PR https://github.com/alphacmc/coopbatch/pull/37 （1.3.0）。
  - 利用年月の計算関数 `src/batch/utils/usage-year-month.ts` とテスト（node:test、8 件、`npm test`）。スキーマ（4 列追加、@@id を利用年月に）、bill-processor の検索キーと保存列、writer の複合キー、docs/coop/bill.md、バージョン 1.3.0。
  - DDL: `db/sql/2026-11-bill-usage-month/`（00_check / 01_ddl1_add_columns / 02_ddl2_switch_pk / 90_rollback / README）。ユーザーが manage サーバで実行する手順を README に記載。
  - 確認済み: build・test が通る。手元の使い捨て PostgreSQL 16 で main のスキーマから DDL-1 → DDL-2 を流すと新しい schema.prisma と差が無い（prisma migrate diff）。DDL-1 は再実行可、DDL-1 後に入った行も DDL-2 で埋まる、DDL-2 の2回目は主キーの確認で止まる、同じ請求年月の2件が登録でき、戻し用の確認クエリが重複を検出する。使い捨て DB は削除済み。
  - コードレビュー（code-reviewer エージェント）: CRITICAL / HIGH / MEDIUM なし、承認。LOW 2 件はその場で対応（コミット 8553b2c）: ① 90_rollback.sql の A は主キー名 `<テーブル名>_pkey` 前提であることを注記（違えば失敗してトランザクションが戻るだけ） ② 過去の請求CSVを新バッチで取り込み直すと、既存行（請求年月-1 で埋めた行）は直らず正しい月の行が別に追加される旨を README に注記し、過去分は修正リスト（段階1・2）で直す方針を明記。
- **coopcdeweb の実装**: Draft PR alphacmc/coopcdeweb#135（1.8.3）。stg 未反映。方式は合意どおり（4 列 NULL 可で追加、@@id は今のまま、利用年月の降順、空なら請求年月-1、速報値は契約内で最大の請求年月と比較）。backend jest 28 件成功、レビューで CRITICAL / HIGH なし。Docker でのビルド確認は未（Docker Desktop が見つからない）。
  - coopcdeweb からの確認: 利用年月を求められない行に空文字が入り、DDL-2 の後は主キーに空文字が入る件。→ coopbatch の回答: 想定どおり。空文字になるのは料金年月も請求年月も使えない行だけで旧実装と同じ扱い（coopcdebatch の挙動を変えないためエラーにしない）。書き込み前に同じキーで findUnique するので一意制約では落ちない。実データ 24 か月で該当 0 件。画面で空文字を NULL と同じに扱い請求年月-1 で表示する方針で問題ない。
  - **段取り**: stg への DDL-1 はユーザーが実行する。実行したらユーザーが coopbatch に知らせ、coopbatch から coopcdeweb に伝える。coopcdeweb の stg 反映時期は、coopcdeweb のセッションでユーザーと決めて連絡が来る。

## 2026-11-16 バージョンを 1.4.0 にする（PR ＃37 マージ後）

- **決定（ユーザー）**: 利用年月の変更のバージョンを 1.3.0 ではなく **1.4.0** にする。DDL の手順書（README・02_ddl2_switch_pk.sql）の「バッチ 1.3.0」も 1.4.0 に直した。coopbatch のタグは v0.5.0 / v1.0.0 のみで重複なし（記録にある「1.4.0〜1.8.0 のタグ」は coopcdeweb の話）。
- PR #36（記録）と PR #37（実装、1.3.0）は 2026-11-16 15:37 JST にユーザーがマージ済みだった。
- **失敗**: Claude が PR #37 の状態を表示させただけで、MERGED でも止まらないコマンドにしていたため、マージ済みの確認より先に、
  - マージ後に削除されていた `feature/bill-usage-month` に 1.4.0 のコミットを push し、リモートにブランチを作り直してしまった。
  - マージ済みの PR #37 のタイトルと説明を 1.4.0 に書き換えてしまった（→ 1.3.0 に戻した）。
  - 作り直したリモートのブランチの削除は権限の自動判定で拒否されたため、ユーザーの判断に任せる（中身はマージ済みのコミットと 1.4.0 のコミットだけ）。
- 対応: main から `feature/version-1.4.0` を作り、1.4.0 のコミットを移して新しい Draft PR にした。
- 再発防止: push の前のマージ確認は、状態が OPEN でなければ止まる形（`[ "$(gh pr view N --json state -q .state)" = OPEN ] && …`）で行う。
- coopcdeweb からも連絡: 利用年月の変更（#135、マージ済み）のバージョンを、ユーザーの指示で **1.8.3 から 1.9.0** に変える（Draft PR alphacmc/coopcdeweb#136）。stg・prd とも 1.9.0 として出す。中身は #135 と同じで、「各環境で DDL-1 の後に出す」順番も変わらない。上の記録の「#135（1.8.3）」は 1.9.0 に読み替える。
- リリースの順番（バージョン込み）: ① DDL-1（stg → prd） ② coopcdeweb 1.9.0 ③ DDL-2 と coopbatch 1.4.0 を同じ日に（K020 が届かない日、11 月中）。

## 2026-11-16 DDL-1 の実行（環境は確認中）

- ユーザーが manage サーバ上で `00_check.sql` → `01_ddl1_add_columns.sql` を実行（SQL は `20261116/` に配置）。
  - 事前確認: 主キーは請求年月のまま、追加列なし、請求年月の形式不正 0 件（gas_bill 753,680 行 / denki_bill 2,390,961 行）。
  - DDL-1: ALTER TABLE ×2、UPDATE 753,680 / 2,390,961（全行）、埋められない行のチェック通過、COMMIT。
- Claude からユーザーに確認中: ① stg と prd のどちらで実行したか（行数は 01:00 の本番ダンプと同じだが、stg は毎晩本番から復元されるので区別できない） ② 実行前の pg_dump を取ったか ③ 事後の `00_check.sql` の結果（列が4つ NULL 可で追加、主キーは請求年月のまま、利用年月が空の行 0 件）。
- stg だった場合は、Claude から coopcdeweb に「stg に DDL-1 を入れた」と伝える（約束済み）。
- **回答（ユーザー）**: ① **stg で実行**。本番の 2026-11-15 分のバックアップを stg にリストアしてから実行した ② 実行前のバックアップ取得済み ③ 事後の 00_check.sql: 主キーは請求年月のまま、4 列（fee_year_month 6 / issue_type 2 / usage_month 2 / usage_year 4）が両テーブルとも NULL 可で追加、利用年月が空の行 0 件、行数 gas_bill 753,680 / denki_bill 2,390,961、請求年月の形式不正 0 件。→ **stg の DDL-1 完了。期待どおり。**
- coopcdeweb に「stg に DDL-1 を入れた。coopcdeweb 1.9.0 を stg に出してよい」と伝えた。coopcdeweb の返信: 1.9.0 の stg 反映は、coopcdeweb の PR #136（1.9.0 にする PR）をユーザーがマージしてから行う（CodeBuild は main をビルドするため）。stg は今 1.8.2 で動いている。反映・確認が終わったら連絡が来る。
- **stg の次の手順（提示・ユーザーの了承待ち）**: ① coopcdeweb #136 マージ → 1.9.0 を stg へ ② coopbatch PR #38（1.4.0）をマージ ③ stg で DDL-2 と coopbatch 1.4.0 の反映を同じ日に（間に stg のバッチが動かない時間帯） ④ stg で新バッチの動作確認。
  - ④の案: stg の DB は本番 11/15 時点と同じなので、11 月分の K020 をリカバリーモードで取り込み直す。対象 `110610997IF-K020_2026110708091201.csv`（ガス）と `122128326IF-K020_2026110609272401.csv`（でんき）。期待: ガス最終請求 14 件が翌月の利用年月で新しく入る、でんき遅れ請求の前月分 18 件（料金年月 202609）が利用年月 202609 で新しく入る、それ以外は通し番号が同じなので「請求情報重複」（stg なので量が多くても可）。でんきの利用年月 202610 の行は 9 月分の中身のまま（過去分の修正＝段階2の範囲）。確認用 SQL と取り込み直しの手順は、了承後に Claude が用意する。
- coopcdeweb から: **stg に coopcdeweb 1.9.0 を反映**（ecs-alb-stg-stack、17:02 JST に ECS 安定、タスク 2 本とも 1.9.0、起動ログにエラーなし）。ユーザーが実アカウントで会員画面（ガス・でんき）の表示を確認中。**DDL-2 の前の状態で表示が今までと同じかを見るため、stg の DDL-2 とバッチ 1.4.0 は、coopcdeweb から確認完了の連絡が来るまで待つ。**
- coopcdeweb から: **stg 1.9.0 の DDL-2 前の画面確認が完了**（ユーザーが実アカウントで確認、3 点とも OK: ガス・でんきの会員画面が出る／表・グラフ・月ごとの明細の年月と金額が今までと同じ／速報値の出方も同じ。CloudWatch で 17:11〜17:12 に請求取得 5 回、16:59 以降の ERROR・例外 0 件）。→ **stg の DDL-2 とバッチ 1.4.0 に進んでよい。**
  - coopcdeweb の依頼で、取り込み後の画面確認用の契約番号を伝えた: ガス 910240391（11 月請求に通常分と解約の最終請求。取り込み後は利用年月 2026-10 と 2026-11 に分かれるはず）、でんき 912292734（11 月請求に料金年月 202609 と 202610。取り込み後は利用年月 2026-09 が新しく入る。2026-10 の行は 9 月分の中身のままで、段階2の範囲）。
- **stg の DDL-2 以降の手順（提示・ユーザーの了承待ち）**: ① 00_check.sql ② pg_dump 退避 ③ 02_ddl2_switch_pk.sql ④ 00_check.sql ⑤ バッチ 1.4.0 を stg に反映（PR #38 のマージが先） ⑥ 11 月分の K020（ガス・でんきの 2 ファイル）をリカバリーモードで取り込み直す ⑦ 確認用 SQL と画面（coopcdeweb）で確認。①〜⑤はユーザー、取り込み直しの手順と確認用 SQL は了承後に Claude が用意する。

## 2026-11-16 coopcdeweb からの調査依頼: 使用期間・検針日が空の請求（相談中）

- **依頼（coopcdeweb-1a、coopcdeweb のユーザー了承済み、急ぎではない）**: 本番の K020 24 か月分で、使用期間開始年月日・使用期間終了年月日・検針年月日が空の行の件数（項目ごと・ガス／でんき別、0 件でなければ契約番号と請求年月の例）。理由: 画面の backend は 3 項目を `DatetimeUtils.addSlash` で yyyy/MM/dd にしており、NULL だと例外になってその組合員の会員画面全体が 500 になる。coopbatch は空欄を `emptyToNull` で NULL にして書く。0 件なら coopcdeweb は記録だけ、1 件以上なら空欄表示の修正を別 PR で出す。
- **Claude の提案（ユーザーの了承待ち）**: 本番 CSV は削除済みなので取り直さず、**stg の DB（本番 11/15 と同じ中身）で gas_bill / denki_bill の 3 項目が NULL・空文字の行を数える** SQL をユーザーに渡した（manage サーバで実行、読むだけ）。画面が 500 になるかは DB に空のまま入っている行で決まり、取消行は DB に入らないので自然に除外される。今後の CSV に空が来るかまで見るなら、本番 CSV 2 年分の取り直しが必要（どちらにするかユーザーに確認中）。coopcdeweb にもこの方向で確認中と返信済み。

## 2026-11-16 coop からの依頼: オンデマンド実行の既定をリカバリーモードに（coopinf の PR 待ち）

- **依頼（coop-c6、ユーザー承認済み 2026-11-16）**: オンデマンド実行（Step Functions `coop-{env}-batch-ondemand`）を、入力なしのときリカバリーモード（BATCH_RECOVERY_MODE=true）で動くように変える。正本は coopinf の `cf/ecs-batch-ondemand-cf.yaml` で、修正とデプロイは coopinf-cd が行う。
  - 新しい動き: 入力なし・`{}`・打ち間違い → リカバリー／`{"batchRecoveryMode": "true"}` → リカバリー／`{"batchRecoveryMode": "false"}` → 通常の実行（SFTP から取得）／`{"sftpCheckOnly": "true"}` → 今までどおり最初に判定（SFTP 接続の確認だけ）。
- coopbatch でやること: ① `docs/coop/overview.md` の「オンデマンド実行（Step Functions）」の表と「リカバリー走行」の手順を新しい動きに直す（手順 3 は「オンデマンド実行を入力なしで起動する」） ② `cf/ecs-batch-ondemand-cf.yaml`（coopinf 版より古く sftpCheckOnly が無い）を、coopinf の修正がマージされたらその内容に同期し、冒頭に「正本は coopinf/cf/ecs-batch-ondemand-cf.yaml。デプロイは coopinf から行う」と書く。
- **段取り**: coopinf の PR が出て（マージされて）から着手する。coop に受領と直す箇所を返信し、coopinf の PR 番号の連絡を頼んだ。
- coop から: 直す箇所はそのとおりで問題なし。coopinf-cd が PR を作ったとき（番号）とマージしたときに coopbatch-9c へ直接知らせる（届かなければ coop が転送）。→ マージの連絡を受けてから着手する。
- coopinf-cd から: Draft PR alphacmc/coopinf#61 を作成（未マージ）。対象は cf/ecs-batch-ondemand-cf.yaml（CheckRecoveryMode の条件反転、Default を RunEcsTaskRecovery に、説明文の修正）。マージ後にあらためて連絡が来る。coopbatch の cf 複製の同期はマージ後に行う。
- coopinf-cd から: **coopinf #61 がマージ**（2026-11-16 17:58 JST）、stg・prd のスタックは更新済み。→ coopbatch で対応: ブランチ `feature/sync-ondemand-recovery-default`、Draft PR https://github.com/alphacmc/coopbatch/pull/39 。`cf/ecs-batch-ondemand-cf.yaml` を coopinf main（d9642ae）と同期（冒頭に「正本は coopinf。デプロイは coopinf から。参照用の複製」の注記のみ追加、それ以外は diff で一致を確認）、`docs/coop/overview.md` の実行入力の表とリカバリー手順 3（「オンデマンド実行を入力なしで起動する」）を修正。注入される SFTP_CHECK_ONLY はバッチが読む（src/config.ts:116）。coopinf・coop に完了を連絡。
- これにより、stg の動作確認（11 月分の K020 の取り込み直し）は、オンデマンド実行を入力なしで起動すればリカバリー走行になる。

## 2026-11-17 PR ＃38・＃39 のマージと、stg の動作確認の進め方

- ユーザーが **PR #38（バッチ 1.4.0）と PR #39（オンデマンド実行の既定変更への対応）をマージ**（main は c430d92）。
- **承認（ユーザー）**: stg の動作確認は、本番の 11 月分の請求CSV（K020。ガス `110610997IF-K020_2026110708091201.csv`、でんき `122128326IF-K020_2026110609272401.csv`）を stg で取り込み直す案で進める。
- Claude が用意したもの（ブランチ `feature/bill-usage-month-stg-verify`）:
  - `db/sql/2026-11-bill-usage-month/03_verify_reimport.sql`（読むだけ）: 取り込み直す前後で実行して見比べる。① 請求年月 2026-11 の行を利用年月・発行種別・料金年月ごとに数える（新しいバッチが書いた行は fee_year_month が入るので区別できる） ② 同じ契約で請求年月 2026-11 の行が 2 つ以上ある契約の数 ③ 確認用の契約（ガス 910240391、でんき 912292734）の行。手元の使い捨て PostgreSQL 16 にダミーの行を入れて、エラーなく動くことを確認した。
  - README に手順を追記: 取り込み前に 03 を実行 → stg の `treated/` に同名ファイルが無いか確認（あると読み飛ばされる。あれば名前に `_stgverify` を付けて置く。種別は名前に K020 を含むかで決まる） → 本番 `treated/` の2ファイルを stg の `untreated/` へコピー → `coop-stg-batch-ondemand` を入力なしで起動（リカバリー走行） → 成功・`treated/` への移動・エラーCSV（大半が「請求情報重複」で正常）・03 の再実行・画面を確認。
  - 期待: ガス 約 14 行（発行種別 02、料金年月 202610、利用年月 2026-11）、でんき 約 18 行（料金年月 202609、利用年月 2026-09）が新しく入る。でんき 912292734 の利用年月 2026-10 の行は9月分の中身のまま（段階2の範囲）。
- 前提として確かめたこと: 行の重複エラーは行を読み飛ばすだけでジョブは成功し、元ファイルは `treated/` へ移る（`untreated/errors/` にエラーCSV）。再投入ファイル（`_errorfixNN`）を作るのは速報値の「契約情報なし」だけで、請求では作られない。
- 実行はユーザー（stg の S3 と DB は Claude の権限では見られない。本番バケットも 2026-11-17 時点で Claude からは AccessDenied）。

## 2026-11-17 空の日付項目の調査結果（coopcdeweb からの依頼）

- **結果（ユーザーが stg の DB で実行。stg は本番 2026-11-15 の複製）**: gas_bill / denki_bill とも、使用期間開始年月日・使用期間終了年月日・検針年月日の **3 項目すべて、NULL・空文字の行は 0 件**。
- 本番 CSV 2 年分を取り直して CSV 側まで確かめるかは、ユーザーの判断待ち（Claude の意見: DB に空の行が無ければ画面は 500 にならないので、取り直しは要らない）。coopcdeweb は 0 件なら記録だけにすると言っていた。
- coopcdeweb-1a に結果を連絡した。

## 2026-11-17 stg の取り込み直し（1回目）: 古いバッチで動いていた

- ユーザーが手順どおり実行した: 取り込み前の 03 → stg の `treated/` に同名ファイルなしを確認 → 本番 `treated/` の2ファイルを prd-manage からリレーバケット `coop-migration-relay-725011976834/tmp/` 経由で stg の `untreated/` へ → オンデマンド実行（admin コンソール）→ 取り込み後の 03。
- 結果: 新しいバッチが書いた行（fee_year_month あり）は 0。請求年月 2026-11 に、利用年月が NULL の行（でんき 15、ガス 6）が増えただけ。同じ請求年月の複数行は 0 のまま、確認用の契約も変化なし。
- Claude の判断: 利用年月が NULL の行が入れた＝NOT NULL になっていない＝**stg は DDL-2 がまだ**。料金年月・発行種別も NULL＝**1.4.0 ではなく古いバッチ（1.2.0）が動いた**（1.4.0 は CSV からこの2列を必ず書き、利用年月も NULL にしない）。21 行は本番 11/15 時点で「契約情報なし」だった契約の行と思われる。DDL-2 が NOT NULL の前に「請求年月 - 1」で埋め直すので、そのまま進めてよい。
- ユーザーに確認を依頼: `00_check.sql` の主キー、CloudWatch の実行ログの `Version:`。
- やり直しの手順（提示）: pg_dump 退避 → 02_ddl2 → 00_check → バッチ 1.4.0 を stg に反映 → リレーバケットの `tmp/` から名前に `_stgverify` を付けて `untreated/` へ（元の名前は stg の `treated/` に入ったため）→ 03 → オンデマンド実行（入力なし）→ 03。確認後、リレーバケットの `tmp/` の2ファイルと stg の `untreated/errors/` のエラーCSV（本番の請求の中身）を消す。
- DDL-2 までは stg に利用年月 NULL の行が 21 行あり、その組合員の画面（coopcdeweb 1.9.0）はエラーになりうるので、画面確認に使わない。
- README の手順に「0. 前提（DDL-2 済み・バッチ 1.4.0）を確かめる」を追加した。
- PR #40（手順と確認用 SQL）は 2026-11-17 07:24 JST にユーザーがマージ済みだった。push 前の確認（OPEN でなければ止まる形）で止まり、追記分は main から `feature/stg-reimport-precheck` を作って Draft PR #41 にした。

## 2026-11-17 1回目の取り込み直しで入った行を戻すか（提案・ユーザーの了承待ち）

- ユーザーの問い: 1回目で更新が入ったので戻す必要があるか。
- Claude の提案: 全体を戻す必要はない（DDL-2 が利用年月の NULL を「請求年月 - 1」で埋めるので、そのままでも進められる）。ただし、2回目の期待値（ガス約 14・でんき約 18）は本番 11/15 の状態が前提で、消せば 21 行も新しいバッチが新しいルールで入れ直すので、**DDL-2 の前に、利用年月が NULL の 21 行（ガス 6・でんき 15）だけを消す**のを勧めた。取り込み前は NULL が 0 件だったので、対象はこの 21 行だけ。
  - 確認（読むだけ）: ① 利用年月 NULL の件数が 6・15 ② 既存行（利用年月あり）で updated_at >= '2026-11-16 15:00'（UTC＝JST 11/17 0時）が 0（古いバッチは通し番号が新しいときしか上書きしないので 0 のはず）。② が 0 でなければ消さずに結果を共有し、退避ダンプからの戻しを検討する。
  - 削除: BEGIN → DELETE ... WHERE usage_year IS NULL OR usage_month IS NULL（6・15 を確認）→ COMMIT。
  - その後は既定のやり直しの手順（pg_dump → DDL-2 → バッチ 1.4.0 → `_stgverify` を付けて配置 → 確認）。S3 は `treated/` の2ファイルは `_stgverify` で回避、`untreated/errors/` のエラーCSVは確認後に削除。

## 2026-11-17 stg の 21 行の削除と DDL-2 の実行

- **承認・実行（ユーザー）**: 提案どおり、利用年月が NULL の行を削除（gas_bill 6・denki_bill 15。件数一致で COMMIT）。上書き確認（updated_at）の②はこの時点では未実行。
- **stg の DDL-2 を実行**: `02_ddl2_switch_pk.sql`（UPDATE 0 / 0、主キーの確認 DO 通過、COMMIT）→ `00_check.sql`: 主キーは両テーブルとも `member_code, contract_number, usage_year, usage_month`、usage_year/usage_month は NOT NULL、fee_year_month/issue_type は NULL 可、行数 gas_bill 753,680 / denki_bill 2,390,961（本番 11/15 と同じ）、利用年月が空 0 件。→ **stg の DDL-2 完了。**
- DDL-2 前の pg_dump の有無はログに無く、ユーザーに確認中（stg なので無くても本番 11/15 のバックアップから戻せる）。updated_at >= '2026-11-16 15:00'（UTC）が 0 件かの確認も依頼中。
- **次の段取り**: stg のスケジュール実行の前に、バッチ 1.4.0 を stg に反映する（DDL-2 後に古いバッチで請求を書くと NOT NULL 違反で Writer エラー → `temporary/`）。その後、`Version: 1.4.0` を確認 → `_stgverify` を付けて配置 → 03 → オンデマンド実行（入力なし）→ 03。
- coopcdeweb-1a に stg の DDL-2 完了を連絡した。
- coopcdeweb から返信: DDL-2 は 1.9.0 に影響なし（請求は読むだけ。Prisma 側は利用年月を NULL 可のままだが、DB が NOT NULL でも読み込みは問題ない）。stg の直近 6 時間のログに ERROR・Prisma エラーなし（会員画面へのアクセスもなし）。取り込み直しが終わったら連絡を受けて、ガス 910240391・でんき 912292734 の画面を確認する。

## 2026-11-17 stg の取り込み直し（2回目）: 何も変わらなかった（調査中）

- ユーザーの回答: stg の DDL-2 の前の **pg_dump は取っていない**（stg なので本番 11/15 のバックアップから戻せる。**prd では DDL-1・DDL-2 とも実行前の pg_dump を必ず取る**）。
- 上書き確認: updated_at >= '2026-11-16 15:00'（UTC）は gas_bill・denki_bill とも 0 件 → 1回目の古いバッチは既存行を上書きしていない。
- 2回目: 取り込み前の 03 → バッチ実行 → 取り込み後の 03 で、**結果がまったく同じ**（新しいバッチが書いた行 0、同じ請求年月の複数行 0、確認用の契約も変化なし）。1回目に入った 21 行（削除済み）すら入っていないので、請求ファイルが1件も処理されていない。
- 考えられる原因（Claude）: ① バッチがまだ 1.4.0 でない（古いバッチだと 21 行の書き込みが NOT NULL 違反で Writer エラー → ステップ失敗 → ファイルは `temporary/`） ② ファイルが `_stgverify` 付きで `untreated/` に置かれていない（元の名前は `treated/` にあるので読み飛ばし → 0 件でスキップ） ③ 1.4.0 で別のエラー。
- ユーザーに確認を依頼: CloudWatch `/ecs/logs/coop-stg-batch-loggroup` の該当実行の `Version:`・`Files by type:`／`No files required processing found`・`Skipping treated file`・ERROR、S3 の `untreated/`・`temporary/`・`treated/` の `_stgverify` の有無。Claude の AWS 認証は別アカウントで stg のログ・S3 は見られない。

## 2026-11-17 2回目の原因: バッチ 1.4.0 がまだ反映されていなかった

- ユーザーの報告: **1.4.0 はビルドしただけで、バッチ実行に反映されていなかった。バッチ実行スタック（coop-ecs-batch-stg）を 1.4.0 に更新した。** もう一度やり直す。
- 推定: 2回目は古いバッチが DDL-2 後の DB に書こうとして、利用年月 NOT NULL 違反で請求のステップが失敗し、ファイルは `temporary/` に移った（DB 変化なしと合う）。
- **やり直しの手順（提示）**: ① `temporary/` と `untreated/` でファイルの場所を確認し、`temporary/` にあれば `untreated/` へ戻す（名前に `_stgverify` が付いていなければ付ける）② オンデマンド実行（入力なし）③ ログで `Version: 1.4.0` と `Files by type: … BILL=2` ④ 03。最後にリレーバケット `tmp/` の2ファイルと `untreated/errors/` のエラーCSVを消す。
- 期待の更新: ガス約 14（利用年月 2026-11）・でんき約 18（利用年月 2026-09）に加え、削除した 21 行（ガス 6・でんき 15）も新しいバッチで入る（主に利用年月 2026-10）。同じ請求年月の複数行の契約はガス約 14・でんき約 18。
- **本番の当日への反映**: README の手順に「バッチの反映はビルドだけでは足りず、`coop-ecs-batch-{env}` スタックの更新が必要。反映後に `Version: 1.4.0` を確認」「DDL-2 からスタック更新までの間にバッチを動かさない」を追加した。

## 2026-11-17 stg の取り込み直し（3回目）: 期待どおり（stg の動作確認 合格）

- ユーザーが stg のバッチ実行スタックを 1.4.0 に更新してから再実行。取り込み後の 03:
  - でんき: 利用年月 2026-09・発行種別 01・料金年月 202609 が 18 行（遅れて届いた前月分）、利用年月 2026-10・料金年月 202610 が 15 行（削除した行の入れ直し）、既存 68,262 行は変化なし。
  - ガス: 利用年月 2026-11・発行種別 02 が 14 行（料金年月 202610 が 7 行＝開始月＝料金年月なので +1、料金年月 202611 が 7 行＝そのまま）、利用年月 2026-10・料金年月 202610 が 6 行（入れ直し）、既存 18,725 行は変化なし。
  - 同じ請求年月 2026-11 の行が2つ以上ある契約: ガス 14・でんき 18（期待どおり）。
  - ガス 910240391: 利用年月 2026-10（通常分 9/10〜10/13、4,371円）と 2026-11（最終請求 10/14〜10/31、2,744円）に分かれた。
  - でんき 912292734: 利用年月 2026-09（8/24〜9/23、8,563円）が新しく入った。2026-10 の行は9月分の中身のまま（画面では9月分が2か月続けて出る。10月分は捨てられたまま。段階2の範囲）。
- → **stg でのバッチ 1.4.0 の動作確認は合格**（Claude の判断）。
- coopcdeweb-1a に画面確認を依頼した（2 契約の見え方と、912292734 の 2026-10 が9月分のままなのは想定どおりであることを伝えた）。
- 残りの後片付け（ユーザー）: リレーバケット `tmp/` の2ファイル、stg の `untreated/errors/` のエラーCSVを削除。

## 2026-11-17 coopcdeweb の stg 画面確認の結果と調査依頼 2 点

- coopcdeweb-1a の報告（ユーザー確認済み）: でんき 912292734 は想定どおり（2026-10 に9月分の中身があるのは段階2で直す前提）。ガス 910240391 は請求は想定どおりだが、画面に「速報値（未確定）」が出る。
- 依頼【1】ガス 910240391 の速報値: early_bill の中身、最終請求（10/14〜10/31）と期間・金額が重なるか、確定後に速報値を消す／画面から外すべきか、旧システムでの扱い。
  - Claude の調査（コード）: 旧 coopcdebatch も coopbatch も、速報値は (組合員, 契約, 調整年月, 停止フラグ) で追加か更新するだけで、**確定の請求が届いても early_bill を消す・更新する処理は無い**。解約の速報値（stop_flag = '1'）は請求年月を「調整年月 + 1 か月」にする（旧・新とも同じ）。画面は「確定の請求の最大の請求年月より後」の速報値を出すので、解約の速報値の請求年月が最終請求の請求年月より後になると、確定後も出続ける。今回の取り込み直しや 1.9.0 で出始めたものではない、という coopcdeweb の見立てと一致。
- 依頼【2】でんきで利用年月の行に前の月の中身が入っている行（段階2の対象）の stg での件数と、2026-09 の 18 行の契約以外にもあるか。
  - Claude の見立て: DB だけで確実に分かるのは、取り込み直しで正しい月の行が入った 18 契約だけ（使用期間が同じで利用年月が違う行の組）。それより前の月は、遅れ請求の行が捨てられているので DB 内に対になる行がなく、元CSVとの突き合わせ（段階1）が必要。段階1（本番 11/16 時点）では、でんきの通常月に遅れ請求の古い月の中身が入っている行は 66 行（更新 85 行の大半）で、それ以前の月にもある。目安として「使用期間の終わりの月が利用年月より前」の行を月ごとに数える。
- 確認用 SQL `db/sql/2026-11-bill-usage-month/04_check_early_bill_and_denki_fix.sql`（読み取りのみ）を追加。手元の使い捨て PostgreSQL 16 でエラーなく動くことを確認。ユーザーに stg での実行を依頼し、結果を coopcdeweb に返す。
- 速報値を確定後に消すか・画面で外すかは、結果を見てから方針を相談する（未決）。

## 2026-11-17 04 の実行結果（stg）と、速報値が出続ける原因

- 1-a / 1-b（ガス 910240391）:
  - 解約の速報値（調整年月 2026-11、stop_flag 1、請求年月 2026-12、10/14〜10/31、14㎥、2,744円）が、確定した最終請求（gas_bill 利用年月 2026-11・請求年月 2026-11・発行種別 02・料金年月 202610、10/14〜10/31、2,744円）と**期間も金額もまったく同じ**。同じ請求が「確定」と「速報値」の2回、画面に出ている。
  - 通常の速報値（stop_flag 0）は、調整年月 = 確定の請求年月（例: 調整 2026-11 ↔ gas_bill 請求年月 2026-11・利用年月 2026-10）で、確定が届くと「最大の請求年月より後」でなくなり、消える。
- 原因（Claude）: 速報値の請求年月の決め方（解約は調整年月 + 1）と、K020 の最終請求の請求年月（今回は通常分と同じ 2026-11 の K020 で届いた）がずれている。今までは、この最終請求が同じ請求年月の重複で捨てられていたので、速報値が確定の代わりに出ていた（重複にはならなかった）。主キーを利用年月に変えて最終請求が入るようになったため、**同じ請求が2回出る形が新しく見えるようになった**（coopcdeweb の「前から同じ」の見立てを一部訂正。速報値が出ること自体は前からだが、確定と二重になるのは今回の修正の結果）。
  - 最終請求が翌月の K020 で届く（請求年月 = 調整年月 + 1）契約では、今までどおり確定で速報値が消える。
- 1-c: 解約の速報値の請求年月が、確定の最大の請求年月より後の契約は、ガス 422・でんき 309（CURRENT_YM の条件なし。古いものは画面の CURRENT_YM の条件で出ない。最終請求が捨てられていて段階2で入る契約も含む）。
- 2-a: でんきで使用期間が同じで利用年月が違う行の組は、旧行 2026-10 ↔ 新行 2026-09 の 18 行だけ（DB だけで特定できるのは今回の 18 契約のみ、の見立てどおり）。
- 2-b: 目安のクエリは毎月 120〜230 行出て、段階1の 66 行（2年分）より桁違いに多い。検針期間の都合の正常な行がほとんどで、**目安として使えない**。月ごとの件数は、段階1のやり直し（元CSVとの突き合わせ）で出す。
- 対策の案（Claude、ユーザーの判断待ち）:
  - 案A（推奨）: 画面の速報値の比較を「速報値の請求年月 - 1」と「確定の最大の利用年月」に変える（coopcdeweb）。通常の速報値は今と同じ結果（調整年月 - 1 = 確定の利用年月）、解約の速報値は最終請求の利用年月（発行種別 02 の +1 で求めた月）と一致して消える。DB・バッチは変えない。ただし、16 日の決定「速報値の比較は bill_year / bill_month のまま」を変えることになる。
  - 案B: バッチで、確定の請求が届いたら同じ期間の速報値を消す。旧 coopcdebatch に無い動きで、速報値のキー（調整年月）と確定のキーの対応づけも要るので、推奨しない。
  - 案C: 何もしない。CURRENT_YM が 2027-01 になれば出なくなるが、それまで同じ請求が2回出る。

## 2026-11-17 速報値の二重表示は案Aで対応する（決定）

- **決定（ユーザー）: 案A。** 画面の速報値の比較を「速報値の請求年月 - 1」と「確定（gas_bill / denki_bill）の最大の利用年月」に変える。2026-11-16 の決定「速報値の比較は bill_year / bill_month のまま」はこれで変更。
- 修正は coopcdeweb のみ。DB・バッチ（coopbatch）は変えない。案B（バッチで速報値を消す）・案C（何もしない）はやらない。
- 利用年月が空の確定の行は、画面の既存ルールどおり「請求年月 - 1」で扱う（DDL-2 の後は空は無い）。
- coopcdeweb-1a に着手を依頼した。方式案はそちらのセッションでユーザーの了解を取ってから実装する。

## 2026-11-17 coopcdeweb が案Aを実装（Draft PR alphacmc/coopcdeweb＃142）

- coopcdeweb-1a の報告（ユーザーの了解は coopcdeweb のセッションで取得済み）:
  - 変更点: 速報値を出すかの比較を「速報値の請求年月 - 1」と「その契約の確定の最大の利用年月」に変えた。利用年月が空の行は「請求年月 - 1」で扱う。
  - 変えていないもの: CURRENT_YM の条件（請求年月で比較）、DB、バッチ。
  - バージョン: 1.9.0 のまま作り直す（ユーザーの指示）。
  - でんきの遅れ請求の契約では、確定がまだ無い月の速報値が出るようになる。ユーザーの判断は「異例なので当面説明がつく」。issue alphacmc/coopcdeweb#141 に記録。
- 段取り: ユーザーが #142 をマージ → CodeBuild でイメージを作り直し → stg に反映 → coopcdeweb がガス 910240391 の速報値が消えることを画面で確認して連絡。
- coopbatch 側の作業は無し。本番は coopcdeweb 1.9.0（作り直し版）を DDL-1 の後に出す（順番は変わらない）。

## 2026-11-17 案Aを入れた coopcdeweb 1.9.0 の stg 確認（合格）

- coopcdeweb-1a の報告: #142 はマージ済み。CodeBuild で 1.9.0 を作り直し、stg のサービスを再起動。ユーザーが画面で確認し、ガス 910240391 の速報値が消えた。ほかの組合員の表示は変わらない。再起動後の stg のログにエラーなし。
- → stg での確認はこれで全部終わり（バッチ 1.4.0・DDL-1/DDL-2・画面 1.9.0）。
- prd は coopcdeweb 1.8.2 のまま。prd の順番は変わらない: ① DDL-1（00_check → pg_dump 必須 → 01 → 00_check）→ ② coopcdeweb 1.9.0 → ③ 同じ日に DDL-2（00_check → pg_dump 必須 → 02 → 00_check）→ coop-ecs-batch-prd スタックを 1.4.0 に更新 → `Version: 1.4.0` を確認（DDL-2 からスタック更新までバッチを動かさない）。11 月中、K020 が届く 4〜7 日を避ける。日取りはユーザーが決める（未定）。

## 2026-11-17 本番の 11 月分で捨てられた請求の補正（coop からの依頼。対象の確定と進め方を相談中）

- coop-c6 から依頼（ユーザー承認済みとのこと）: 本番リリース（DDL-1 等）の前に、11 月分 K020 で「請求情報重複」で捨てられた請求を DB で補正する。10 月分は保留。方式:
  - でんきの遅れ請求: 既存行（請求年月 2026-11、中身は料金年月 202609）の請求年月を 2026-10 に UPDATE。捨てられた行（料金年月 202610）を請求年月 2026-11 で INSERT。
  - ガスの解約の最終請求（発行種別 02）: 既存行（通常分、2026-11）は触らず、最終請求を請求年月 2026-12 で INSERT。
  - ガスの訂正（削除サイン 1）: 対象外。
  - 段取り: 対象の確定 → 補正 SQL（事前確認・pg_dump・1トランザクション・件数チェック・事後確認）→ stg で予行（本番の最新ダンプを戻す。要相談）→ 本番実行（ユーザー）→ 画面確認 → 補正一覧を残し、段階2で除外。
- Claude の調査（`coop` プロファイルで本番の 11 月分 K020・エラーCSV・errorfix00・日次ダンプ 11/17 01:00 を scratchpad に取得。手元の使い捨て PostgreSQL に請求3テーブルだけ戻して確認）:
  - エラーCSV（11/06・11/07）の「請求情報重複」は 34 行で、すべて元の K020 の行と完全に一致。でんき 18（すべて料金年月 202610・発行種別 01。残っているのは 202609 の行）、ガス 16（発行種別 02 が 14、削除サイン 1 が 2＝910263458・912815697、対象外）。
  - **でんき 912531098・912521584 の 2 契約は 11/16 に手で補正済み**（9 月分の行が請求年月 2026-10 に移され、10 月分が errorfix00 から請求年月 2026-11 で入っている。依頼の方式と同じ形）。→ **でんきの残りは 16 契約**。
  - でんきの 16 契約は、いずれも請求年月 2026-10 の行が無い（主キーはぶつからない）。
  - ガスの 14 契約は、いずれも請求年月 2026-11 に通常分があり、2026-12 の行は無い（gas_bill 全体でも 2026-12 以降は 0 行）。解約の速報値（請求年月 2026-12）は、14 契約とも最終請求と期間・金額が同じ。補正後は、1.8.2（請求年月で比較）でも 1.9.0（案A）でも速報値は出なくなる。
- 進め方の案（Claude、ユーザーの確認待ち）:
  - INSERT の値は、バッチと同じ変換（`csvRowBillNormalized` と bill-processor の列の対応）を使うスクリプトで元の K020 の行から作る。検証として、同じスクリプトで 11/16 に errorfix00 で入った 2 行も作り、本番の行と一致することを確かめる。
  - 予行は、stg を戻す代わりに、手元の使い捨て DB（本番 11/17 ダンプ）で行う案を推奨（stg は DDL-2 済みで、戻すと stg の確認環境が壊れるため）。
  - 補正の型の違い（実際の請求年月と DB の請求年月がずれる）: でんきの 9 月分は実際は 11 月請求だが 2026-10 に、ガスの最終請求は実際は 11 月請求だが 2026-12 に入る。DDL-1 の「請求年月 - 1」で利用年月は正しくなる。料金年月・発行種別は空（既存行と同じ）。

## 2026-11-17 11 月分補正: 方針の承認と、補正 SQL の作成・予行

- **決定（ユーザー）: ① INSERT の値は、バッチと同じ変換で元の K020 の行から作る（OK） ② 予行は stg ではなく手元の使い捨て DB で行う。** → stg は戻さない（DDL-2 済みの確認環境のまま）。
- 作成: `db/sql/2026-11-prd-nov-bill-fix/`（generate-fix-sql.ts・README・targets.csv）。生成した `fix_prd_nov_bill.sql` は請求の中身を含むので、リポジトリには置かず scratchpad（prd1117/out）に置く。
- 予行（本番 11/17 01:00 ダンプの請求3テーブルを手元の PostgreSQL 16 に戻して実施）:
  - 変換の検証: 11/16 の errorfix00 の 2 行と、対象の契約の残った行（でんき 16・ガス 14）を同じ変換で作り、日時以外の全列が DB の行と一致（32 行）。
  - dryrun → ROLLBACK で件数変わらず。本実行 → UPDATE 16、追加 でんき 16・ガス 14、COMMIT。レビュー（CRITICAL・HIGH なし）の MEDIUM 1・LOW 3 を反映して予行をやり直し、既定 ROLLBACK・`-v commit=1` で COMMIT・2 回目と DDL-1 の後は止まることを確認（gas 753,680 → 753,694、denki 2,390,963 → 2,390,979）。2 回目は事前の確認で止まる。
  - 補正後に旧主キー（請求年月）を付け直して重複なし、続けて DDL-1・DDL-2 も通る（利用年月が空 0）。でんきは利用年月 2026-09 = 9 月分・2026-10 = 10 月分、ガスは 2026-10 = 通常分・2026-11 = 最終請求。解約の速報値は 1.8.2・1.9.0 のどちらでも出ない。
- 本番の順番: **補正（DDL-1 の前）** → DDL-1 → coopcdeweb 1.9.0 → DDL-2＋バッチ 1.4.0（同じ日）。補正の日取りはユーザーが決める（未定）。補正の手順: SQL をリレーバケット経由で coop-prd-manage へ → pg_dump → `psql`（確認のみ、既定で ROLLBACK）→ `psql -v commit=1` → 画面確認（coopcdeweb）→ 置いた SQL を消す。
- 本番から取得したデータ（K020・エラーCSV・ダンプ）と手元の DB は削除済み。生成した SQL（scratchpad）は本番実行の後に消す。

## 2026-11-17 11 月分補正: stg での確認は要るか（stg での予行はしないことに決定）

- Claude の回答: stg での予行は不要と考える。
  - stg は DDL-2 済みで、この SQL は前提の確認（DDL-1 の前）で止まる。
  - stg で予行するには本番ダンプを戻す必要があり、stg の画面 1.9.0 が動かなくなり、DDL-1・DDL-2 もやり直しになる。
  - 手元の予行で、本番のデータでの結果と、その後の DDL-1・DDL-2 まで確かめている。
- 手元の予行で確かめていないことは、次で補う（提案）:
  - manage サーバの psql と Aurora で動くか（`\if`・`\gset`・`\encoding`・ロック権限）→ 本番で、まず `-v commit=1` なしで流す（既定で ROLLBACK し、何も変わらない）。
  - 補正した行の本番の画面 1.8.2 での見え方 → 11/16 に同じ形で手で補正済みのでんき 912531098 を、今の本番の画面で見る。
  - 任意: stg の manage サーバでこの SQL をそのまま流し、前提の確認で止まるまでの部分（psql の機能・ロック）を、何も変えずに確かめる。
- → **ユーザー「了解しました」: stg での予行はしない。** 本番では、まず `-v commit=1` なしで流して確認し、そのあと `-v commit=1` で反映する。本番の補正の日取りは未定（ユーザーが決める）。

## 2026-11-17 11 月分補正を本番で実施中

- ユーザー: 本日、本番で補正を行う。手順 2（退避）は `bill_before_novfix_$(date +%Y%m%d_%H%M).dump` の名前でカレントディレクトリに取る（Claude の提案を README に反映済み）。「このあと 4（反映）を実施する」。
- ユーザーの確認: でんき 912531165 は対象か → Claude: 対象（でんき 16 契約の 1 つ。9 月分 08/24〜09/23 を請求年月 2026-10 へ移し、10 月分 09/24〜10/23 を 2026-11 で追加）。似た番号の 912531098 は 11/16 に手で補正済みで対象外。
- 反映の前に、手順 3（`-v commit=1` なし）で「前提の確認 OK」「事前の確認 OK（でんき 16、ガス 14）」「事後の確認 OK」を確かめるよう伝えた。
- この後: 反映の結果（`*** COMMIT しました ***`）→ coopcdeweb に画面（1.8.2）の確認を依頼 → manage サーバとリレーバケットの SQL を削除 → scratchpad の生成 SQL を削除。

## 2026-11-17 ガス 910238133 の 9 月分の最終請求の補正 SQL（ユーザー依頼）

- ユーザーの確認: 本番 DB の 910238133 は 07-09〜08-10（請求年月 2026-09）の行まで。2026-09 の K020 にある解約の最終請求（発行種別 02、料金年月 202609、08-11〜09-02、23 日、使用量 0、563 円）が入っていない（11 月分と同じ「ガスの解約の最終請求」の型）。9 月分のエラーCSVはバケットに残っていない（残っているのは 10 月分から）。
- ユーザーの依頼で、この 1 件の補正 SQL を作成: 最終請求を請求年月 2026-10 で入れる（11 月分と同じ形。DDL-1 で利用年月は 2026-09 になり、新しいバッチの求め方〈料金年月 202609、開始月 08 ≠ 料金年月なのでそのまま〉と一致）。値は 11 月分と同じ変換（generate-fix-sql.ts の関数を使用）で 9 月の K020 から作った。前提・事前・事後の確認、ロック、既定 ROLLBACK（`-v commit=1` で COMMIT）は 11 月分と同じ。
- 使い捨て DB での予行は、この PC のアプリケーション制御ポリシーで initdb.exe がブロックされるようになったためできていない。本番で `-v commit=1` なしで流して確認してから反映する。
- この契約も段階2で除外する。9 月・10 月分のほかの契約は、引き続き保留（段階2で扱う）。
- SQL は scratchpad（sep910238133/fix_910238133_sep.sql）に置き、画面に表示した。本番で実行した後に消す。

## 2026-11-17 なぜ 910238133 が 11 月分の補正に入らなかったか（説明と、範囲を広げるかの相談。ユーザーの判断待ち）

- ユーザーの質問: ガスの補正は、捨てられた解約の最終請求を埋めるためだったのに、なぜ 910238133 は入らなかったのか。
- Claude の説明: 補正の範囲は、coop の依頼どおり「11 月分（11/06・11/07 に取り込んだ K020）のエラーCSVで捨てられた分」だけ（10 月分は保留）。910238133 の最終請求は 9/5 の K020 で捨てられたので範囲外。段階1（11/16、過去2年）では、ガスの最終請求で捨てられたものが 258 件あり、今回の 14 件と 910238133 はその一部。残りは段階2で扱う計画。
- 相談（ユーザーの判断待ち）: 直近の 9・10 月分も、本番リリース前に同じ方法で埋めるか。10 月分はエラーCSVが残っているので 11 月分と同じ手順で抜き出せる。9 月分はエラーCSVが無いが、K020 と本番 DB のダンプの突き合わせで抜き出せる。10 月分の保留は coop との取り決めなので、広げるかはユーザーが決める。広げる場合は、まず対象を抜き出して件数を報告する。

## 2026-11-17 9・10 月分の対象の抜き出し（ユーザー依頼）と、912531657 の扱いの相談

- **決定（ユーザー）: 9 月分・10 月分も対象を抜き出す**（10 月分の保留を解き、範囲を広げる）。
- 抜き出し方: 9・10 月の K020（10 ファイル）の各請求（削除サイン 0、同じ使用期間は通し番号の大きい方）を、本番 DB（11/17 01:00 ダンプ、pg_restore で請求2テーブルをテキストに出して比較）と使用期間で照らし合わせ、DB に無いものを拾った。10 月分はエラーCSV（10/06・10/07）とも一致。9 月分はエラーCSVが残っていない。
- 結果: 10 契約。11 月分の 30 契約とは重ならない。移す先・入れる先の請求年月はすべて空き。
  - 9 月: ガスの最終請求 910238133・910324778・911015319、でんきの遅れ請求 912340249、でんき（特殊）912531657。
  - 10 月: でんき（解約）912419582、でんきの遅れ請求 912530158・912415268・912530761・912534424。10 月のエラーCSVのガス 910263458 は削除サイン 1 で対象外。
- 置き方の原則（提案）: 「新しいバッチが求める利用年月 + 1 か月」の請求年月に置く（DDL-1 の「請求年月 - 1」で正しい利用年月になる）。11 月分の補正もこの原則に合っている。
- 相談（ユーザーの判断待ち）: でんき 912531657 は、4 月分（03/24〜04/23）と解約の最終請求（04/24〜04/27）が 9 月の K020 で届いた。DB では 4 月分が請求年月 2026-09（画面では利用年月 2026-08）。案1（推奨）: 原則どおり 4 月分を 2026-05 に移し、最終請求を 2026-06 に入れる（画面で 2026-04・2026-05 になる）。案2: ほかと同じく 1 か月だけずらして 2026-08・2026-09。
- 910238133 は、先に出した単独の SQL ではなく、この 10 件をまとめた SQL に含める（単独の SQL は流さない）。
- 使い捨て DB が作れない（initdb がアプリケーション制御ポリシーでブロック）ので、SQL 全体の予行はできない。値の変換は、残っている行を作り直してダンプの行と比べる方法で確かめる。
- → **決定（ユーザー）: 912531657 は案1**（4 月分を請求年月 2026-05 に移し、最終請求を 2026-06 に入れる。画面で利用年月 2026-04・2026-05）。10 契約をまとめた補正 SQL を作る。
- 9・10 月分の補正 SQL を作成（`generate-sepoct-fix-sql.ts`。生成物 `fix_prd_sepoct_bill.sql` は scratchpad の sepoct/out）。ガス 3・でんき 7（移動 7、追加 10）。912531657 は 2026-09 → 2026-05 に移し、最終請求を 2026-06 に入れる。
  - 検証: 残っている 10 行を同じ変換で作り、本番ダンプの行と全列一致。SQL 全体の予行はできていない（initdb がブロックされるため）。本番では `-v commit=1` なしで流して確認してから反映する。
  - 前回の説明の「でんきの 6 件」は誤りで、正しくは 7 件（912340249・912531657・912419582 と遅れ請求 4 件）。
  - 先に出した 910238133 単独の SQL（scratchpad の sep910238133）は不要になったので削除。この SQL に含めた。単独の SQL を本番で流していた場合は、この SQL は事前の確認で止まるので、その時は 910238133 を外して作り直す。
  - 本番から取得したデータ（K020・エラーCSV・ダンプ）は削除済み。
- ユーザーが本番で `fix_prd_sepoct_bill.sql` を確認のみ（`-v commit=1` なし）で流したところ、事前の確認で `gas:910238133` が想定と違うとして止まった（17:39。何も変わっていない）。**910238133 は単独の SQL で既に反映済み**だったため。→ 910238133 を外して作り直した（ガス 2・でんき 7、移動 7・追加 9・書いた行 16）。作り直しの際に K020 を取り直し、作った後に削除した。

## 2026-11-17 9・10 月分の補正を反映。912419582 で速報値が二重に出る件（相談中）

- ユーザーが本番で `psql -v commit=1 -f fix_prd_sepoct_bill.sql` を実行（9・10 月分の補正を反映。ガス 2・でんき 7）。
- ユーザーの報告: でんき 912419582 で、最終請求と速報値が同時に画面に出ている。
- Claude の調査（本番 11/17 01:00 ダンプの early_bill。補正では速報値は変えていない）:
  - 912419582 の解約の速報値（stop_flag 1）は、調整年月 2026-10、請求年月 2026-11（+1）、08/24〜09/10、514 円。確定の最終請求（補正で請求年月 2026-10 に入れた）と期間・金額が同じ。確定の最大の請求年月 2026-10 より後なので出る（1.8.2）。1.9.0（案A）でも、2026-11 - 1 = 2026-10 > 確定の最大の利用年月 2026-09 で出る。
  - 原因: 解約の速報値の調整年月が、ガスは通常分と同じ月（+1 で最終請求の請求年月と一致）なのに、でんきは通常分の 1 か月後で、+1 すると確定を 1 か月追い越す。補正の前は最終請求が捨てられていて、速報値が代わりに出ていた（二重ではなかった）。
  - ガスの 9 月分（910238133・910324778・911015319）は、解約の速報値の請求年月 2026-10 = 最終請求の請求年月で、出ない。
  - 912531657: 解約の速報値は請求年月 2026-09（調整年月 2026-08）。補正で確定の最大の請求年月が 2026-06 に下がったので、本番の CURRENT_YM が 2026-09 以下なら出る（おそらく出ない。ユーザーに画面確認を依頼）。
- 対策の案（ユーザーの判断待ち）:
  - 案1（推奨）: 画面の判定を使用期間で比べる（速報値の使用期間の終了日 ≦ その契約の確定の使用期間の終了日の最大 なら出さない）。ガス・でんき、調整年月の付け方に左右されず、リリース後の新しいデータも直る。coopcdeweb の修正（案A の判定方法の変更）。
  - 案2: 912419582 の解約の速報値の行を early_bill から消す（この 1 件だけ。旧システムに無い動き）。
  - 案3: 何もしない（CURRENT_YM が 2026-11 を過ぎれば出なくなる）。
- ユーザーの画面確認: **912531657 は速報値が表示されていない**（CURRENT_YM の条件で出ていないと考えられる）。二重表示は 912419582 だけ。対策（案1〜3）はユーザーの判断待ち。
- → **決定（ユーザー）: 案1。** 画面の速報値の判定を使用期間で比べる（速報値の使用期間の終了日 ≦ その契約の確定の使用期間の終了日の最大 なら出さない）。案A（請求年月 - 1 と利用年月の比較）からの変更。CURRENT_YM の条件はそのまま。coopcdeweb-1a に依頼（方式案は coopcdeweb のセッションでユーザーの了解を取ってから実装）。案2（速報値の行を消す）・案3（何もしない）はやらない。本番の 912419582 は、案1 を入れた画面が本番に出るまで二重に出る。

## 2026-11-17 coopcdeweb が速報値の判定（使用期間の終了日で比べる）を実装（Draft PR alphacmc/coopcdeweb＃145）

- coopcdeweb-1a の報告（ユーザーの了解は coopcdeweb のセッションで取得済み。#145 は未マージ）:
  - 判定: 速報値の usage_End_date が、その契約の確定の usage_end_date の最大より後なら出す（YYYYMMDD の文字列比較）。912419582（09/10 ≦ 09/10）と 910240391（10/31 ≦ 10/31）は出ないことをテストで確認。
  - 確定の行が無い契約は今のまま（最新の速報値を出す）。終了日が空・形式違いのときは案A の利用年月で比べる。CURRENT_YM の条件・DB・バッチは変えない。
  - バージョンは 1.9.0 のまま作り直す（ユーザー決定）。本番は予定どおり DDL-1 → 1.9.0。それまで本番の 912419582 は二重に出たまま。
  - でんきの解約の速報値が、最終請求が届く前に表で 1 か月ずれた月（請求年月の前月）に入る件は直さず、issue alphacmc/coopcdeweb#144 に記録（ユーザー決定）。
- 段取り: ユーザーが #145 をマージ → CodeBuild で 1.9.0 を作り直し → stg を入れ替えて画面確認（coopcdeweb）。coopbatch 側の作業は無し。
