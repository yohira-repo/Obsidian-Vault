# alphaexapi 作業ログ

## 2026-10-14 Plan E（ジョブオーケストレーション）最終レビュー対応

最終全体レビュー（opus）で検出された指摘への対応方針。

- **二重起動防止のDBチェック廃止**: `MfJobOrchestratorService`の`findRunningByType`による「同一jobTypeでRUNNING中なら409」チェックを削除する方針を承認。理由: プロセス異常終了時、アドバイザリロックはPostgres側で自動解放されるが`MfJob`行は`RUNNING`のまま残り、このチェックが以後の起動を永久に409ブロックしてしまう（手動DB修正以外に回復手段がない）致命的な問題のため。アドバイザリロックのみで二重起動を防止する方式に変更。設計書3.1章に追記済み。
- **MF送信成功後の記録更新失敗時の扱い**: `continueChain`で、MF送信(`run()`)自体は成功したが結果記録(`markSucceeded`)がDB都合で失敗した場合、`markFailed`を呼ばない方針を承認（mf-customer-sync Task 7と同じ前例）。理由: 送信成功済みのジョブをFAILED扱いにすると、再実行で二重送信のリスクがあるため。ログのみ出力しチェーンを中断する。
- **`GET /money-forward/jobs`のレスポンス形状**: 設計書2.3章の`{targetMonth, jobs:[...]}`というラップ形式を廃止し、実装（計画書通り）の裸配列`MfJobListItemDto[]`に設計書側を合わせる方針を承認。理由: 同じAPI群の`GET /customer-sync/candidates`（2.5章）も裸配列であり、形状を統一するため。alphasysへの契約化（API仕様のハンドオフ）前に確定。設計書2.3章に追記済み。
- **クラッシュ後に`RUNNING`のまま残る`MfJob`行の可視化**: `GET /jobs`のポーリングだけでは「応答なしの実行中」と「本当に実行中」を区別できない問題について、今回（Plan E）では対応せず、Plan C/D（請求書送信・取込等の実業務ロジック実装）着手時のフォローアップとする方針を承認（レビュアー推奨に従う）。
- **`PostgreSQLアドバイザリロックのセッション内再入可能性**への対応として、`MfJobLockService`にプロセス内in-memoryガード（`inFlightLockKeys: Set<number>`）を追加する方針を承認。DBチェック廃止後の唯一の排他手段がロックになるため、プロセス内の多重取得をロック層で確実に防ぐ目的。

## 2026-10-14 alphasysへのAPI契約ハンドオフを実施、画面構成はalphasys側で検討する方針を確認

ユーザーより「alphasysへの修正依頼をお願いします。画面構成などはalphasysで検討する予定です。」と依頼。alphaexapi設計書2章（alphasysとのAPI契約）の内容のみを抽出し、alphasysリポジトリに`docs/design/2026-10-14-MFクラウド連動-API契約.md`として作成、[alphasys PR #208](https://github.com/alphacmc/alphasys/pull/208)としてDraft PR化した。画面構成・UIレイアウトの検討はalphaexapi側のスコープには含めず、alphasys側に委ねる方針。

これにより、alphasystem仕様（docs/design/2026-10-09-MFクラウド連動-仕様.md）のうちalphaexapiが担当する部分（タスク0・Plan B取引先同期・Plan Eジョブオーケストレーション）の実装と、alphasysへのハンドオフまでが完了した。残課題（MfPartnerGatewayの実運用実装、Plan C/D、`MfSyncStatus.SENT`ベースの整合性再構築）は`.superpowers/sdd/progress.md`に記録済み。

## 2026-10-14 MfPartnerGateway実装に向けたMF API仕様調査とOAuth方式の確定

ユーザーがMoneyForwardクラウドの開発者ドキュメント（https://developers.biz.moneyforward.com/docs/common/getting-started-moneyforward-cloud-apis）を発見。本セッションで内容を調査し、請求書(Invoice)・債務支払(Payable)それぞれのAPIベースURL・OAuthエンドポイント・取引先(partners/counterparties)APIのリクエスト/レスポンス仕様を実際のOpenAPI仕様書(Swagger/Stoplight)から直接確認した。

**判明した事実**:
- 請求書(Invoice): `https://invoice.moneyforward.com/api/v3`、OAuth認可/トークンURLは統合基盤`https://api.biz.moneyforward.com/authorize`・`/token`、スコープ`mfc/invoice/data.write`。取引先は`POST/GET/PUT/DELETE /partners`、必須項目は`name`のみ
- 債務支払(Payable): `https://payable.moneyforward.com/api/external/v1`、OAuth認可/トークンURLは旧来の製品個別基盤`https://payable.moneyforward.com/oauth/authorize`・`/oauth/token`（クラウド経費と共通）、スコープ`office_setting:write`。取引先は`POST/GET/PUT/DELETE /offices/{office_id}/counterparties`、必須項目多数（`code`/`name`/`is_domestic`/`is_antisocial_checked`/`register_type`/`is_enable_output_payment_record`/`subcontract_type`/`company_type`）
- 債務支払は「user token」（クラウド債務支払自体のアプリ登録画面で発行）と「office token」（アプリポータルで発行）の2方式があり、**取引先の作成・更新はuser token方式でのみ可能**（office token方式のSwagger仕様には取引先作成APIが存在しないことを実際の仕様書比較で確認済み）
- APIキー方式（OAuthフロー不要）も存在するが、ユーザーが実機確認した結果、**請求書側はAPIキーに対応していない**ことが判明

**方針決定**: 債務支払はAPIキーで利用可能サービスに表示されるが、請求書側がAPIキー非対応であり、認可方式が製品ごとに分かれると運用・実装が煩雑になるため、**請求書・債務支払ともにOAuth2.0による認可フロー（user token方式）に統一する**。APIキー方式は採用しない。

この結果、タスク0で確立済みのOAuth実装（authorize/callback、トークン暗号化、リフレッシュ管理）がそのまま両製品に使える。債務支払は「クラウド債務支払」自体のアプリ登録画面（アプリポータルではない）でクライアント登録が必要な点が、経費(EXPENSE)と同じ方式で揃っている。

## 2026-10-14 債務支払アプリ登録時のリダイレクトURI検証エラーの原因判明

ユーザーが「クラウド債務支払」自体のアプリ登録画面でアプリ作成を試みたところ、フォームエラー（詳細非表示）が発生。原因切り分けの結果、登録しようとしていた複数のリダイレクトURIのうち`http://localhost:3000/money-forward/oauth/callback`（httpスキーム）が原因と判明、これを除外したところ登録が通った。

MoneyForward共通仕様の「認可・トークン取得・API呼び出しは必ずHTTPSを使用する」制約により、`http://`スキームのリダイレクトURIは弾かれることを確認。登録画面自体に「自社（個人）利用（バッチ処理）や手元の検証等では`urn:ietf:wg:oauth:2.0:oob`をご利用ください」という案内があり、ローカル動作確認時はこの値を使う方針とする。これにより設計書6章の未確定事項#3（ローカル開発時のOAuthリダイレクトURI回避方法）が解決した。

請求書側のアプリポータル登録が完了次第、確定した内容（Client ID/Secret格納場所、oobの扱い）をまとめて設計書に反映する予定（現時点ではPR #105に未反映、保留中）。

## 2026-10-14 請求書・債務支払の両アプリ登録が完了

ユーザーより、請求書（アプリポータル）・債務支払（クラウド債務支払自体の設定画面）ともにアプリ登録が完了した旨の報告。設計書6章に反映し、Client ID/Secretの環境変数命名規則を明記した。次はSSMパラメータストアへの実際の値の登録、および認可フローの疎通確認。

## 2026-10-14 ECSタスク定義へのMFシークレット注入が未実装と判明、alphasyscdkに修正を実施

ユーザーより、既存シークレット（Google OAuth等）の保管先がSSMパラメータストアだったかSecret Managerだったか確認を受け、調査した結果、両方使われているが明確な使い分け（APIキー・OAuthシークレット類はSSM、DB認証情報のみSecrets Manager、alphasystemリポジトリのdocs/design/2026-07-28-secret-management-design.mdに文書化済み）があることを確認。

その過程で、**alphasyscdk（インフラコード）のECSタスク定義に、MF関連のシークレットを注入する設定が一件も存在しない**ことが判明。タスク0の実装計画書にも既知のフォローアップとして記載されていたが未着手のままだった。

ユーザーの承認（「alphasyscdk/lib/constructs/ecs.tsの既存パターンに倣って進めてください」）を得て、alphasyscdk側に対応を実施:
- `lib/constructs/ecs.ts`に、既存のGoogle OAuth等と同じ`secureParam()`パターンで、`MF_INVOICE_*`・`MF_PAYABLE_*`・`MF_TOKEN_ENCRYPTION_KEY`・`MF_OAUTH_REDIRECT_URI`（計14キー）をSSMパラメータストア（`/alpha/{env}/alphaexapi/<KEY>`）経由で注入する設定を追加
- `cdk synth --profile staging`で実際にCloudFormationテンプレートへ14キー全てが出力されることを確認済み
- [alphasyscdk PR #95](https://github.com/alphacmc/alphasyscdk/pull/95)としてDraft PR化

残作業: SSMパラメータストアへの実際の値（Client ID/Secret、確認済みの認可URL等）の登録。

## 2026-10-14 請求書(INVOICE)のOAuth実疎通確認が成功

ローカル環境で、タスク0のOAuth実装（`/money-forward/oauth/authorize`→MFログイン・許可→`/money-forward/oauth/callback`）を実際のMFクラウド環境に対して疎通確認し、成功した（`{"product":"INVOICE","authorized":true}`、DBの`alp_mf_oauth_token`テーブルにも正しく保存されたことを確認）。

確認の過程で判明した、今後の作業（債務支払のOAuth確認、他メンバーの再現時）に役立つ知見:

- **アプリポータルには「アプリ開発」権限と「アプリ連携」権限が別物として存在する**。アプリ登録（Client ID/Secret発行）には「アプリ開発」権限で足りるが、実際にOAuth認可フロー中で「事業者を選択」→許可する操作には別途「アプリ連携」権限が必要（アプリポータルの「ユーザー」画面で対象ユーザーに付与する）。本番ではセキュリティ上、この2つの権限は別人に分けることが公式に推奨されている
- **ローカルでの疎通確認手順（ブラウザとcurlの併用）**: `/money-forward/oauth/authorize`はGoogle認証(`Authorization: Bearer <id_token>`)とRolesGuard(`x-user-role: ADMIN`)で保護されているため、ブラウザで直接開けない。alphasysの`/api/auth/session`エンドポイント（ログイン済みブラウザで開く）から`id_token`を取得し、`curl -c <cookiejar>`で`/authorize`を叩いてMFの認可URLを取得→そのURLをブラウザで開いてMFにログイン・許可→リダイレクト先の`code`/`state`をブラウザのアドレスバーからコピー→`curl -b <cookiejar>`で`/callback`を手動で叩く、という手順で完結できる（nonce Cookieがcurlとブラウザ間で共有されないため、ブラウザでの着地はエラー表示になるが無視してよい）
- state(10分)・Googleのidトークン(1時間)それぞれに有効期限があるため、アプリポータルでの権限設定等に時間がかかると、やり直しが必要になる
- ローカル実行時は`npm run start`等でサーバーを起動したままだと`.env`編集後の値を読み込まないため、`.env`変更のたびにサーバー再起動が必要

次: 債務支払(PAYABLE)側も同様に疎通確認を行う。

## 2026-10-14 MFクラウド連動のOAuth疎通確認用の自動化ツールを作成する方針を承認

請求書・債務支払それぞれでOAuth疎通確認を手動のcurl往復で行ったが、GoogleのIDトークンが1時間・stateが10分で失効するため、都度の手動作業（IDトークン取得→curl→ブラウザでMF許可→code/stateコピー→curl再実行）がやり直しになりやすく時間がかかった。これを解消するツールを作成する方針で合意。

検討した案:
- A: curlの往復のみ自動化（IDトークン取得・ブラウザ操作は手動のまま）
- **B（採用）**: ブラウザ操作（MFの許可画面のクリック等）まで自動化。ただしGoogleログイン自体（パスワード・MFA入力）はPlaywrightで自動化せず、**ユーザーの既存のログイン済みブラウザプロファイルをそのまま使う**方式とする（Googleのボット検知・法人Workspaceアカウントの追加セキュリティポリシーを踏まえ、認証情報をスクリプトに持たせるリスクを避けるため）
- C: ローカル開発時のみGoogleAuthGuardを一時バイパス → 本番コードに穴ができるリスクがあるため不採用

ツールは`scripts/`配下に作成し、Playwrightを新規devDependencyとして追加する想定（実装の詳細は別途確認の上で着手）。

## 2026-10-14 OAuth疎通確認自動化ツール(scripts/mf-oauth-verify.js)が動作確認完了

作成したツールを実際に実行し、請求書(INVOICE)のOAuth疎通確認が自動化フローで成功した（MF自体のログイン画面でEnter待ちし、手動ログイン後は自動でcode/state中継→コールバック処理→DBへのトークン上書き保存まで完了）。1回目の実装では「未知の画面でブラウザを自動で閉じてしまう」バグがあり(MF自体のログイン画面をパスワード入力中に強制終了)、人間の操作待ちをEnterキー待ちにする修正を実施して解決した。

次: 債務支払(PAYABLE)でも同じツールを使って疎通確認を行う。

## 2026-10-14 請求書・債務支払の両方でOAuth実疎通確認が完了

`scripts/mf-oauth-verify.js`を使い、債務支払(PAYABLE)でも同様に実疎通確認を実施し成功（`{"product":"PAYABLE","authorized":true}`）。`alp_mf_oauth_token`テーブルにINVOICE・PAYABLE両方のトークンが保存されていることを確認済み。

これにより、MFクラウド連動のOAuth基盤（タスク0の実装）が、請求書・債務支払の両方で実環境に対して疎通することが確認できた。残作業は以下:
- SSMパラメータストアへの本番/ステージング用の値の登録（ローカルの.envとは別に、実際の運用環境向けの値を別途登録する必要がある。本番・ステージングでも各製品のアプリ登録が必要）
- `MfPartnerGateway`の実装計画（brainstorming→設計→実装計画）に着手可能な状態

## 2026-10-14 MfPartnerGateway実装のbrainstorming開始、債務支払の個人/法人判定方式を確定

`MfPartnerGateway`実装のbrainstormingを開始。中心的な論点として、債務支払(Payable)の取引先作成APIが必須とする`company_type`（個人/法人）・`register_type`（インボイス登録番号有無）等のフィールドに対応する情報が、alphadbの`Customer`テーブルに存在しないことが判明。

**決定**: 既存の`CorporationService.getInvoiceInfoByCorporateNumber()`（国税庁の適格請求書発行事業者公表システムWeb-API）を呼び出し、`corporateNumber`をキーに判定する。国税庁公式のリソース定義書で`kind`項目（人格区分）の値を確認済み: `"1"`=個人、`"2"`=法人。

- `company_type`: `kind`の値から`"individual"`/`"corporate"`に変換。`corporateNumber`が無い、API呼び出し失敗、該当なしの場合は`"unknown"`
- `register_type`: `announcement`が1件以上あれば`"registered"`、0件なら`"none"`、判定不能なら`"unknown"`
- 既存の`getInvoiceInfoByCorporateNumber()`は他のコントローラで既に使われているため戻り値の形は変更せず、`kind`等を返す新しいメソッドを`CorporationService`に追加する方針

その他、ドメインモデルに対応情報が無い必須フィールドはデフォルト値とする:
- `is_antisocial_checked`（反社チェック実施）: **`true`**（既存のオンボーディングプロセスで実施済みという前提のため、`false`ではなく`true`に修正）
- `subcontract_type`（下請法区分）: `"unknown"`
- `is_enable_output_payment_record`（支払調書出力要否）: `false`

## 2026-10-14 MfPartnerGateway設計: 債務支払のoffice_idは環境変数で固定設定する方針を確定

債務支払APIの`/offices/{office_id}/counterparties`が必要とする`office_id`（取引先のIDではなく、自社「株式会社アルファ・コミュニケーションズ」自体のMFクラウド上の事業者ID）について、毎回`GET /offices`で動的取得するのではなく、**環境変数（`MF_PAYABLE_OFFICE_ID`）として固定設定する**方針を確定。

## 2026-10-14 MfPartnerGateway設計: フィールドマッピング方針を確定

`CustomerSyncPayload`から各製品APIへのマッピング方針を確定。

- 請求書(Invoice) `/partners`: `code`=`buildMfPartnerCode(customerNo)`(Plan Bの既存実装を再利用)、`name`=`customerName`、`departments[]`に`zip`=`postalCode`・`address1`=`address`(分割せずそのまま)・`tel`=`telNo`・`email`=`email`
- 債務支払(Payable) `/offices/{office_id}/counterparties`: `code`=`buildMfPartnerCode(customerNo)`、`name`=`customerName`、`address`=`address`(そのまま)、`phone_number`=`telNo`、`individual_number`=`corporateNumber`、`company_type`/`register_type`=前述の国税庁API判定結果、`is_antisocial_checked`=`true`、`subcontract_type`=`"unknown"`、`is_enable_output_payment_record`=`false`
- **確認済み**: 債務支払の取引先(counterparty)リソースには`email`に相当するフィールドが存在しない(ユーザーが仕様書で確認)。`CustomerSyncPayload.email`は債務支払側では使用しない。

## 2026-10-14 MfPartnerGateway設計: 請求書updatePartnerのdepartments更新方式を確定

設計書作成後、実装計画に進む前の最終確認で、請求書(Invoice)の`PUT /partners/{partner_id}`リクエストボディに`departments`フィールドが存在しないことが仕様書の再確認で判明（住所・電話・メールは`/partners/{partner_id}/departments/{department_id}`という別サブリソースでのみ更新可能）。

**決定**: `updatePartner`では、基本情報の更新に加えて部署情報も追従させる方針とする。具体的には`PUT /partners/{partner_id}`で基本情報を更新した後、`GET /partners/{partner_id}/departments`で既存の部署一覧を取得し、先頭の1件を`PUT .../departments/{department_id}`で更新する（0件の場合は新規作成）。設計書4.1章に追記済み。

## 2026-10-14 MfPartnerGateway実装、Subagent-Drivenで開始

設計書・実装計画（PR #107, #109）承認済み。実行方式はSubagent-Driven Development（タスクごとに新しいsubagent + レビュー）を選択。実装計画: `docs/superpowers/plans/2026-10-14-mf-partner-gateway.md`（6タスク構成）。

## 2026-10-14 MfPartnerGateway実装完了、PR ＃109マージ済み後への誤push発覚・PR ＃111作成

MfPartnerGatewayの実装（6タスク、Subagent-Driven Development）が全て完了し、最終全体レビュー（opus）もImportant指摘3件の修正を経て承認された。

**インシデント**: 実装作業用ブランチ`feature/mf-partner-gateway-plan`のPR #109は、実装着手前（設計書・実装計画のドキュメントのみ、commit fca6bdcまで）の時点で既にマージされていた。その後の実装作業（Task 1-6+最終レビュー修正、計11コミット）を同じブランチに追加pushする前に、CLAUDE.mdの方針通りマージ済みかどうかの確認を怠っていた。`git push`実行後に`gh pr view`でマージ済み(33d3c70)と判明し、直ちに新規PR #111を作成して対応した（コミット自体は失われていない）。

今後の同種の失敗を避けるため、長時間の実装作業（Subagent-Driven Developmentの各タスク）の途中でも、pushの都度ではなくとも、ブランチのPRがマージされていないか定期的に確認する必要がある。

## 2026-10-14 20:08 セッション区切り: MfPartnerGatewayマージ完了、次の作業は未確定

[alphaexapi PR #111](https://github.com/alphacmc/alphaexapi/pull/111) マージ確認、ローカルstaging同期・ブランチ削除まで完了。MFクラウド連動のalphaexapi側実装基盤（タスク0・Plan B取引先同期・Plan Eジョブオーケストレーション・MfPartnerGateway）が一通り揃い、`CustomerSyncService`経由で実際にMFクラウドへ取引先を作成・更新できる状態になった。

次にどれを着手するかはまだ決まっていない（提示した3つの選択肢、ユーザーからの指定待ち）:
1. 債務支払の取引先作成・更新の実疎通確認（OAuthは確認済みだが実際の`POST /counterparties`は未実施）
2. SSMパラメータストアへの`MF_PAYABLE_OFFICE_ID`等の本番/ステージング値登録
3. Plan C/D（請求書送信・債務支払送信・取込の実業務ロジック実装）

引き続き未着手・保留中の事項（過去記録の再掲、継続して有効）:
- `MfPartnerGateway`の実運用時の`company_type: "unknown"`受理可否の実疎通確認
- `CustomerSyncService`の二重作成リスク対応（`MfSyncStatus.SENT`ベースの整合性再構築、未着手）
- alphasys側のUI実装4画面（請求一覧の送信/取込ボタン差し替え、バッチ共通処理配下のMF実行状況画面、取引先管理配下のMF取引先照合・設定画面、管理者画面のMF認可ボタン）。brainstormingの検討結果は別セッションでalphasysの`docs/superpowers/specs/2026-10-14-MFクラウド連動-UI設計.md`にローカルコミット済み・未push（alphaexapi側からは関知しない）

## 2026-10-15 残作業の着手順を確定

ユーザーより、2026-10-14時点で提示した3つの残作業の着手順を指定: **1→3→2**の順で進める。

1. 債務支払の取引先作成・更新の実疎通確認（OAuthは確認済みだが実際の`POST /counterparties`呼び出しは未実施）
2. Plan C/D（請求書送信・債務支払送信・取込の実業務ロジック実装）
3. SSMパラメータストアへの`MF_PAYABLE_OFFICE_ID`等の本番/ステージング値登録

まず1（債務支払の実疎通確認）から着手する。

## 2026-10-15 債務支払の取引先作成・更新API、実疎通確認が成功

`MfPartnerGatewayImpl`の`createPartner`/`updatePartner`/`listPartners`を、実際のMFクラウドテスト環境(債務支払)に対して疎通確認した。

- `GET /offices`で自社の`office_id`(`dRFWI3FVyuZ7u5okxV25TA`、株式会社アルファ・コミュニケーションズ)を取得し、ローカル`.env`の`MF_PAYABLE_OFFICE_ID`に設定
- `createPartner`: 実際に取引先を作成(`mfId=i963W7QSBd3AUU4w2uxISg`、`code=S0000999999`)、成功
- `listPartners`: 作成した取引先が正しくページング吸収・検索できることを確認
- `updatePartner`: 既存取引先の更新(名称・住所・電話番号)も成功
- **設計書§8の未解決事項が解決**: `corporateNumber`未指定(個人/法人判定不能)時の`company_type: "unknown"`/`register_type: "unknown"`が実際のAPIに受理されることを確認済み

確認用データ(「接続確認用テスト株式会社」、`code: S0000999999`)はMFテスト環境に残存している(テスト環境のため削除不要と判断、ユーザーにも確認済み)。

残作業(2026-10-15時点の着手順どおり、次はPlan C/D): SSMパラメータストアへの`MF_PAYABLE_OFFICE_ID`等の本番/ステージング値登録はまだ行っていない(ローカル`.env`のみ設定済み)。

## 2026-10-15 Plan C/D着手: 送信→取込の2段階に分割する方針を確定

Plan C/D（請求書送信・請求書取込・債務支払送信・債務支払取込）のbrainstormingを開始。製品単位ではなく**送信/取込の軸**でサブプロジェクトに分割する方針をユーザーが承認:

1. **送信**（請求書送信・債務支払送信）— 上位仕様5.1で「請求書と同型」と明記されており、対象契約抽出・金額ルールが共通
2. **取込**（請求書取込・債務支払取込）— 品名パーサによる突合ロジックは共通だが、債務支払側のみ合算・経費科目WARN等の追加ルールあり

まず1（送信）から設計・実装し、完了後に2（取込）に進む。

## 2026-10-15 債務支払送信をAPI制約により保留、請求書送信を先行する方針を確定

Plan C/D「送信」のbrainstorming中、債務支払送信（`invoice_reports`/支払依頼）について重大な制約が判明した。

**発見した事実**:
- `POST /offices/{office_id}/invoice_reports/{invoice_report_id}/invoice_transactions`（既存の支払依頼に支払明細を追加する）は存在するが、**支払依頼（箱）自体を新規作成するAPIが見当たらない**（user token版・office token版双方で確認、GETのみ）
- office token版の`POST /v1/received_invoices`はファイル(PDF等)アップロード前提のOCR系APIで、構造化データからの作成には使えない
- ユーザーが実際のMFクラウド債務支払画面（支払依頼＞申請一覧）のスクリーンショットを提示。「インポート」ボタンはCSVから**行ごとに独立した新しい申請を作成**しており、既存の1つの箱に明細を追加していく挙動ではない。この挙動は確認済みの公開APIでは再現できないため、CSV取込機能は非公開の内部APIを使っている可能性が高い
- ユーザーからは「現在は毎月CSVでインポートしているだけで、何をしているか分からない」との回答。経理担当者・MFサポートへの確認が別途必要な状態

**決定**: 債務支払送信は保留とし、**請求書送信（Invoice側、`POST /invoice_template_billings`で新規作成APIが明確に存在する）を先に設計・実装する**。債務支払送信の方式確定は、ユーザーが別途MFサポートまたは経理担当者に確認した後に再開する。

## 2026-10-15 請求書送信の実装詳細を2点確定

- `department_id`: 取引先作成時に自動作成される部署（1件）を`GET /partners/{partner_id}/departments`で取得し、先頭の1件を使う
- 税区分（`excise`）: 標準税率10%（`ten_percent`）固定

## 2026-10-15 請求書送信: 請求書の単位・明細の命名規約を確定

- 請求書(Billing)の単位は**取引先＋支払年月**（現行CSVと同じ）。1顧客につき1枚の請求書を作成する
- 明細(items[])は契約単位。品名は`契約番号_契約名`（上位仕様6章の命名規約通り）
- 請求書側の識別子（タイトル等）は`取引先番号_取引先名_支払年月日`形式（現行CSVの形式を踏襲）

## 2026-10-15 請求書送信: 実際のCSVファイルで現行フォーマットを確認

ユーザー提示の実際のCSVファイル（`MFクラウド請求書_20260930.csv`、Shift-JISエンコード）を確認し、以下を確定:

- **件名**: 取引先名そのもの（ユーザーの前回回答の訂正通り）
- **メモ**: `{連番}_{取引先名}_{支払期限YYYYMMDD}`形式（例: `1_株式会社NTTデータ_20261031`）。先頭の連番は現行ファイル内の行番号らしきもの
- **請求書の単位**: 1顧客につき1請求書（行形式=請求書）、契約ごとに品目行（行形式=品目）を複数追加。実データでも1顧客に最大5契約程度の例を確認
- **品名**: `契約番号_契約名`形式、上位仕様6章の命名規約と完全一致（例: `6059_ろうきん勘定系基盤更改対応＿角田`）
- **消費税率**: 実データで小計の10%ちょうどになっており、標準税率10%固定の前提を裏付け
- **請求書番号**: 実データでは空欄（設定不要と判断）

残課題: メモ欄の先頭連番を、新システムでは実際の`customerNo`に置き換えるかどうかユーザー確認待ち。

## 2026-10-15 請求書送信: メモ欄の形式を確定

メモ欄は`{customerNo}_{取引先名}_{支払期限YYYYMMDD}`（生の`customerNo`を使用。MF側の`code`フィールド用の`S0000000207`形式とは別物であることを明確化）。

## 2026-10-15 請求書送信: 「入金予定日」フィールドの欠落を発見、alphadbへの連携が必要

請求書の支払期限（`due_date`）を検討中、**同じ取引先でも契約ごとに支払期限が異なりうる**ことが判明（「月末と15日があります」）。さらに詳細確認の結果、**現行の旧システムには既にこの情報を持つフィールドが存在する**ことが分かった（新システム=alphadbのスキーマには未移行、漏れている）。

**現行システムの「入金予定日」フィールド（数値、契約単位）**:
- `0` → 翌月末日
- `0以外の数値N` → 翌々月のN日（ただしMAXは翌々月の末日）

このルールに基づき、請求書送信時は**支払期限（算出結果の日付）が同じ契約同士を1つの請求書にまとめ、支払期限が異なる契約は別の請求書に分ける**必要がある（1顧客につき1請求書、という単純な単位ではなく、1顧客×支払期限の組み合わせごとに1請求書）。

**対応方針**: この「入金予定日」相当のフィールドをalphadbの`Contract`テーブルに追加する必要がある。**alphadbプロジェクト側での対応をユーザーが別セッションで行う予定**。請求書送信の実装は、このフィールドがalphadbに追加されるまで着手できない（ブロック中）。

## 2026-10-15 請求書送信: alphadb側の新フィールド名を確定、設計を続行する方針を確認

alphadb側に追加予定の列名: `scheduled_payment_date`（Int）。alphadb側の対応完了を待つ間も、この前提で請求書送信の設計を完了させる方針を確認。

## 2026-10-15 請求書送信: 再実行時の重複防止方式を確定

既存のMF請求書一覧(`GET /billings`)をメモ欄(`{customerNo}_{取引先名}_{支払期限}`)で検索し、一致するものがあれば送信をスキップする方式を採用。請求書を置換したい場合は、その取引先の請求書をMFC請求書画面から手動削除する運用とする（システム側での自動置換・更新は行わない）。

## 2026-10-15 請求書送信: 実装計画をalphadb対応と並行して先に作成する方針を確認

設計書レビュー完了。alphadb側の`scheduled_payment_date`追加作業と並行して、実装計画(`docs/superpowers/plans/`)を先に作成する。実装着手自体はalphadb対応完了後。

## 2026-10-15 請求書送信: 金額優先順位の対象月スコープを確認

「`BillRecipt`が存在すればその値」は、対象月に該当する`BillRecipt`（`billDate`が対象月のもの）に限定する（契約に過去のBillReciptが存在するだけでは使わない）。

## 2026-10-15 請求書送信: 実装計画を作成、alphadb対応完了によりブロッカー解消・実装着手

実装計画(`docs/superpowers/plans/2026-10-15-invoice-send.md`)を作成（6タスク構成: due-date算出 → 対象契約抽出リポジトリ → グルーピング・リクエストボディ組み立て → InvoiceSendService本体 → InvoiceSendJobRunner・モジュール配線 → 最終確認）。

計画自己レビュー中に、`Contract.BillRecipt.amount`がPrismaの`@db.Decimal`型（`Decimal`インスタンスとして返る）であることを発見し、計画のTask 2実装例を`number`直接代入から`.toNumber()`変換に修正（自己レビューで検出・修正、実装者への引き渡し前に解消）。

ユーザーからalphadb側のスキーマ変更完了の報告（alphadb 0.2.2→0.2.3、`Contract.scheduledPaymentDate`(Int, nullable)追加）を受け、`npm install alphadb@0.2.3`で取り込み・`prisma generate`を再実行して型生成を確認。これによりブロッカーが解消されたため、Subagent-Driven Developmentによる実装着手を開始（Task 1から）。

なお取り込み時、`CODEARTIFACT_AUTH_TOKEN`が未設定でnpm installがE401で失敗する問題が発生。`aws codeartifact get-authorization-token`で都度取得する運用（`.npmrc`記載の通り）で解消。

## 2026-10-15 請求書送信: Subagent-Driven Developmentで6タスク実装完了、最終レビューで重大指摘3件を確認・対応方針を確定

実装計画の全6タスク(支払期限算出・対象契約抽出リポジトリ・グルーピング・InvoiceSendService本体・InvoiceSendJobRunner配線・最終確認)をSubagent-Driven Developmentで実装完了。各タスクのレビューで計4件のImportant指摘(型安全性のlintエラー、契約名null時のMF品名破損、テスト書き換えによるMfProduct検証漏れ、いずれも修正済み)が出たが、個別タスクレベルでは全て解消・承認済み。

その後の最終的なブランチ全体レビューで、現行システム(alphaofficesystem)の実コードを確認した結果、以下3件の重大な指摘が出て、ユーザーに確認の上で対応方針を確定した:

1. **（Critical）請求金額の税区分誤り**: `BillRecipt.amount`(税込)を使っていたが、現行システムの実コード(`BillReceiptItemProcessor.java`で`amount=amountExTax+amountExTax*0.1`と算出、かつ本番設定`tax.include=0`=税抜モード)を確認した結果、MF側には税抜金額(`amountExTax`)を渡すべきと判明。旧設計のままだと約10%の過大請求になっていた。→ **`amountExTax`を使うよう修正する**。
2. **（Important）「対象外」(MfSyncStatus.EXCLUDED)の顧客にも請求書が送信されてしまう**: 対象外設定後も`mfId`が残る仕様のため、`mfId`有無だけでの判定では対象外顧客もスキップされない。→ **対象外(EXCLUDED)の顧客は`mfId`の有無に関わらずスキップする**。
3. **（Important）重複防止チェック(`GET /billings`)がページング未対応**: 既存のMF取引先一覧取得(`listInvoicePartners`)は正しくページングしているが、新規実装の重複チェックは1ページ目しか見ておらず、請求書数が多い顧客で再実行時の二重作成リスクがあった。→ **同じページング方式(`page`/`per_page`、`pagination.current_page/total_pages`)を適用する**。

あわせて、対象月に同一契約のBillReciptが複数件存在する場合（本来想定外）の金額の扱いについても確認し、**合算する**方針とした。また、金額0円以下の契約を含むまま送信が成功した場合は`OK`ではなく`WARN`として記録するよう、ついでに改善する（送信自体は変更しない）。

設計書(`docs/superpowers/specs/2026-10-15-invoice-send-design.md`)の§4・§6・§7・§8を上記方針に合わせて更新し、実装側の修正をSubagent-Driven Developmentの修正ラウンドとして実施。再レビューで「対象外かつmfId未設定」時のSKIP理由メッセージが誤る軽微な指摘(Important、マージブロッカーではない)が出たため直接修正(コミット394bdd3)。全体テストスイート262/262パス・ビルド成功・lint(対象ファイル)エラー0件を確認し、[PR #117](https://github.com/alphacmc/alphaexapi/pull/117)にpush・完了コメントを投稿。請求書送信(Plan C送信)の実装はこれで完了。

## 2026-10-15 請求書送信の実MF環境疎通確認: 事前調査でINVOICE側のcreatePartner未検証を発見、テスト手順を確認中

PR #117マージ後、残作業の最初の項目として請求書送信の実MF環境疎通確認に着手。事前にconversations.mdを確認した結果、**PAYABLE側は接続確認用テスト取引先(`S0000999999`)でcreatePartner/updatePartner/listPartnersの実疎通確認済みだが、INVOICE側はOAuth疎通確認(`scripts/mf-oauth-verify.js`)のみで、実際の`createPartner`(`POST /partners`)呼び出しはまだ未実施**であることが判明。つまりテスト環境のDBには、請求書送信が依存する「INVOICE側で同期済み(mfId設定済み)の`MfLink`」がまだ存在しない可能性が高い。

予定しているテスト手順(MfPartnerGateway疎通確認時と同じ`scratch-*.ts`方式、確認後に削除):
1. INVOICE側のテスト用取引先をcreatePartnerで作成し、mfIdをMfLinkとしてDB登録
2. `InvoiceSendService.run(targetMonth)`を直接実行し、department_id解決・請求書作成(`POST /invoice_template_billings`)を確認。**特に、今回修正した税区分(amountExTax使用)がMF画面上で正しく10%加算された税込合計になっているかを最重要確認項目とする**
3. 同じtargetMonthで再実行し、メモ欄一致によるSKIP(重複防止)を確認
4. 作成した確認用データは、PAYABLE側の前例(テスト環境のため削除不要、ユーザー確認済み)に倣う想定

テスト用取引先データ(完全な仮データ vs 実際のalphadb顧客・契約データ)をどちらにするか、ユーザーに確認中。

## 2026-10-15 請求書送信の実MF環境疎通確認: テストデータ方針を確定

テスト用のCustomer/Contract/MfLinkは、実在の顧客とは無関係な完全な仮データ(PAYABLE側の「接続確認用テスト株式会社」と同様の位置付け)として、既存データとの整合性を取らずに作成する方針をユーザーに確認・承認された。確認完了後、MF側のデータは削除不要(PAYABLE側の前例通り)だが、alphadb側の仮レコード(Customer/Contract/MfLink)は削除する。

## 2026-10-15 請求書送信の実MF環境疎通確認が成功

`scratch-invoice-send-verify.ts`(確認後削除)を使い、実際のMFクラウド請求書テスト環境に対して疎通確認を実施した。

**事前に発覚した環境上の問題**: ローカルのPostgreSQL(`alphaexapi-postgres-1`)に、alphadb 0.2.3で追加されたはずの`scheduled_payment_date`列のマイグレーション(`20261015024244_add_contract_scheduled_payment_date`)が未適用だった(`npm install`でPrismaクライアントの型は更新されるが、実DBのスキーマ変更は別途`prisma migrate deploy`が必要なため)。`npx prisma migrate deploy --schema=node_modules/alphadb/prisma/schema.prisma`で適用し解消。

**確認結果**:
1. テスト用Customer(customerNo=2)/Project/Contract(contractNo=1、契約名「請求書送信確認用テスト契約」、`contEarnings=1,000,000`(税抜)、`scheduledPaymentDate=0`)を作成
2. `MfPartnerGatewayImpl.createPartner(INVOICE, ...)`でMFクラウド請求書テスト環境に取引先を新規作成成功(`mfId=hH8eA6v7L5ZPFUQXvbvG7g`)。**INVOICE側のcreatePartner実疎通確認はこれが初めて**(PAYABLE側は既存で確認済みだった)
3. `InvoiceSendService.run('2026-10')`を実行し、請求書が1件新規作成されたことを確認(`succeededCount=1`)
4. 同じ対象月で再実行し、メモ欄一致による重複防止SKIPが正しく機能することを確認(`skippedCount=1`)
5. `GET /billings`で実際に作成された請求書データを取得し、**今回修正した税区分バグが実環境で正しく解消されていることを確認**: `items[0].price="1000000.0"`(税抜)・`excise_price_of_ten_percent="100000.0"`(消費税)・`total_price="1100000.0"`(税込合計) — 税抜1,000,000円+消費税100,000円=税込合計1,100,000円で完全に一致。`memo`(`2_請求書送信確認用テスト株式会社_20261130`)・`items[0].name`(`1_請求書送信確認用テスト契約`)・`billing_date`/`sales_date`(`2026/10/31`)・`due_date`(`2026/11/30`)もすべて設計通り

後片付け: スクリプトファイルは削除(`git status`クリーン確認済み)。alphadb側のテスト用レコード(Customer/Project/Contract/MfLink)は削除済み。MF側に作成された確認用取引先・請求書データは、PAYABLE側の前例に倣い削除不要(テスト環境のため)とした。

請求書送信(Plan C送信)の実MF環境疎通確認はこれで完了。

## 2026-10-15 請求書取込の設計に着手、目的・データ取得元・除外ロジックを確認

残作業のうち現在対応可能な「請求書取込」の設計をブレインストーミング開始。上位仕様(alphasystem)4.2章・alphaexapi設計書§4.3、および現行システムの実装(`BillReceiptItemProcessor.java`)を確認し、以下を確認・承認された:

1. **取込の目的**: 入金消込やMF側ステータス取得ではなく、**MFクラウド請求書側の確定請求データ(品目ごとの金額)を`BillRecipt`テーブルへ登録・反映すること**(現行システムのCSVインポートと同じ目的)。
2. **データ取得元**: 既存の重複防止チェックでも使用している`GET /billings`を使う。特定の取引先(`partner_id`)に絞らず、自社全体の請求書を対象にページング全件取得し、`sales_date`=対象月末のものをクライアント側で絞り込む。
3. **契約管理対象外の請求書の除外ロジック**: 自社の本業(システム開発)以外の目的で発行された請求書(弊社の契約管理の対象外)が`GET /billings`に混在しうる点について確認。既存の`item-name-parser.ts`で各`items[].name`を解析し、**`契約番号_契約名`形式として解析できる品目だけを取込対象とする**方式で、契約管理対象外の請求書を自然に除外できることを確認・承認された。

## 2026-10-15 請求書取込の設計: 再実行時の挙動・異常系の扱いを確認

ブレインストーミング継続。以下を確認・承認:

1. **再実行時の挙動**: 同一契約・同一月で既に`BillRecipt`が登録済みの場合、既存行を最新のMFデータで上書き更新する（送信側の「既存はSKIPして自動更新しない」方針とは異なり、取込側は常にMF側が正という前提で上書きする）。
2. **存在しない契約番号の扱い**: 品目名が`契約番号_契約名`形式だが、その契約番号がalphadbに存在しない場合（削除済み・タイプミス等）は、警告ログを残してその品目だけ読み飛ばす（債務支払側5.2章の「想定外の経費科目で取り込んだ」警告パターンと同種、ただし本件は契約自体が無いため読み飛ばす点が異なる）。
3. **同一対象月内で同じ契約番号が複数回出現した場合**: 通常は送信側のグルーピングによりあり得ない想定。ユーザーの明示的な判断により、**後から検出した方をエラーとして扱う**（合算はしない。債務支払側5.2章の合算ルールとは異なる扱い）。

## 2026-10-15 請求書取込の設計: データ取得方式・税率異常系を確定

MF公式OpenAPI仕様書(`https://invoice.moneyforward.com/docs/api/v3/reference/iv_web_api.yaml`)を直接確認した結果、`GET /billings`には`range_key`(`sales_date`等)+`from`/`to`(日付範囲)というサーバー側絞り込みパラメータが実在することが判明。当初決めていた「全件ページング+クライアント側絞り込み」から、**`range_key=sales_date&from=<対象月初>&to=<対象月末>`でサーバー側に絞り込ませる方式に変更**する方針を確認・承認された。対象月の判定基準は**売上計上日(`sales_date`)であり、支払期限(`due_date`)ではない**ことをユーザーに明示的に確認済み(上位仕様4.2章と一致)。

あわせて、品目の`excise`(税率)が`ten_percent`以外だった場合(本来起こりえない想定)の扱いも確認: 存在しない契約番号と同様に**警告ログを残して読み飛ばす**(SKIP)。

これで請求書取込の設計に必要な論点(目的・データ取得元・除外ロジック・再実行時の挙動・異常系の扱い全般)が出揃った。設計書の作成に進む。

## 2026-10-15 請求書取込の実装計画を作成

PR #119（請求書取込の設計書）マージ確認後、実装計画(`docs/superpowers/plans/2026-10-15-invoice-import.md`)を作成（全4タスク構成: 税額計算・日付変換の純関数 → 契約照合・BillRecipt upsertリポジトリ → InvoiceImportService本体 → InvoiceImportJobRunner・モジュール配線 → 最終確認）。[PR #121](https://github.com/alphacmc/alphaexapi/pull/121)としてDraft PR化。これから実装に着手する。

## 2026-10-15 請求書取込: 最終の全体レビューで発見された送信/取込間の整合性問題への対応方針を確定

Subagent-Driven Developmentで全4タスク実装完了後、最終の全体レビュー(opus)で以下3件のImportant指摘が出た。現行システム(alphaofficesystem)の実装を直接確認した上で、ユーザーに対応方針を確認した:

1. **取込側の単一行upsertが送信側の複数行合算ポリシーと不整合で、分割計上等があると金額が二重計上されうる問題**: 現行システムは対象月の売上側BillReciptを全削除してから登録し直す方式(delete-then-insert)だが、今回の実装はupsert方式。ユーザーの判断: **現状のupsert方式のままでよい**(分割計上は実運用上あり得ない想定のため、complexity増を避ける)。
2. **品目1件ごとのエラーハンドリングが無く、途中で例外が起きると部分的な書き込みが記録に残らない問題**: ユーザー承認により、送信側と同様に品目1件ごとのtry/catch(部分失敗をERROR記録して続行)を追加した。
3. **送信チェーンと取込チェーンが別ロックキーで、同一対象月での同時実行を防げない問題**(取込がBillReciptを書き込み、送信がそれを読むという依存関係があるため): ユーザー承認により、送信・取込のアドバイザリロックキーを1つに統合し、対象月を問わず送信と取込が同時に走らないよう排他制御する方針に変更した(`MF_JOB_SEND_LOCK_KEY`/`MF_JOB_IMPORT_LOCK_KEY`→`MF_JOB_LOCK_KEY`に統合)。これはPlan E設計時の意図的な決定(「送信と取込は業務的に独立しているため別ロックとし、同時に走ってよい」)を、今回実装した業務ロジックの依存関係を踏まえて見直したもの。

2・3の修正をコミット(56bbb3f)、全体テストスイート281件パス・ビルド成功・lintエラー0件を確認済み。再レビューで軽微な指摘(upsert失敗時にcustomerNoがnull記録される欠落)が出たため直接修正(コミットe921df6)。全体テストスイート282/282パス・ビルド成功を再確認し、[PR #121](https://github.com/alphacmc/alphaexapi/pull/121)にpush・完了コメントを投稿。請求書取込(Plan C取込)の実装はこれで完了。

## 2026-10-15 請求書送信→取込の一連の流れ、実MF環境疎通確認が成功

`scratch-invoice-send-import-verify.ts`(確認後削除)を使い、実際のMFクラウド請求書テスト環境に対して送信→取込の一連の流れを確認した。

テスト用Customer/Project/Contract(税抜999,995円、わざと10%で割り切れない金額にして切り捨て計算を実環境で確認する目的)を作成し、以下を確認:

1. `InvoiceSendService.run()`で請求書を新規送信 → 成功
2. `InvoiceImportService.run()`で取込 → `BillRecipt`を正しく作成(`amountExTax=999995, tax=99999`(切り捨て、四捨五入ではない)、`amount=1099994`)。**副次的な確認**: 以前のテスト(2026-10-15午前に実施した請求書送信単体の疎通確認)で作成した請求書がMF側に残っており、そのcontractNo(alphadbからは削除済み)が「存在しない契約番号」としてSKIP記録される実データでの動作も確認できた
3. `InvoiceSendService.run()`を同月で再実行 → 重複防止により正しくSKIP
4. `InvoiceImportService.run()`を同月で再実行 → 同一`billNo`のまま`updatedAt`のみ更新される上書き更新(二重作成なし)を確認

alphadb側のテスト用レコードは削除済み。MF側に作成された確認用取引先・請求書データは、既存の方針通り削除不要(テスト環境のため)とした。

これにより、請求書送信・請求書取込(Plan C)の実MF環境疎通確認が完了した。残作業は債務支払送信・取込(Plan D、ユーザーのMF側への確認待ち)のみ。

## 2026-10-15 マージ済みブランチへのpushインシデント(再発)、新規PRで対応

PR #121のマージ完了に気づかず、疎通確認結果の記録コミットをマージ済みの`feature/invoice-import`ブランチにpushしてしまった(2026-10-14のPR #109/#111と同種のインシデント)。push後に`gh pr view`で気づき、新規ブランチ`feature/invoice-send-import-verification`を切って該当コミットのみを含め、[PR #123](https://github.com/alphacmc/alphaexapi/pull/123)として作成し直した。

今後、長時間の作業(今回は実MF環境への疎通確認スクリプト実行)の後にpushする際は、都度`gh pr view`でPRのマージ状況を確認する習慣を継続する。

## 2026-10-16 ユーザー単位MF連携の検討開始、債務支払の支払依頼問題はトークン種別と無関係と判明

ユーザーより、MFクラウド連動の登録ユーザー(operator_id/member_id)・支払依頼の申請者(承認フローの起点)がどのユーザーになるか懸念の指摘。alphaexapi・alphadbに影響しうる論点として検討開始。

**調査結果**: 第三者(実際にMFクラウド債務支払のAPI自動化を試みて断念した税理士のブログ記事、https://note.com/kentaro_ajisaka/n/n498f0a735b93 )でも同様の結論。「User TokenとOffice Tokenの両方を実装したが、どちらでも支払依頼(invoice_report)の作成は不可能」「POST /invoice_reportsエンドポイントが存在しない」「承認・差戻し実行もAPIでは操作できない」。つまり**支払依頼の新規作成・承認は、トークンの種類(ユーザー単位かオフィス単位か)に関わらず、そもそもMF側がAPIを提供していない**。

**方針**: 債務支払の支払依頼申請者問題は、ユーザー単位OAuth連携を導入しても解決しないため、既存の「Payable送信ブロッカー」(ユーザーがMF側に確認予定)のまま据え置き、今回のuser単位OAuth連携の検討スコープからは除外する。請求書側のoperator_id/member_id問題(登録ユーザーが実際の担当者と異なる記録になる点)のみを対象に設計を進める方針を提案中(ユーザー確認待ち)。

alphaexapi側で概要設計を固めた上で、alphadb側に必要な変更点(担当者フィールド・ユーザー単位トークン保持テーブル等)を整理し、ユーザーがalphadbセッションへ伝達する進め方で合意。

## 2026-10-16 債務支払の支払依頼API制約、最新仕様書で再確認・確定

ユーザーより「現在CSVで作成してインポートすると、支払依頼が明細付きで作成される。APIではこれができないという理解で良いか」との確認依頼。MF公式の最新OpenAPI仕様書(`https://payable.moneyforward.com/api/index.json?urls.primaryName=external`、user token版、および`...=gateway`、office token版)を直接取得して確認した。

**確認結果**: `invoice_reports`(支払依頼本体)・`general_reports`(経費精算等含む他の申請種別)は、user token・office tokenのいずれの仕様でもGETのみで、新規作成するAPIは存在しない。`invoice_reports/{id}/invoice_transactions`はGET/POSTがあるが、これは既存の支払依頼への明細追加のみ。

**新たな発見**: 承認処理自体(`POST /me/approving_ap_reports/{report_id}/approve`)はAPIとして存在する。ただし支払依頼の容れ物自体を新規作成できない以上、現時点では活用できない。

ユーザーの理解(CSVインポートに相当するAPIは無い)が正しいことを確認。債務支払送信(Plan D送信)はこの制約を理由に検討から除外し、請求書側のユーザー単位OAuth連携の設計のみを進める方針を確定。

## 2026-10-16 請求書のユーザー単位OAuth連携: フル対応で進める方針を確定

operator_id/member_id問題への対応方針をbrainstormingで検討。当初、ユーザー単位OAuth対応は「`MoneyForwardClientService`(全MF API呼び出しが経由)・`MfJobRunner`インターフェース・OAuth認可フロー」に影響する大きな変更と捉えていたが、ユーザーから以下の指摘を受け、想定より小さい変更で済むことが判明:

- 各担当者が自分自身で一度MF側のOAuth認可を行うだけでよく(既存の認可フローをそのまま使う、新しい仕組みは不要)
- MF側の権限が無い人はそもそも認可できない、または認可してもAPI呼び出しが失敗する(MF側が自然に権限管理する。こちら側で権限チェックを作り込む必要はない)
- トークン未登録の担当者は月次送信をトリガーできない、で問題ない(自然な制約)

これを踏まえ、**フル対応(ユーザー単位OAuth)で進める**方針を確定。実装上必要になるのは「`MfOauthToken`の保存キーを製品単位→製品×ユーザー単位に変える」「送信処理が`MfJob.triggeredBy`(既存、Plan E実装済み)のユーザーのトークンを使うよう通す」の2点に整理された。もう一つの選択肢(既存の`MfJob.triggeredBy`記録のみで対応を見送る案)は不採用。

## 2026-10-16 ユーザー単位OAuth連携: 適用範囲・RBACを確定

brainstorming継続。データモデル・認可フローの設計案(`/authorize`のADMIN限定を請求書側のみ撤廃する案)を提示したところ、以下2点の訂正を受けた:

1. **`/authorize`のADMIN限定(`@Roles('ADMIN')`)は変更しない**。月次送信等をトリガーする人は元々ADMINロールの人のみという前提は変わらないため、RBAC自体の緩和は不要。
2. **債務支払(PAYABLE)も請求書(INVOICE)と同じ扱いにする**。送信側(支払依頼作成)は引き続きMF問い合わせ中でブロックされているが、受信側(支払明細のダウンロード等)は請求書と同様にユーザー単位トークンの対象とする。

この訂正により、「ADMINロールを持つ複数人が、各製品でそれぞれ自分自身のトークンを認可する」という統一的な仕組みになり、債務支払側に共有トークン用の特別扱い(センチネル値等)が不要になった。両製品に同じ(`mfProduct`, `userEmail`)複合キーの仕組みをそのまま適用する。

## 2026-10-16 ユーザー単位OAuth連携の全体設計を承認

brainstormingで提示した設計案(データモデル(`MfOauthToken`を(mfProduct, userEmail)複合キー化)・認可フロー(stateペイロードにuserEmailを埋め込みコールバックへ届ける)・影響範囲(MfJobRunner/MfPartnerGateway/MoneyForwardClientServiceインターフェースへの`triggeredBy`伝播))を承認。横断的な変更のため、複数フェーズ(①OAuth基盤本体の拡張→②MoneyForwardClientService/MfPartnerGateway/CustomerSyncServiceへの反映→③MfJobRunnerインターフェース・各ジョブランナーへの反映)に分けて実装計画を進める方針も承認された。

## 2026-10-16 債務支払送信、MF問い合わせの中間報告: CSV生成への方針転換が濃厚

ユーザーよりMF問い合わせの中間報告。支払依頼(invoice_report)を新規作成するAPIは存在しないが、支払依頼明細(invoice_transactions)のCRUD APIは存在するという非対称性についてMF側に質問中とのこと。

ユーザーの見立て: 落としどころとして、**債務支払送信(Plan D送信)は、従来通りインポート用CSVを作成するところまでをalphaexapi側で行い、担当者がMFクラウド債務支払の支払依頼画面でCSVインポートする**運用になりそうとのこと(API経由の「送信」ではなく「CSV生成」に役割が縮小する見込み)。一方、**支払明細の受信(Plan D取込)はAPI経由で可能**そうとのこと(invoice_reports/invoice_transactions等のGET系エンドポイントで対応可能、請求書取込と同様の設計が適用できる見込み)。

この方針はまだMF側の回答待ちのため確定ではないが、Plan D(債務支払送信・取込)の設計時に参照する前提として記録しておく。

## 2026-10-16 MFクラウド連動: CSVエクスポート/インポートの口を残す方針、設計はalphasystemへ

ユーザーより、MFC債務支払のAPI対応結果(送信側のCSV生成方式への転換検討含む)に関わらず、**現行システム(alphaofficesystem)が実現しているCSVエクスポート/インポートの口を、新システムでも残したい**との方針が示された。この設計は複数リポジトリ(alphaexapi・alphasys等)にまたがる全体設計のため、**alphasystemプロジェクト側で検討を進める**ことで合意(本セッション(alphaexapi)では着手しない)。

本セッション終了時点でalphasystemのアクティブセッションは存在しないため、ユーザーが別途alphasystemセッションを開始して引き継ぐ想定。

## 2026-10-16 上位仕様のCSV経路並行維持改訂にalphaexapi設計書を追従

alphasystemの上位仕様(`docs/design/2026-10-09-MFクラウド連動-仕様.md`)が2026-10-16に改訂され、API連携を主軸としつつ移行期間中は現行(alphaofficesystem)同様のCSV手動連携も並行経路として残す方針に変更された（`MfJob`に`source`/`uploadMode`/`deletedCount`追加、新規/追加モード、判定ロジックはAPI経路と共通化）。

ユーザーに今回の対応範囲を確認したところ、**まずalphaexapi設計書の参照更新・矛盾箇所の修正のみ**(CSV経路自体の実装設計は別途brainstormingから着手)と確認された。[PR #128](https://github.com/alphacmc/alphaexapi/pull/128)として対応:
- 設計書ヘッダーの上位仕様参照箇所を2026-10-16改訂に追従
- 0.5章を新設しCSV経路並行維持の概要と「実装設計は別途」である旨を明記
- 7章の各モジュール作業表に、上位仕様11章改訂で追加されたalphaexapiの新規担当範囲(CSVアップロード解析・生成API等)を追記
- **設計書とは別に見つかった既存の乖離も修正**: 3.1章「送信と取込は別ロックで同時に走ってよい」という記述が、実際にはPlan C(請求書取込)実装時の最終レビュー対応で`MF_JOB_LOCK_KEY`に統合済み(取込がBillReciptを書き込み送信がそれを読む依存関係のため)だったため、実装と一致するよう記述を修正した

CSV経路（手動アップロード/ダウンロード）の実装設計は、今後あらためてbrainstormingから着手する。

## 2026-10-16 CSV経路設計: まず請求書(INVOICE)側から着手する方針を確認

alphadb 0.2.4(`MfJob.source`/`uploadMode`/`deletedCount`)を取り込み、CSV経路(上位仕様2.4章)の設計をbrainstorming開始。請求書・債務支払×エクスポート・インポートの4パターンに分かれ範囲が広いため、**請求書(INVOICE)側から先に着手し、債務支払(PAYABLE)側は別途設計する**方針を提案、ユーザー承認(進め方は一任、ただし現行システム(alphaofficesystem)の実装を引き続き参考にする旨の指示あり)。

## 2026-10-16 CSV経路: 文字コードをShift-JIS(MS932)に確定、現行システムの実装詳細を調査

alphaofficesystemの実コードを調査し、CSV経路の仕組みを確認: アップロード画面(`GuploadController`)がファイル種別・対象年月・モード(`mode`)を受け取りSpring Batchジョブを起動、`mode="1"`=追加(そのまま取込)・それ以外=新規(取込前に対象月の既存明細を削除してから取込)という判定ロジックを確認。CSVの文字コードは現行システムと同じ**Shift-JIS(MS932)で統一**する方針を確認(経理担当者がExcelで開く前提、MF側との相互運用性のため)。

## 2026-10-16 請求書CSV経路の設計を承認

brainstormingで提示した設計案(アーキテクチャ・フィールドマッピング・ジョブ統合・エンドポイント)を承認。既存の`InvoiceSendService`/`InvoiceImportService`・`InvoiceImportRepository`・`computeTaxAmounts`・`parseItemName`を再利用し、38列CSVの入出力アダプタを新設する方針。設計書作成に進む。

## 2026-10-16 請求書CSV経路: 行構造違反時の扱いを訂正

設計書作成時、「品目行の前に請求書(ヘッダー)行が無い」場合をSKIP扱いとしていたが、ユーザーより**CSVの構造上、請求書行→1件以上の品目行の繰り返しが保証されており、あり得ないケース**との指摘を受けた。個別行のSKIPではなく、CSV自体の構造異常として例外を投げジョブ全体を`FAILED`にする扱いに修正した。
