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

## 2026-10-20 会話記録を日付別ファイルに切り替え

- **経緯**: alphasystem からの申し送り（`INBOX_FROM_ALPHASYSTEM.md`）で依頼を受けた。全リポジトリ共通の方針として、ユーザーが 2026-10-20 に承認済み。申し送りはこのファイルに取り込んでから削除した。
- **結論**:
  - 以後の会話記録は `docs/conversations/YYYY-MM-DD.md`（日付別）に書く。見出しは従来どおり `## YYYY-MM-DD タイトル`。
  - `docs/conversations/README.md` を置いた（雛形は alphasystem の同名ファイル）。README は Obsidian 同期の対象外。
  - 既存の `docs/conversations.md` は過去分のアーカイブとして残し、追記しない。分割や移動はしない（リンク切れ防止）。10/20 の前半（PR #99 のデプロイ等）の記録はそちらにある。
  - Obsidian 同期と Stop フックは、alphasystem 側で新旧両方の形式に対応済み。`docs/conversations/` ディレクトリがあるかどうかで、フックが書き先を切り替える。
  - `INBOX_FROM_ALPHASYSTEM.md` の取り込み先も、旧 `docs/conversations.md` から当日付の日付別ファイルに変える。
- **確認結果**: 切替後の Stop フックの書き先が `docs/conversations/2026-10-20.md` になることを確認した（`find_conversation_targets` の出力で確認）。変更は Draft PR #103（base: staging）で出した。

## 2026-10-22 alphasystem から申し送り: メール送信（Amazon SES）のインフラ準備

- **経緯**: `INBOX_FROM_ALPHASYSTEM.md` で依頼を受けた。このファイルに取り込んでから削除した。
- **依頼内容**:
  - 背景: 4_7_1 社員情報変更依頼（設計書: alphasystem の `docs/design/2026-10-22-社員情報変更依頼-仕様.md` の 7 章）で、alphaexapi から却下通知とメール変更の確認メールを送る。送信方式は Amazon SES に決定（2026-10-22 ユーザー承認）。送信量は社員約 55 名で月に数十通。
  - 確認・提案すること: (1) 送信元ドメインの DNS をどこで管理しているか、DKIM・SPF を CDK で作れるか、(2) alphaexapi のタスクロールへの `ses:SendEmail`（送信元を制限）、(3) 環境変数（`MAIL_FROM`、リージョン）を既存のシークレット注入の仕組みに乗せる案、(4) staging のサンドボックス解除の申請内容の下書き、(5) 本番は設計だけにとどめる。
  - 進め方: コード修正は、方式案を alphasystem に示して了解を得てから（ブランチ + Draft PR、base=staging）。必要な権限・環境変数は alphaexapi-aa の実装計画と合わせる。SMTP 認証情報の直書きは持ち込まない。cdk deploy は人が実行する。

## 2026-10-22 SES インフラの事前調査と方式案

- **調査結果**:
  - staging の `alphacmc-test.com` は staging アカウントの Route 53 にあり、公開 DNS の委任も一致している。CDK はすでにこのゾーンを参照しているので、DKIM・MAIL FROM（SPF）のレコードまで CDK で作れる。人による DNS 登録は不要。
  - 本番アカウントにあるゾーンは `alphasystem.alphacmc.com` だけ。親の `alphacmc.com` は別アカウントの Route 53 にあり、MX は Google Workspace。`cdk.json` の本番 `domainName`（`alphacmc.com`）と食い違っている（本番着手時に見直す）。
  - SES は staging・本番ともサンドボックス。検証済みの ID は無い。
  - フロントとバックがタスク定義を共有しているため、タスクロールも共有。`AWS_REGION` はすでにバックエンドに渡されている。
- **方式案**: [docs/superpowers/specs/2026-10-22-ses-mail-infra-design.md](../superpowers/specs/2026-10-22-ses-mail-infra-design.md)。要点は次のとおり。
  - 送信元は `no-reply@alphasys.alphacmc-test.com`。DKIM と MAIL FROM（`bounce.alphasys.alphacmc-test.com`）は CDK で作る。
  - `ses:SendEmail` は `ses:FromAddress` の条件で絞る。サンドボックス中は受信者側の ID にも許可が要るため `identity/*` を対象にする。
  - `MAIL_FROM` は機密ではないので、平文の `environment` で渡す（SSM には置かない）。
- **次のアクション**: 方式案を alphasystem に送って了解を得る。環境変数名と、送信の有効・無効を切り替える変数が要るかは alphaexapi-aa と合わせる。了解が出るまでコード修正には着手しない。
- **送付**: 方式案を alphasystem-6b に送った。環境変数名（`MAIL_FROM`、送信の有効・無効を切り替える変数の要否、Reply-To など）は alphaexapi-aa に問い合わせた。どちらも返事待ち。

## 2026-10-22 alphaexapi-aa から SES 用の環境変数について回答

- **回答**: 方式案の前提（`MAIL_FROM=no-reply@alphasys.alphacmc-test.com`、既存の `AWS_REGION` を使う、タスクロールの `ses:SendEmail` に `ses:FromAddress` の条件、アクセスキー無しで SDK のデフォルト認証チェーン、SESv2 の SendEmail）で実装する。
- **追加で注入する変数**（staging、どちらも平文の `environment`）:
  - `MAIL_DRIVER=ses`（`ses` か `stub`。未設定なら `stub` なので、ローカルとテストでは設定不要）
  - `ALPHASYS_BASE_URL=https://alphasys.alphacmc-test.com`（末尾スラッシュなし。確認メールのリンクと、却下メールに載せる画面 URL に使う）。CDK で `https://${subDomain}.${domainName}` から組み立てる。
- Reply-To は今回は不要。alphaexapi 側が alphasystem に送った想定の `APP_BASE_URL` は `ALPHASYS_BASE_URL` に改める（alphaexapi から alphasystem に訂正を送る）。
- サンドボックス中は、結合試験の宛先（試験する社員の mm_adder・email）を事前に SES で検証しておく必要がある。これを試験手順に書いてもらうよう、alphaexapi から alphasystem に伝える。
- 方式案（[specs/2026-10-22-ses-mail-infra-design.md](../superpowers/specs/2026-10-22-ses-mail-infra-design.md) の 3 章・6 章）に反映した。alphasystem の了解はまだ返事待ち。
- **送付**: 追加の2変数（`MAIL_DRIVER`・`ALPHASYS_BASE_URL`）を反映したことを alphaexapi-aa と alphasystem-6b に伝えた。実装は alphasystem の了解が出てから着手し、デプロイ後に alphaexapi-aa に連絡する。

## 2026-10-22 SES 方式案が了承され、実装した

- **回答（alphasystem-6b 経由、ユーザー判断）**:
  - (a) 方式全体を了承。staging は DNS（DKIM・カスタム MAIL FROM の MX と SPF）を CDK で自動登録する。共有タスクロールに `ses:SendEmail`（FromAddress の条件付き）を付ける。`MAIL_FROM`・`MAIL_DRIVER`・`ALPHASYS_BASE_URL` は平文の environment で渡す。リージョンは既存の `AWS_REGION` を使う。
  - (b) DMARC の TXT（p=none）は置く。
  - (c) staging は**サンドボックスのまま**、受信者を検証済みにして試験する。解除の申請は本番の前に行う（申請文の下書きは方式案に残す）。
  - 本番は設計だけにとどめる（staging の目処が立つまで着手しない）。
- **実装**: `feature/ses-mail-infra`（base=staging）。`lib/constructs/ses.ts`（`SesConstruct`）を追加し、`ecs.ts` に省略可能な `mail` を追加、`staging-stack.ts` でつないだ。prod-stack は変更なし。
- **cdk diff**（2026-10-22 実施）: 想定どおり。SES の ID が1件、Route 53 のレコードが6件、IAM のステートメントが1件追加され、タスク定義に3変数が追加される（新しいリビジョンに置き換わる）。`AUTH_URL` に差分は無い。リポジトリにテストは無い（`jest` の対象が0件）。型チェック（`tsc --noEmit`）は通った。
- 試験用の受信者を検証する手順（人の作業）を、方式案の 4.1 に追記した。
- **次のアクション**: (1) Draft PR をユーザーがレビューしてマージする。(2) 人が `npm run deploy:staging` を実行する（直前に `cdk diff` で `AUTH_URL` に差分が無いことを確認）。(3) SES コンソールで、ドメイン ID `alphasys.alphacmc-test.com` が「検証済み」になったことを確認する。(4) 試験用の受信者を検証する（4.1）。(5) デプロイ後に alphaexapi-aa と alphasystem-6b に連絡する。
- **PR**: Draft PR #105（base=staging）を作り、alphasystem-6b に PR・手順書（4.1・4.2）の場所と、デプロイ後の流れを伝えた。

## 2026-10-22 SES インフラを staging にデプロイし、ドメイン ID の検証完了を確認

- **経緯**: PR #105 がマージされた後、ユーザーが `npm run deploy:staging` を実行した（StagingStack は 2026-10-22 16:25 JST に UPDATE_COMPLETE）。
- **確認結果**（CLI で確認）: ドメイン ID `alphasys.alphacmc-test.com` は送信可能（VerifiedForSendingStatus=true）。DKIM は SUCCESS、MAIL FROM ドメインも SUCCESS。
- **確認する画面**: AWS コンソール（staging アカウント 570024666076、東京リージョン）の「Amazon SES」→ 左メニュー「設定: ID（Identities）」→ `alphasys.alphacmc-test.com`。一覧の「ID のステータス」が「検証済み」、詳細の「認証」タブで DKIM と MAIL FROM の状態が見られる。
- **連絡**: alphaexapi-aa と alphasystem-6b に、デプロイ完了と ID の検証完了を連絡した。
- **次のアクション**: 試験用の受信者のアドレスを検証する（方式案の 4.1、人の作業）。

## 2026-10-22 試験用の受信者 yohira@alphacmc.co.jp を SES で検証済みにした

- **経緯**: ユーザーが SES コンソールから `yohira@alphacmc.co.jp` を E メールアドレスの ID として登録した。いったん「検証保留中」（確認メールのリンクがまだ開かれていない状態）になったが、リンクを開いて「検証済み」になった。
- **補足**:
  - `alphacmc.co.jp` は社内のメールサーバー（`mx.alphacmc.co.jp`）で受けている。確認メールが見当たらないときは、迷惑メールの判定や隔離を確認する。
  - 本番は、本番アクセス（サンドボックス解除）を申請してから運用するので、受信者を1件ずつ登録する作業は不要（社員全員・mm_adder 分の登録も要らない）。staging はサンドボックスのままなので、試験の宛先は毎回登録する。
- **次のアクション**: 試験で使うほかの宛先（mm_adder 用のアドレス、メール変更試験の新しいアドレス）は、必要になったら同じ手順で登録する。

## 2026-10-22 staging SES から yohira@alphacmc.co.jp にテストメールを送信

- **経緯**: ユーザーの了解を得て、2026-10-22 16:45 JST に CLI（`aws sesv2 send-email`、staging アカウントの権限）から送信した。送信元は `no-reply@alphasys.alphacmc-test.com`、件名は「[staging] SES 送信テスト」。SES は受け付けた（MessageId `010601a162928f1e-4babebe7-6013-463c-820c-58cdf37638f0-000000`）。
- **補足**: Windows の aws CLI で日本語を含む JSON を `file://` で読ませるときは、`AWS_CLI_FILE_ENCODING=UTF-8` が要る（無いと、ファイルを解釈できないエラーになる）。
- **確認待ち**: 受信箱（迷惑メールフォルダを含む）に届いたか。ヘッダーの SPF・DKIM・DMARC の判定は、ユーザーが確認する。
- **注意**: 今回は個人の CLI 権限で送ったので、ECS タスクロール（alphaexapi からの送信）の権限までは確かめていない。そこは alphaexapi の結合試験で確認する。

## 2026-10-27 alphasys-d3 から依頼: Google Sheets テンプレートID 2変数の ECS 注入

- **依頼**（alphasys-d3 から）: alphasys でマージ済みの2機能が読む環境変数を、ECS タスク（フロントのコンテナ）に注入してほしい。
  - `ORDER_MATCHING_TEMPLATE_SHEET_ID`（課題2_1_4 受発注対応表、alphasys PR #288）。値は `1KBREddvkJTiAAk9ELmRKEv16pkU-knNRldNztMMJhFY`（2026-10-23 作成の「受発注対応表_テンプレート」）。
  - `BILL_PROFIT_TEMPLATE_SHEET_ID`（課題3_1_13 受発注採算表、alphasys PR #290）。値は alphasys 側の記録に無いので、ユーザーに確認する。
  - いまは `SKILL_TEMPLATE_SHEET_ID` だけが注入されているため、デプロイ環境ではこの2機能のテンプレートIDが未定義になり、動かない見込み。
- **調査**: `SKILL_TEMPLATE_SHEET_ID` は、`bin/app.ts` の必須変数リスト、`lib/constructs/ecs.ts` のフロントコンテナの `environment`、`.env.example`、`docs/構築・メンテナンス手順.md` の4か所で扱っている。値は共通の `.env` に置いているので、staging と本番で同じテンプレートを使う前提になっている。alphasyscdk に、関連する対応済みの PR は無い。
- **方式案**: 2変数を `SKILL_TEMPLATE_SHEET_ID` と同じ4か所に追加し、必須変数にする（未設定ならデプロイ前に止まる）。値を置く場所は、staging と本番で同じなら `.env`、別なら `.env.staging` / `.env.prod`（`.example` も同じ扱い）。
- **ユーザーに確認すること**: (1) `BILL_PROFIT_TEMPLATE_SHEET_ID` の値、(2) staging と本番で同じテンプレートを使うか、(3) 必須変数にしてよいか。
- **その他**: 2026-10-22 の記録の追記分（SES のデプロイ・検証・テスト送信）が、staging 上で stash されたままになっていた。これを戻した（今回のブランチでまとめてコミットする）。
- **ユーザー回答（.env 方式の場合の前提）**: staging と本番で**同じテンプレート**を使う（値は共通の `.env`）。2変数は**必須**にする。`BILL_PROFIT_TEMPLATE_SHEET_ID` の値は**まだ無い**（後で伝える）。

## 2026-10-27 alphasystem-27 から設計依頼: テンプレートの変更管理（案A）

- **依頼**（alphaexapi-92 経由。ユーザー承認済み「案Aでお願いします」。経緯は alphaexapi の `docs/conversations/2026-10-27.md`「Google Sheetsテンプレートの置き場所と変更管理の方針」、Draft PR #169）:
  - 現状: テンプレートの実体は Drive 上にしか無く、ID は alphasyscdk の `.env`（git 管理外）にしか無いので、変更を管理できない。
    - スキルシート（`SKILL_TEMPLATE_SHEET_ID`）は、共有ドライブ `04_resource/skillsheet/スキルシート_原本` にある（サービスアカウント googledrivemanager などが管理者、ドメイン全員が閲覧可）。
    - 受発注対応表は yohira のマイドライブにあり、本人にしか共有されていない（他の人が出力するとコピーの権限エラーになる見込み）。
    - 受発注採算表は未作成。
  - 案A: `alphasyscdk/templates/*.json` にテンプレートの定義（値・列幅・行の高さ・結合・罫線・書式）を置き、PR でレビューする。`scripts/templates-export.ts` で Drive 上の作業用シートから JSON を書き出す。`scripts/templates-deploy.ts --env staging|prod` で `04_resource/templates/{env}/` に、ID を変えずに作成・更新する。認証はサービスアカウント googledrivemanager の鍵（Parameter Store の `GOOGLE_CREDENTIALS_JSON`）。ID は `template-ids.{env}.json`（git 管理）に書き、CDK が読んで `*_TEMPLATE_SHEET_ID` に入れる。staging と本番でテンプレートを分ける。cdk deploy とは別のスクリプトにする。
  - 先に試作で確かめること: (1) スキルシート_原本を JSON に書き出して作り直したときの再現度（条件付き書式・入力規則・保護範囲）、(2) ID を変えずに中身を差し替える方法、(3) ローカルから Parameter Store の鍵を使えるか。
  - 返すもの: 試作の結果を含む方式案。了解後に着手する（ブランチ + Draft PR、base=staging。デプロイと Drive への配置は人が実行）。
- **影響**: 案A は、alphasys-d3 から依頼された .env 方式の追加を置き換える。受発注の2機能を「二段構え（いったん手作業で 04_resource に置き、.env 方式で先に動かして、後で案A に移す）」にするか「案A ができるまで待つ」かは未決。**回答が出るまで .env 方式の追加は進めない**（alphasystem の指示）。
- 補足: ユーザーが「同じテンプレートを使う」と答えたのは .env 方式の場合の前提。案A では staging と本番を分ける提案になっていて、食い違っている。

## 2026-10-27 受発注の2機能は二段構えで進める・案Aの試作を始める（ユーザー決定）

- **決定1（ユーザー）**: 受発注の2機能は**二段構え**にする。先に、テンプレートを手作業で共有ドライブ `04_resource` に置き、.env 方式（必須変数、staging と本番で共通の値）で動かす。案A ができたら、そちらに移す。
  - 受発注対応表のテンプレートは、いまはユーザーのマイドライブにあり本人にしか共有されていないので、`04_resource` への移動が必要（人の作業）。
  - `BILL_PROFIT_TEMPLATE_SHEET_ID` は値がまだ無い（テンプレートが未作成）。必須変数にするので、値が揃うまで staging へのデプロイは止まる。
- **決定2（ユーザー）**: 案A の試作を始めてよい。Parameter Store のサービスアカウント鍵をローカルで使う。原本は読むだけにする。作り直しの確認用のシートは、試作用の場所に作り、終わったら削除する。
- **段取り**: (1) .env 方式の変更を `feature/sheet-template-env-vars`（base=staging）で実装し、Draft PR を作る。(2) alphasystem-27 と alphasys-d3 に決定を連絡する。(3) 案A の試作をして、方式案を alphasystem-27 に返す。
- **実施**: .env 方式の変更を Draft PR #107（`feature/sheet-template-env-vars`、base=staging）で出した。`tsc --noEmit` は通った。`cdk diff` は、`BILL_PROFIT_TEMPLATE_SHEET_ID` の値が無く必須変数のチェックで止まるため、未実施。alphasystem-27 に決定を、alphasys-d3 に PR とデプロイの前提を連絡した。
- **デプロイの前提（人の作業）**: (1) 受発注対応表のテンプレートを `04_resource` に移す、(2) 受発注採算表のテンプレートを作る、(3) `.env` に ID を書く、(4) `cdk diff` を確認してから `deploy:staging`。

## 2026-10-27 案A の試作（読み取り）と方式案

- **試作**: スキルシート_原本を、Sheets API（ユーザーの権限、読み取りのみ）で調べた。シート1枚（12行×56列）。値（数式は無い）、書式・罫線、結合44か所、列幅・行の高さ（12行目 130px）、メモ5件。条件付き書式・入力規則・保護範囲は無い。使われている要素は、すべて API で書き出し・作り直しができる。扱えないのは図形・画像と Apps Script だけ。
- **ID を保つ方法**: 1回の batchUpdate で、シートを足して内容を書き、古いシートを消し、元の名前と位置に戻す。gid は変わるが、alphaexapi は sheetId を実行時に読んでいるので影響しない。
- **重要な発見**: `GOOGLE_CREDENTIALS_JSON`（サービスアカウント googledrivemanager の鍵）は、Parameter Store（staging・本番）にも Secrets Manager にも登録されていない。ECS への注入も無い（漏えい対応で無効にした後、再発行されていない）。そのため、作り直しの往復の試験はしていない（Drive に試作用のシートは作っていない）。
- **方式案**: [specs/2026-10-27-sheet-templates-design.md](../superpowers/specs/2026-10-27-sheet-templates-design.md)。認証は A-1（新しい鍵を発行して Parameter Store に登録）を推奨。
- **送付**: alphasystem-27 に送った。返事待ち（方式の了解、認証方式と鍵の発行者、alphaexapi の ECS 注入も直すか）。

## 2026-10-27 案A の方式が了承された（alphasystem-27 から回答）

- **了承**: 方式（1）は全体を了承。`templates/*.json`、`scripts/templates/export.ts`・`deploy.ts`、`template-ids.{env}.json` を CDK が読む構成、`04_resource/templates/{staging,prod}/` への配置、図形・画像・Apps Script を使わない運用ルール、gid が変わっても影響しないこと。`.env` と必須変数リストから外す（PR #107 の分も移す）ことも了承。
- **往復の試験**は、鍵が用意できてから行い、結果を方式案に追記する。
- **認証（2）と鍵の発行**は、alphasystem からユーザーに確認する（漏えい対応で無効にした経緯があり、Google 側の管理者権限が要るため）。alphasystem の見解は A-1。鍵の保管は SSM だけにし、`.env`・git・ログには出さない。決まるまで、デプロイスクリプトの実行部分は作りかけでよい。
- **（3）ECS への注入も一緒に直す**: alphaexapi の Drive を使う既存の機能（追加シートの保存・取得など）は、いま staging・本番で鍵が無いため動かない見込み。鍵が用意できてから、`/alpha/{env}/alphaexapi/GOOGLE_CREDENTIALS_JSON` を ECS の secrets に注入する PR を別に作る。
- **段取り**: `feature/sheet-templates`（PR #107 のブランチから派生、base=staging）で、スクリプトと CDK の読み込みを実装する。鍵が無くても確かめられる範囲（正規化とリクエストの組み立て）をオフラインで確認する。Drive での実行と往復の試験は、鍵が用意できてから行う。
- **実装**（`feature/sheet-templates`）: `scripts/templates/`（template-def・google・files・export・deploy）、`templates/`（manifest・drive-folders・template-ids.{staging,prod}・README）、`lib/template-sheet-ids.ts`（CDK が ID を読み、無ければ synth を止める）を追加。3つの `*_TEMPLATE_SHEET_ID` を `.env`・必須変数リストから外した。テスト（jest、7件）は、手元の簡易版で batchUpdate を適用する往復の確認を含めて通った。`tsc` を通すため、tsconfig に `skipLibCheck` を足した（`@aws-sdk/client-ssm` が引き込む `@smithy` の型定義が、`@types/node` 20.14 と合わないため）。
- **確認**: `templates:deploy --dry-run` は Google API を呼ばずに動く。`templates:export` は鍵が無いため `ParameterNotFound` で止まる（想定どおり）。`cdk synth` は ID が無いため止まる（想定どおり。マージは staging の ID が揃ってから）。
- **PR**: Draft PR #108（base=staging、#107 から派生）。alphasystem-27 に、PR とマージの前提を連絡した。
- **残り（鍵が用意できてから）**: (1) 鍵の発行と SSM への登録（alphasystem がユーザーに確認中）、(2) `04_resource/templates/staging/` のフォルダ ID、(3) 3テンプレートの export、(4) `deploy --env staging`、template-ids のコミット、往復の確認結果を方式案に追記、(5) ECS への `GOOGLE_CREDENTIALS_JSON` 注入の PR（別）。

## 2026-10-27 サービスアカウント鍵の発行・登録手順を文書にした

- **経緯**: alphasystem-27 から依頼を受けた。ユーザーは「以前に発行した記憶はあるが、手順が分からない」。リポジトリの文書にも発行手順が無かった。
- **実施**: `docs/google-service-account-key.md` を追加し、構築手順書と SECRETS.md からリンクした。内容は、事前確認（Drive API・Sheets API が有効か、組織ポリシー `iam.disableServiceAccountKeyCreation`）、古い鍵の確認、発行（「鍵」タブ →「鍵を追加」→「新しい鍵を作成」→ JSON）、Parameter Store への登録（`MSYS_NO_PATHCONV=1`・`AWS_CLI_FILE_ENCODING=UTF-8`）、値を表示しない確認（`client_email` だけを表示）、共有ドライブの権限、登録後の作業。鍵の値は書いていない。
- **分かったこと**: GCP プロジェクトは `alphadevs-348511`、サービスアカウントは `googledrivemanager@alphadevs-348511.iam.gserviceaccount.com`。無効にした旧鍵の、機密でない項目（alphaexapi の git 履歴の `project_id`・`client_email`）から確認した。
- **方針（文書に書いたもの）**: staging と本番で別々の鍵を発行する。2024 年 5 月以降に作った組織では鍵の作成が既定で禁止されているので、禁止されていたら A-2 に切り替えるか、組織の管理者に例外を依頼する。
- **未確認**: 画面の項目名は、実際のコンソールでは確認していない（コンソールに入る権限が無いため）。ユーザーが発行するときに食い違いがあれば直す。

## 2026-10-27 リポジトリ直下のサービスアカウント鍵ファイルを .gitignore の対象にした

- **経緯**: ユーザーが alphasyscdk 直下でサービスアカウントの鍵のファイル（`alphadevs-348511-efee06b006db.json`、最終更新 2026-07-28 10:01）を見つけた。alphasystem-27 によると、このファイルは `.gitignore` の対象外で、未追跡として出ていた。alphasystem-27 が、この PC の `.git/info/exclude` に `alphadevs-*.json` を足して応急処置をした。
- **確認（alphasyscdk）**: すべてのローカルブランチとリモートブランチのツリー、および `git log --all` に、このファイル（と `credentials` を含むファイル）は無い。**コミットも push もされていない。** 中身は開いていない。
- **対処**: PR #108 のブランチで `.gitignore` に追加した。`alphadevs-*.json`、鍵の既定のファイル名（`*-<16進12桁>.json`）、`credentials.json`、`*service-account*.json`。追跡中のファイルが新たに除外されないことを `git ls-files -ci --exclude-standard` で確認した。
- **以後のルール**: このリポジトリでのステージングは、`git add <ファイル名>` で1件ずつ行う。`git add -A` / `git add .` は使わない（alphasystem-27 の依頼）。
- **保留**: このファイルの鍵が、7 月に無効にした鍵なのか、有効な鍵なのかは、alphasystem がコンソールで照合中。照合が済むまで Parameter Store には登録しない。
- **補足（ユーザー）**: 鍵ファイルは、ユーザーがこの日に置いたばかりで、すでに削除した（最終更新の 2026-07-28 は、ダウンロードした日時）。作業フォルダに長く置かれていたわけではない。削除されたことを確認した。

## 2026-10-27 受発注採算表テンプレートの作成を alphaexapi に依頼

- **決定（ユーザー）**: テンプレートの作成は alphaexapi に依頼する。
- **依頼**（alphaexapi-92 へ送付）: alphasys の `create-bill-profit-sheet.action.ts`（課題3_1_13、PR #290）の前提（行の高さ 21px、書き込むセルの位置、行の複製の仕方）に合う受発注採算表のテンプレートを作る。前提は alphasys-d3 に確認しながら進める。置き場所は共有ドライブ `04_resource`（ドメイン全員が閲覧可）。図形・画像・Apps Script は使わない。作ったら ID を alphasyscdk-85 と alphasystem-27 に連絡する。
- 受発注対応表の `04_resource` への移動（ファイルの持ち主の作業）も alphaexapi が扱うかは、alphaexapi からユーザーに確認してもらう。
- **次のアクション**: ID の連絡を受けたら、`.env` に書いて PR #107 の `cdk diff` → デプロイ（人）へ進める。

## 2026-10-27 受発注採算表テンプレートの ID を受領し、PR ＃107 の cdk diff を確認

- **受領**（alphaexapi-92 から）: `BILL_PROFIT_TEMPLATE_SHEET_ID = 111RNAg4624G2X1v_6GrkUkZzfaoRLAAz_54A1-c5R60`。場所は共有ドライブ `04_resource/templates/work/受発注採算表_テンプレート`。タブ0「取引先別」（A〜I列）、タブ1「部門別」（A〜J列）。2行目がモデル行（21px）、3行目が合計行。alphasys-d3 に前提を確認済み。
- **フォルダ**（ユーザー了承済み）: `04_resource/templates/`（`1AeJvvw_srUO-ixh6zRzp1oaWTv_Q-mHl`）、`04_resource/templates/work/`（`1SPm-XQU6of-_83oEBVyXQVFNLCi37_EV`、人が編集する作業用で export の元）。`staging/`・`prod/` は案A で deploy するときに作る（`drive-folders.json` はそのとき記入）。
- **実施**: この PC の `.env` に、`ORDER_MATCHING_TEMPLATE_SHEET_ID`（`1KBREddvkJTiAAk9ELmRKEv16pkU-knNRldNztMMJhFY`）と `BILL_PROFIT_TEMPLATE_SHEET_ID` を追記した（1段目は staging と本番で共通の値）。PR #107 のブランチで `npm run diff:staging` を実行した。SharedStack は差分なし。StagingStack はタスク定義に2変数が加わるだけ（新しいリビジョンに置き換わる）。`AUTH_URL` に差分は無い。
- **残り（ユーザーの作業）**: (1) 受発注採算表・受発注対応表のテンプレートに、ドメイン全員の閲覧権限を付ける（alphaexapi のツールではドメイン単位の権限を付けられない。済むまで、本人と共有ドライブのメンバー以外は出力できない見込み）。(2) スキルシート_原本と受発注対応表を `templates/work/` に移す（ID は変わらない）。(3) PR #107 をマージし、`npm run deploy:staging` を実行する（別の PC からデプロイするときは、その PC の `.env` にも2つの値を書く）。

## 2026-10-27 鍵の照合が済み staging に登録された・注入の PR ＃109・デプロイは1回にまとめる

- **連絡**（alphasystem-27 から）: 鍵 ID `efee06b006db…` は有効だと、ユーザーがコンソールで確認した。ユーザーの依頼で alphasystem が staging の `/alpha/staging/alphaexapi/GOOGLE_CREDENTIALS_JSON`（SecureString、バージョン 1）に登録した（値は表示していない）。本番は未登録（本番の準備ができてから、別の鍵で）。`04_resource` のフォルダ構成（`templates/work/` は編集用、`templates/staging・prod/` は deploy 専用）は了承。
- **実施**: ECS への注入の Draft PR #109（`feature/inject-google-credentials`、base=staging）を作った。PR #107 はすでにマージ済み（2026-10-27 17:09 JST、未デプロイ）だったので、#109 はそのあとの staging から派生させた。マージ済みのローカルブランチ `feature/sheet-template-env-vars` は削除した。cdk diff: タスク実行ロールにパラメータの読み取り権限、タスク定義に `GOOGLE_CREDENTIALS_JSON`（secrets）と #107 の2変数が加わる。`AUTH_URL` の差分なし。
- **決定（ユーザー）**: #109 をマージしてから、`deploy:staging` を**1回**実行する（#107 を単独で先にデプロイはしない）。デプロイで Bastion が置き換わり、夜間移行のタイマーが消えるため（タイマーはユーザーが 4_7_1 の結合試験の前後で扱う）。
- **次のアクション**: 案A の往復試験（export と deploy）。試作用のシートは、試作用の場所に作り、終わったら削除する。

## 2026-10-27 案A の往復の試験に成功

- **実施**: staging の鍵で、スキルシート・受発注対応表・受発注採算表の原本を読んだ。試作用のスプレッドシート（`04_resource/templates/` に「【試作・削除予定】往復試験_<名前>」の名前で作成）に書き込み、読み直して比べた。2回入れ替えて、ID が変わらないことも確かめた。試作用のファイルは試験の後に削除した。原本には書き込んでいない。試験のスクリプトは使い捨て（scratchpad）で、リポジトリには入れていない。
- **結果**: 3つとも、1回目・2回目ともに差分0件。ID も変わらなかった。スキルシートはリクエスト61件（セル125件、結合44件）、受発注採算表はシート2枚。
- 方式案の 2 章 (4) に結果を追記し、状態を「了承済み」にした。
- **次のアクション**（PR #108 のマージ前）: (1) スキルシート_原本と受発注対応表を `templates/work/` に移す（ユーザー）、(2) `04_resource/templates/staging/` を作って `drive-folders.json` に ID を書く、(3) 3つを `templates:export` で書き出してコミットする、(4) `templates:deploy --env staging` で配置して `template-ids.staging.json` をコミットする、(5) #109 と #107 のデプロイの後で、#108 をマージしてもう一度デプロイ（ID が `templates/staging/` のものに替わる）。

## 2026-10-27 ＃108・＃109 がマージ済みと判明。案A を仕上げて staging に配置し、デプロイは1回にまとめる

- **判明**: PR #108 と #109 は、どちらも 2026-10-27 18:21 JST に staging にマージされていた。#108 のため CDK は `templates/template-ids.staging.json` から ID を読むが、中身が空だったので `deploy:staging` は synth で止まる状態だった（何も変更されずに止まる）。#108 のブランチに push した記録2件は未マージだったので、新しいブランチに移した。
- **決定（ユーザー）**: 案A を仕上げてから、StagingStack を1回でデプロイする（#107・#108・#109 をまとめて反映。Bastion の置き換えは1回）。つなぎで今の ID を入れる案は採らない。alphasystem-27 の推奨も同じ。staging のフォルダは deploy スクリプトが初回に作る（alphasystem 了承）。
- **実施**（`feature/templates-staging-deploy`）:
  - deploy スクリプトを直した。`templates/{env}/` フォルダが無ければ作り、`drive-folders.json` に書く（`parent`＝`04_resource/templates/` を追加）。フォルダにドメイン全員の閲覧権限が無ければ付ける（`readerDomain`）。export する JSON の数値の配列を1行にした。
  - 3つの原本（ID は移動しても変わらない）を `templates:export` で書き出した（`skillsheet.json`・`order-matching.json`・`bill-profit.json`）。
  - `templates:deploy --env staging` を実行した。`04_resource/templates/staging/`（`1w2QpsvuffSC8lr0wKUPlcPdQEwfYQ9xE`）を作り、スキルシート（`1gCyhpGHmrsX7V86mbFUls0HtW1h41kqdCdMor7vnzKE`）・受発注対応表（`13k890mASzd4Pmwv2ESHm3bAICsRO7S4YP6tXLFtOGdY`）・受発注採算表（`1y-xkGVrQSWls9w9ObDv5Ojp6CeCEV1xzDt7wD-S22As`）を作成した。3つとも往復の確認で定義と一致した。
  - cdk diff: タスク定義のテンプレート ID 3つが staging/ のものになる。#109 の `GOOGLE_CREDENTIALS_JSON` と、タスク実行ロールの読み取り権限も加わる。`AUTH_URL` の差分なし。
- **未完了**: `templates/staging/` フォルダへの、ドメイン全員の閲覧権限の付与。スクリプトの実行が、権限の付与にあたるためブロックされた（共有設定はユーザーの判断）。付与されるまで、共有ドライブのメンバー以外はテンプレートをコピーできない（いまの原本はドメイン全員が閲覧可なので、このままデプロイすると、メンバー以外のスキルシート出力が失敗する）。
- **PR**: Draft PR #111（base=staging）。alphasystem-27 に連絡した。
- **次のアクション**: (1) ユーザーが `templates/staging/` にドメイン（alphacmc.co.jp）全員の閲覧権限を付ける（Drive の画面、または `templates:deploy` を実行）、(2) この PR をマージ、(3) `deploy:staging` を1回実行。

## 2026-10-27 StagingStack をデプロイ（＃107・＃108・＃109・＃111 を1回で反映）、Bastion が置き換わった

- **ユーザーの作業**: `templates/staging/` フォルダに、alphacmc.co.jp 全員の閲覧権限を付けた（中のテンプレートに継承されていることを確認済み）。PR #111 をマージし、`deploy:staging` を実行した。
- **確認**: StagingStack は 2026-10-27 19:22 JST に UPDATE_COMPLETE。ECS はタスク定義 `staging-alphasys-unified:81`、desired=1 / running=1、ロールアウトは COMPLETED。
- **Bastion**: 置き換わった（新しいインスタンス `i-08f13fc70ac372bde`、19:22 JST 起動）。新しいインスタンスには夜間移行の資材・設定・タイマーが無いので、復旧するまで夜間移行は止まる。最後の実行は `nightly-20261027-010001`。
- **復旧手順**（alphadb `prisma/doc/migration/nightly_automation.md` §7 → §9.3）: (1) 手元 PC で `bash prisma/doc/migration/nightly/deploy.sh`、(2) Bastion で `sudo bash /opt/alphadb-migration/nightly/setup_bastion.sh`、(3) `/etc/alphadb-migration.env` を作り直す（`DST_PGHOST`＝DB クラスタのエンドポイント、`SECRET_ID`＝StagingStack の出力 `MasterSecretArn`、`LOG_GROUP=/alphasys/staging/nightly-migration`。権限 0640 root:postgres）、(4) `sudo systemctl start alphadb-migration.timer`（setup が enable 済み）、(5) 翌朝 CloudWatch で `RESULT: SUCCESS` を確認する。4_7_1 の結合試験中に止めておく場合は、(4) を行わず `disable --now` にする。
- **元のシートの扱い（ユーザーの質問への回答）**: 書き出しに使った元のシート（スキルシート_原本・受発注対応表・受発注採算表）は**消さない**ことを勧めた。案A では `templates/work/` に置いた作業用のシートが、次に変更するときの編集元（export の元）になるため。消さずに `templates/work/` に移す（受発注採算表はすでに work/ にある）。

## 2026-10-27 テンプレートはドメインに公開せず、共有ドライブから継承した権限だけで読む（方針変更）

- **決定（ユーザー、alphaexapi-92 経由で連絡。alphaexapi の記録は PR #174）**: 先に了承していた「テンプレートをドメイン全員が閲覧できるようにする」を取り消す。alphasys を使う社員は全員が共有ドライブのメンバーなので、継承した権限で足りる。`04_resource/templates/` 配下はドメインに公開しない。
- **Drive の現状（alphaexapi が確認）**: 作業用の3ファイルは `templates/work/`（`1SPm-XQU6of-_83oEBVyXQVFNLCi37_EV`）にあり、継承は有効（`inheritedPermissionsDisabled=false`）。スキルシート_原本についているドメインの閲覧権限は、ユーザーが外す。
- **扱い**: 共有ドライブの管理者権限によって全社員がテンプレートを編集できる。変更は Git で管理し、Drive で直接直したものは次の deploy で上書きされる。
- **alphasyscdk への影響（ユーザーの了解待ち）**: PR #111 でマージ済みの deploy スクリプトに、ドメインの閲覧権限を付ける処理がある（`ensureEnvFolder` の `permissions.list` / `permissions.create`、`drive-folders.json` の `readerDomain`）。これを外し、`templates/README.md` と方式案 §3「権限」を直す案を提示した。`templates/staging/` に手作業で付けたドメインの閲覧権限を外すかどうかも、ユーザーに確認中。

## 2026-10-28 テンプレートの Drive 権限の構成が確定（ドメインの権限なし）

- **alphaexapi-92 から連絡（alphaexapi の記録は PR #177）**: `04_resource/templates/` と `templates/work/`、その中の3つのテンプレートの権限を、次の構成にそろえた。
  - 管理者: yohira と googledrivemanager
  - 閲覧者: account@、user@、manage@、executive@ の4グループ
  - ドメインの権限: 無し
  - テンプレートは継承した権限で読む前提なので、deploy でファイルやフォルダの permissions を操作する必要は無い。googledrivemanager は管理者のままなので、deploy（作成・更新）はこれまでどおりできる。
- **こちらで確認（読み取りのみ）**: `templates/` とスキルシート_原本は、上の構成どおりだった。`templates/staging/` には、2026-10-27 に手作業で付けたドメイン（alphacmc.co.jp）の閲覧権限が残っている。中の3つのテンプレートにも継承されている。
- **ユーザーの判断待ち**: (1) deploy スクリプトから、ドメインの閲覧権限を付ける処理（`ensureEnvFolder` の `permissions.list` / `permissions.create`、`readerDomain`）を外す修正に着手するか（PR #115 に追加する）。(2) `templates/staging/` のドメインの閲覧権限を外すか（外すのはユーザーの作業）。(3) alphasys が使うのは `templates/staging/` に deploy したテンプレートで、`work/` は編集用、という理解でよいか。

## 2026-10-29 alphasystem からの申し送り（課題表6件）を取り込み、alphasyscdk担当分を確認

- **経緯**: `INBOX_FROM_ALPHASYSTEM.md`（2026-10-28付、ユーザーが5リポジトリのstagingへpush）で依頼を受けた。設計全体はalphasystemの`docs/design/2026-10-28-alphasys課題表6件-設計.md`（PR #122、マージ済み）。決定の記録はalphasystemの`docs/conversations/2026-10-28.md`。このファイルに取り込んでから削除した。
- **alphasyscdkの担当は3点**:
  1. 2_1_9/3_1_17: `templates/work`の受発注対応表・受発注採算表のモデル行に細い格子罫線を付ける
  2. 5_5_4: alphaexapiのタスクロールに`ec2:DescribeImages`を追加
  3. 5_5_3: 既存のSES権限（`ses:SendEmail`）で足りるか確認
- **確認結果**:
  - **2（IAM）**: `ec2:DescribeImages`は`lib/constructs/ecs.ts:135`に既に付与済み。**追加不要**。
  - **3（SES）**: `lib/constructs/ses.ts`の`grantSend()`は`resources: identity/*`・`condition: ses:FromAddress=MAIL_FROM固定`で、宛先アドレスの制限は無い。5_5_3は宛先が`<ユーザー名>@alphacmc.co.jp`と可変だが、FROMは既存の`MAIL_FROM`を使う想定なので既存権限で足りる。**追加不要**。
  - **1（罫線）**: `templates/bill-profit.json`（受発注採算表）は、2行目（モデル行）に既にA〜I列/A〜J列全列でSOLID幅1の罫線（top/left/right）があり、3行目（合計行）のtop罫線（DOUBLE）が2〜3行目の境界を埋めている。**既に条件を満たしており追加不要**。
    一方`templates/order-matching.json`（受発注対応表）は現状ヘッダー行（1行目、A1〜G1の7セル）のみで、モデル行（2行目）自体が存在せず書式も無い。**こちらは追加作業が必要**。
- **残作業**: `order-matching.json`に2行目（モデル行、A2〜G2）を細い格子罫線付きで追加する。ただし`templates/*.json`は「手で書かない（exportで書き出す）」運用（`templates/README.md`）のため、本体の`04_resource/templates/work/受発注対応表_テンプレート`（ID: `1KBREddvkJTiAAk9ELmRKEv16pkU-knNRldNztMMJhFY`）側を編集してから`npm run templates:export -- --name order-matching --from <ID>`で書き出す必要がある。編集方法（自分でGoogle SheetsのMCPツールから直接編集するか、ユーザーに手動編集を依頼するか）はユーザーに確認中。

## 2026-10-29 受発注対応表テンプレートにモデル行（罫線）を追加

- **承認**: templates/work配下の編集を、ユーザー了承のうえGoogle SheetsのMCPツールから直接実施する方式で進めることにした（手動編集との選択肢を提示し、(a)を選択）。
- **実施**: `受発注対応表_テンプレート`（ID: `1KBREddvkJTiAAk9ELmRKEv16pkU-knNRldNztMMJhFY`）のA2:G2に、`updateBorders`で細い格子罫線（SOLID・幅1・黒、上下左右）を追加した（`templates/bill-profit.json`のモデル行と同じ書式）。追加前にA2:G2が空であることを確認済み。
- `npm run templates:export -- --name order-matching --from 1KBREddvkJTiAAk9ELmRKEv16pkU-knNRldNztMMJhFY`で書き出し、`templates/order-matching.json`に反映（セル7件→14件）。
- **運用方針の確認**: `04_resource/templates/work/`フォルダ自体はコード上必須ではない（`templates:export --from <ID>`は任意のシートIDを指定でき、`scripts/templates/export.ts`にフォルダへの依存は無い）ことを確認し、ユーザーに回答した。ただし編集元を1箇所に決めておく運用は引き続き推奨。

## 2026-10-29 受発注対応表テンプレートをstagingへデプロイし、課題表6件のalphasyscdk担当分が完了

- PR #117をマージ後、ユーザーが`npm run templates:deploy -- --env staging --name order-matching`を実行。`staging`配置先（ID: `13k890mASzd4Pmwv2ESHm3bAICsRO7S4YP6tXLFtOGdY`）の中身を入れ替え、往復確認で定義と一致した。
- これで2026-10-28の申し送り（課題表6件のうちalphasyscdk担当3点: 罫線・IAM・SES）はすべて完了した。

## 2026-11-02 申し送り2件を取り込み（受発注対応表のタイトル行の罫線、業務経歴書の「資格・特殊技能」見出し 4_6_1）

`INBOX_FROM_ALPHASYS.md`（alphasys、2026-11-01）と `INBOX_FROM_ALPHASYSTEM.md`（alphasystem が alphaexapi の依頼を中継、2026-11-02）を取り込み、両ファイルを削除した。

### 1. 業務経歴書テンプレートの「資格・特殊技能」の見出しが表示されない（課題4_6_1、alphasys から）

- ユーザー承認済み（2026-11-01、alphasys のセッションで「4_6_1 は alphasyscdk へ依頼」）。
- 対象: `templates/skillsheet.json` の Z4（結合セル Z4:AC8、`wrapStrategy: WRAP`、中央寄せ）。今の値は `"資　　　格" + 全角スペース多数 + "特殊技能"`。旧システムの Excel で、列幅に合わせてスペースで2行に見せていた作りと思われる。Google Sheets では折り返す位置が違い、スペースの行だけが見えている可能性が高い。
- 依頼された修正: Z4 の値を改行入りにする（例: `"資　格\n特殊技能"`）。実物で見え方を確認したうえで、staging・本番のテンプレートに反映する。
- 関連: 4_6_2（資格が1セルに全部入る）は alphasys 側で直す（資格を改行で分割して AD4〜AD8 に出す）。AD4〜AD8 の書式は変えなくてよい。
- 完了したら、PR 番号と反映先（staging／本番）を alphasys に知らせる（セッションが無ければ alphasys 直下に `INBOX_FROM_ALPHASYSCDK.md`）。

### 2. 受発注対応表テンプレートのタイトル行（1行目）に罫線がない（alphaexapi から、alphasystem 経由）

- 経緯: サプレス（alphaexapi PR #181）の実機確認で見つかった。記録元は alphaexapi の Draft PR #197（`docs/conversations/2026-11-02.md`）。原因はテンプレートで、alphaexapi の修正は不要。
- 対象: staging の受発注対応表（`13k890mASzd4Pmwv2ESHm3bAICsRO7S4YP6tXLFtOGdY`、`templates/order-matching.json`）。10/29 の対応（PR #117）はモデル行（2行目）だけで、タイトル行は含めていなかった。
- **確認結果**（`templates/*.json`）:
  - 受発注対応表: A1〜G1 に罫線が無い（2行目の上の罫線で、1行目の下だけは線が見える）。**直す必要がある**。
  - 受発注採算表: 取引先別の A1〜I1、部門別の A1〜J1 とも、上下左右に SOLID 幅1 の罫線がある。**直す必要は無い**。

### 進め方（ユーザーの了解待ち）

- 10/29 と同じく、`templates/work/` の作業用シートを編集してから `templates:export` で書き出し、PR → マージ → `templates:deploy --env staging` の順で進める案を提示した。
  - 受発注対応表: A1:G1 に、受発注採算表のタイトル行と同じ罫線（SOLID・幅1・黒、上下左右）を付ける。
  - 業務経歴書: Z4 を `"資　格\n特殊技能"` にする。staging に deploy した後、実物の見え方をユーザーに確認してもらう。
- 本番のテンプレートはまだ作っていない（`template-ids.prod.json` は空）。本番の初回 deploy のときに、この修正も含めて作られる。

## 2026-11-02 テンプレート2件を作業用シートで直して書き出した（ユーザー承認「着手してください」）

- **承認**: 上の進め方で着手することを、ユーザーが了承した。
- **事前確認**: 編集する前に、作業用シートを書き出して git の定義と比べた。差は改行コード（CRLF/LF）だけで、中身は一致していた（Drive で直接直された分は無い）。
- **実施**（サービスアカウントの鍵で `templates/work/` の作業用シートを batchUpdate。10/29 は MCP ツールだったが、どちらでも同じ）:
  - 受発注対応表_テンプレート（`1KBREddvkJTiAAk9ELmRKEv16pkU-knNRldNztMMJhFY`）: A1:G1 に格子罫線（SOLID・幅1・黒、上下左右と縦の内側）を付けた（`updateBorders`）。
  - スキルシート_原本（`1KT2uYILCfPeHiLiRb0OwgAKXVAWiu7GDzQ4GCM_sjzw`）: Z4 の値を `"資　格\n特殊技能"` にした（`updateCells`、fields=`userEnteredValue`。書式は変えていない）。
- `templates:export` で書き出した。差分は `order-matching.json` の A1〜G1 の罫線と、`skillsheet.json` の Z4 の値だけ。テスト7件は成功し、`templates:deploy --env staging --dry-run` も通った。
- **次のアクション**: (1) ユーザーが PR #121 をマージ、(2) ユーザーが `npm run templates:deploy -- --env staging` を実行（ID は変わらないので `cdk deploy` は不要）、(3) staging で受発注対応表と業務経歴書を出力して見え方を確かめる（特に Z4 の改行）、(4) alphasys（4_6_1）と alphaexapi に、PR 番号と反映先（staging。本番は初回 deploy のときに反映）を知らせる。

## 2026-11-02 テンプレート2件を staging に deploy し、確認を終えた（申し送り2件が完了）

- **ユーザーの作業**: PR #121 をマージし、`npm run templates:deploy -- --env staging` を実行した。3つのテンプレート（skillsheet・order-matching・bill-profit）とも、往復の確認で定義と一致した。ID は変わっていない。
- **確認（ユーザー）**: staging で受発注対応表と業務経歴書を出力し、タイトル行の罫線と「資格・特殊技能」の見出しが直っていることを確かめた。
- **連絡**: alphasys-4e（4_6_1）と alphaexapi-63（#197 の件）に、PR #121・反映先（staging）・本番は初回 deploy のときに反映されることを知らせた。
- これで、2026-11-02 の申し送り2件の alphasyscdk 担当分は完了した。

## 2026-11-02 テンプレートのドメイン閲覧権限の方針を確定し、templates/staging/ に残っている問題を確認

- **決定（ユーザー）**: テンプレートにドメイン（alphacmc.co.jp）の閲覧権限は、基本的に要らない。業務経歴書（スキルシート）はあっても構わないが、それ以外（受発注対応表・受発注採算表）にはあってはいけない。
- **ユーザーの認識との食い違い**: ユーザーは、10/28 の2点（deploy スクリプトの権限付与をやめること、`templates/staging/` のドメイン権限を外すこと）は解決したと考えていた。実際には、10/28 に alphaexapi が整えたのは `templates/` と `work/` だけで、`staging/` は対象外だった。
- **確認（読み取りのみ）**: `templates/staging/` フォルダにドメインの閲覧権限が残っていて（10/27 に手作業で付けたもの）、staging のスキルシート・受発注対応表・受発注採算表の3つとも、それを継承している。受発注の2つは、方針に反する状態。
- **原因**: `scripts/templates/deploy.ts` の `ensureEnvFolder` は、deploy のたびに `templates/{env}/` フォルダを確かめ、ドメインの閲覧権限が無ければ付ける。手で外しても次の deploy で戻り、本番の初回 deploy でも `templates/prod/` に付いてしまう。
- **提示した案（ユーザーの了解待ち）**: (1) deploy スクリプトからドメインの閲覧権限を付ける処理と `readerDomain` を外し、README と方式案の「権限」の節を直す。スキルシートだけに付ける仕組みは作らない（無くても困らないため）。(2) そのマージ後に、ユーザーが `templates/staging/` フォルダの共有設定からドメインの行を削除する。先に外すと、その間の deploy で権限が戻るので、この順序で行う。
- **ユーザーの作業（同日）**: `templates/staging/` フォルダの共有設定から、ドメインの閲覧権限を外した。確認（読み取りのみ）で、フォルダと3つのテンプレートからドメインの権限が消え、継承した4グループの閲覧と管理者だけになった。
- **注意**: deploy スクリプトを直すまでは、`templates:deploy` を実行するとドメインの閲覧権限が付け直される。修正をマージするまで deploy は実行しない。

## 2026-11-02 deploy スクリプトから、ドメインの閲覧権限を付ける処理を外した（ユーザー承認「お願いします」）

- **承認**: 上の案 (1) のまま着手することを、ユーザーが了承した（Drive の権限は、ユーザーが先に外した）。
- **変更**:
  - `scripts/templates/deploy.ts`: `ensureEnvFolder` から、権限の確認（`permissions.list`）と付与（`permissions.create`）を外した。`templates/{env}/` フォルダが無ければ作る処理だけ残した。
  - `scripts/templates/files.ts`・`templates/drive-folders.json`: `readerDomain` を消した。
  - `templates/README.md`・方式案 §3「権限」: 共有ドライブから継承した権限だけで読む、ドメインには付けない、Drive で直接直したものは次の deploy で上書きされる、に書き換えた。
- **確認**: tsc・テスト7件・`templates:deploy --env staging --dry-run` が通った。
- **次のアクション**: ユーザーが PR #123 をマージする。マージ後は `templates:deploy` を実行しても、ドメインの閲覧権限は付かない。本番の初回 deploy で作る `templates/prod/` にも付かない。

## 2026-11-06 staging の SES サンドボックスも解除する（ユーザー決定、alphasystem-45 から連絡）

- **決定（ユーザー、alphasystem で 2026-11-06）**: staging（570024666076、ap-northeast-1）の SES サンドボックスも解除する。申請はユーザーが行う。経緯は alphasystem の `docs/conversations/2026-11-06.md` の末尾。当初（2026-10-22）の「staging は解除せず、受信者を検証して試験する。解除の申請は本番の前」を改める。
- **依頼（alphasystem-45）と対応**: `docs/superpowers/specs/2026-10-22-ses-mail-infra-design.md` を直した。コード・インフラの変更は無い。
  - 7章の確認事項3を「解除する（2026-11-06 ユーザー決定）」に改めた。食い違わないように、4章冒頭の決定と 4.2 の見出し（「本番の前に行う」）も合わせて直した。
  - 4.2 の申請文の下書き（英語）に、3つ目の用途「5_5_3: 研修用 Windows インスタンスのユーザー（@alphacmc.co.jp）に初期パスワードを送るメール」を加えた。
- 解除が承認されるまでは、これまでどおり 4.1 の手順（受信者の検証）で試験する。

## 2026-11-09 alphaexapi から確認依頼: staging への push でバックエンドのビルドが起動しなかった件と、ECR のタグの運用

- **依頼（alphaexapi-3e、alphaexapi のユーザー承認済み）**: alphaexapi #203 を staging にマージした（951005e、15:50:36 JST）が、CodeBuild `staging-alphasys-backend-ecr-build` が起動しなかった。15:54 の StagingEcsDeployPipeline は成功したが、ECR `alphasys-backend:0.1.0` は 11/06 のイメージ（be8679b）のままで、古いイメージがデプロイされた。16:10 に手でビルドし、16:19 にデプロイし直して解消した。#205（17:30）のマージでは、webhook からビルドが起動していた。
- **調査結果**:
  - webhook のフィルターは `EVENT=PUSH` かつ `HEAD_REF=refs/heads/staging` の1組で、正しい。11/06 の3つのマージと 11/09 の #205 は GitHub-Hookshot から起動している。
  - GitHub の webhook（id 672516288。alphaexapi に1つだけ）の配信一覧では、マージの前後の push は 15:50:41 と 15:51:10（main への push、#204）の2件だけ。マージとブランチ削除で2件届くはずの push が1件しか無いので、staging への push（951005e）の配信は GitHub 側で作られなかったと考えられる。配信の中身は、gh に `admin:repo_hook` の権限が無いので見ていない。
  - **結論**: GitHub 側で配信がたまに抜けたもの。CDK の設定では防げない。
  - パイプラインは、15:54 も 16:14 も人が手で起動していた（StartPipelineExecution）。ビルドは3分ほどかかるので、15:54 の起動ではビルドが終わる前だった可能性もある。
- **ECR のタグ**: MUTABLE で version（0.1.0）を上書きするのは、正式リリースまでの意図した暫定の運用（`lib/shared-stack.ts` のコメント、`cdk.json` の `imageTagMutability`）。ただ、このままでは古いイメージのデプロイに気づけない。対策案を alphaexapi-3e に返した（どれも未着手。ユーザーの了解待ち）:
  - A（勧め）: alphaexapi・alphasys の buildspec で、コミットハッシュのタグも push する。alphasyscdk の imagedefinitions のステップで、デプロイするイメージのダイジェスト・push 時刻・タグをログに出す。
  - B（つなぎの運用）: パイプラインを手で起動する前に、ECR のイメージの push 時刻がマージより後であることを確かめる。
  - C（今はやらない案）: ECR への push をきっかけに、パイプラインを自動で起動する（EventBridge）。

## 2026-11-09 対策案A に着手（ユーザー承認「案A に進めてください」）

- **承認**: ECR のタグの対策は案A で進める（コミットハッシュのタグを付け、パイプラインのログでデプロイしたイメージを確かめられるようにする）。B（つなぎの運用）は A が入るまで続け、C（EventBridge で自動起動）はやらない。
- **alphasyscdk の変更**: `lib/constructs/imagedefinitions-project.ts` のイメージを確かめるステップで、`=== DEPLOY IMAGE (digest / pushedAt / tags) ===` に続けて、frontend・backend のダイジェスト・push 時刻・タグを1行ずつ出すようにした。デプロイはこれまでどおり version のタグで行う（imagedefinitions.json は変えない）。
  - 確認: 同じクエリを staging の ECR で実行し、`sha256:a6a7… 2026-11-09T17:41:45 0.1.0` と出ることを確かめた。tsc・テスト7件が通った。`diff:staging` の差分は StagingStack の `ImagedefinitionsProject/MergeProject`（CodeBuild のビルド設定）1つだけ。反映には `deploy:staging` が要る。
- **依頼**:
  - alphaexapi-3e（SendMessage）と alphasys（セッションが無いので `alphasys/INBOX_FROM_ALPHASYSCDK.md`）に、buildspec.yml の修正を頼んだ。push するときに、version のタグに加えて、コミットハッシュ（先頭7文字）のタグも付けて push する。docs だけの push と prod では付けない。
- **影響**: ECR のライフサイクルは変えない。今後は、上書きされた古いイメージにもコミットハッシュのタグが残るので、7日で消えずに最新10個まで残る。
- **次のアクション**: (1) ユーザーが PR #126 をマージし、`deploy:staging` を実行する、(2) alphaexapi・alphasys の buildspec の PR がマージされたら、次にパイプラインを実行したときのログで、コミットハッシュのタグが出ることを確かめる。
- **alphasys の対応**: alphasys-a8 が Draft PR alphasys #322（base=staging、alphasys のユーザー了解済み）を作った。buildspec.yml の pre_build で `COMMIT_HASH` を求め、push する分岐の中だけで `$REPOSITORY_URI:$COMMIT_HASH` を tag・push する。差分を見て、依頼どおりであることを確かめた。alphaexapi は、alphaexapi のユーザーの承認待ち。
- **alphaexapi の対応**: alphaexapi-3e が Draft PR alphaexapi #208（base=staging、alphaexapi のユーザー承認済み）を作った。push する分岐の中だけで `$REPOSITORY_URI:$COMMIT_HASH` を tag・push する。`COMMIT_HASH` が空のときは付けない（alphaexapi のユーザー判断）。差分を見て、依頼どおりであることを確かめた。alphasys #322 には空のときの判定が無いが、CodeBuild ではソースのコミットが必ず決まるので、実害は無い見込み。

## 2026-11-09 今 deploy:staging を実行すると Bastion が置き換わることが判明（デプロイは保留）

- **ユーザーの質問**: 「deploy:staging では Bastion は置換されないか」。
- **確認結果**: 置き換わる見込み。Bastion の AMI は `lib/constructs/ssm-ec2.ts` の `MachineImage.latestAmazonLinux2023()` で、デプロイのたびに CloudFormation が SSM パラメータ（`/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-6.1-x86_64`）を読み直す。今の Bastion（`i-08f13fc70ac372bde`、10/27 起動）は `ami-0a5110ef683dd3ad9`、最新は `ami-0c6b329f2abc3518d`（10/31 更新）なので、デプロイすると置き換わり、夜間移行の設定とタイマーが消える。テンプレートは変わらないので、cdk diff には出ない（上の「差分は1つだけ」は、この点で不十分だった）。
  - 補足: Git Bash から `aws ssm get-parameter --name /aws/...` を実行すると、パスが Windows 形式に変換されて ParameterNotFound になる。`MSYS_NO_PATHCONV=1` を付ける。
- **提示した案（ユーザーの判断待ち）**: (1)（勧め）`latestAmazonLinux2023({ cachedInContext: true })` にして、`cdk.context.json` に今の AMI を記録し、AMI を固定してからデプロイする（PR #126 に含める）。(2) 置き換わる前提でデプロイし、夜間移行を 10/27 と同じ手順で復旧する。
- **上の次のアクションの訂正**: どちらにするか決まるまで、`deploy:staging` は実行しない。
- あわせて、10/27 に置き換わった Bastion で、夜間移行の復旧が終わっているかをユーザーに確認中。

## 2026-11-09 Bastion の AMI を固定した（ユーザー承認「AMIを固定してください」）

- **承認**: 上の案 (1) で進める。あわせて、10/27 に置き換わった Bastion の夜間移行の復旧は、正常に終わっていることをユーザーが確認した。
- **変更**:
  - `lib/constructs/ssm-ec2.ts`: `MachineImage.latestAmazonLinux2023({ cachedInContext: true })` にした。AMI の値は `cdk.context.json` から読み、デプロイのたびに最新を読み直さない。
  - `cdk.context.json`: synth で作られたキー（`ssm:account=570024666076:parameterName=/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-6.1-x86_64:region=ap-northeast-1`）の値は、最新の `ami-0c6b329f2abc3518d` だった。これを今の Bastion の `ami-0a5110ef683dd3ad9`（al2023-ami-2023.12.20261026.1、廃止予定日 2027-01-22）に書き換えた。
- **確認**:
  - 変更セットを使う `diff:staging`（既定）では、差分は `ImagedefinitionsProject/MergeProject`（PR #126）と、使わなくなった SSM パラメータの削除だけ。Bastion の差分は無い。
  - `--no-change-set` では、ImageId の書き方が変わる（パラメータの参照 → 直書き）ため、Bastion が「replace」と出る。ただ、値は今と同じなので、CloudFormation の変更セットでは変更なしと判定された。
  - tsc・テスト7件が通った。
- **今後の扱い**: AMI を更新するとき（OS の更新や、2027-01-22 の廃止予定日の前など）は、`cdk.context.json` の値を書き換えて、意図して Bastion を置き換える。置き換えたら、alphadb の `nightly_automation.md` の手順で夜間移行を復旧する。本番は、初めて synth するときに、その時点の最新の AMI が `cdk.context.json` に記録される。
- **次のアクション**: (1) ユーザーが PR #128 をマージし、`deploy:staging` を実行する、(2) デプロイ後、Bastion のインスタンス ID が `i-08f13fc70ac372bde` のままであることを確かめる。

## 2026-11-09 StagingStack をデプロイし、Bastion が置き換わらなかったことを確認

- **ユーザーの作業**: PR #128 をマージし、`deploy:staging` を実行した（StagingStack は 2026-11-09 19:19 JST に UPDATE_COMPLETE）。
- **確認**:
  - Bastion は `i-08f13fc70ac372bde`（`ami-0a5110ef683dd3ad9`、10/27 起動）のままで、置き換わっていない。夜間移行の設定とタイマーも残っている。
  - CodeBuild `staging-alphasys-imagedefinitions-pipeline-project` のビルド設定に、`=== DEPLOY IMAGE (digest / pushedAt / tags) ===` が入った（PR #126 の反映）。
- **残り**: alphasys #322 と alphaexapi #208（コミットハッシュのタグ）のマージ。マージ後、次にパイプラインを実行したときのログで、`0.1.0` と7桁のハッシュのタグが並んで出ることを確かめる。

## 2026-11-14 本番の DB をリリースまで 1 台にする依頼（alphasystem-62 から、ユーザー承認済み）

- **決定（ユーザー、alphasystem で 2026-11-14）**: 本番スタックの DB（Aurora）は、リリースまで staging と同じ 1 台で作る。リリースのときに `instanceCount: 2` に戻して `cdk deploy` で2台目を足す。停止もデータ移行も無く、書き込みのエンドポイントも変わらない見込み。
- **依頼（alphasystem-62）**: `lib/prod-stack.ts` の `instanceCount: 2` を `1` にする。1→2 の増設が、インスタンスの追加だけ（今あるインスタンスの置き換え無し）になることを `cdk diff` で確かめる。リリース時に 2 へ戻す手順を docs に残す。PR のリンクを知らせる。
  - 注意（依頼元）: 1 台の間は、障害時に自動で切り替わらない（バックアップから戻すしかない）。2台目の AZ は、デプロイ後に確かめる必要がある。
- **確認**:
  - 本番スタック（ProductionStack）はまだ作られていないので、本番で 1→2 の diff は取れない。
  - そこで、同じ `RdsConstruct` を使っている staging で、一時的に `instanceCount: 2` にして `diff:staging`（変更セット）を流し、すぐ元に戻した。
  - 結果: 追加は `RDS/DBCluster/Instance2`（AWS::RDS::DBInstance）だけ。`Instance1` とクラスタは置き換わらない。ほかの差分は、`MigrateTrigger` とその IAM ポリシーの `DependsOn` に Instance2 が加わることだけ（中身は変わらない）。
- **提示した案（alphasyscdk のユーザーの了解待ち）**:
  - `lib/prod-stack.ts` を `instanceCount: 1` にし、リリース時に 2 へ戻すことをコメントに書く。
  - `docs/構築・メンテナンス手順.md` に「リリース時に DB を 2 台にする」手順を足す。手順は、2 に戻す PR → `diff:prod` で Instance2 の追加だけか確かめる → `deploy:prod` → 2台目の AZ を確かめる → フェイルオーバーの試験をするか決める。1 台の間の注意も書く。

## 2026-11-14 本番の DB を 1 台にする修正（ユーザー承認「着手してください」）

- **承認**: 上の案で着手することを、alphasyscdk のユーザーが了承した。
- **変更**:
  - `lib/prod-stack.ts`: `instanceCount: 2` → `1`。リリース時に 2 へ戻すこと、1 台の間は自動切り替えが無いことを、コメントに書いた。
  - `docs/構築・メンテナンス手順.md`: 5-2-1「本番の DB を 2 台にする（リリース時）」を足した。手順は、2 に戻す PR → `diff:prod` で Instance2 の追加だけか確かめる → `deploy:prod` → 2台目の AZ を確かめる（`describe-db-instances`）→ フェイルオーバーの試験をするか決める。1 台の間の注意も書いた。
- **確認**: tsc・テスト7件が通った。
  - `cdk synth ProductionStack` は、DB とは関係なく、`templates/template-ids.prod.json` が空のため止まる（テンプレート ID が無ければ synth を止める作り。本番のテンプレートはまだ deploy していない）。本番テンプレートの中身は、synth では確かめていない。
  - 本番を初めてデプロイする前に、`templates:deploy --env prod` で本番のテンプレートを作り、ID を記録する必要がある（既知の残作業）。
- **連絡**: alphasystem-62 に PR #132 のリンクと diff の結果を知らせた。

## 2026-11-14 8-3（手順書のシークレット件数）の修正（ユーザー承認「着手お願いします」）

- **承認**: 上の 8-3 の案で着手することを、alphasyscdk のユーザーが了承した。別の PR にする（`feature/doc-secret-count`、base=staging）。
- **変更**（`docs/構築・メンテナンス手順.md`）:
  - 1-2 の表の「機密7件」、1-3-A-3 の「機密7件」と「対象は11件」を直した。登録スクリプトは 26 件、ECS が読むのは `GOOGLE_CREDENTIALS_JSON` を足した 27 件、と書いた。
  - 1-3-A-3 の表に、MF クラウド連動の 15 件を足した（表は 26 行）。
  - `GOOGLE_CREDENTIALS_JSON` の 📝 を直した。手で登録すること、`ecs.ts` に入っている（PR #109）ので未登録だとタスクが起動しないこと、本番は別の鍵にすることを書いた。
  - 付録 A ゲート③ の前提1 の「11件」を、26件+1件=27件に直した。
  - 付録 A の「ゲート②-1 初回リリース前（1.0.0 上書き運用）」を削除した。ただし、その中の「スキーマを変更した場合はマイグレーションも必要」（③）は、1.0.0 の上書き運用とは関係なく今も当てはまるので、ゲート② の注意として残した（仕様の「削除」から外れる点）。
- **PR**: https://github.com/alphacmc/alphasyscdk/pull/135 （Draft、base=staging）。
- **連絡**: alphasystem-62 に PR のリンクを知らせ、ECS が読むのは 27 件なので、仕様 4.2 の「26 件」に `GOOGLE_CREDENTIALS_JSON` の注記を足すか検討してほしいと伝えた。

## 2026-11-14 本番アカウントの NetworkStack が完成（alphacdk-bd から連絡）

- **連絡（alphacdk-bd）**: 本番アカウント（938812705475）に NetworkStack をデプロイした（CREATE_COMPLETE）。
  - VPC は vpc-0941a4778168de668（10.100.0.0/16）。
  - NAT は NAT インスタンス（t3.nano、1a・1c に各 1 台）。
  - ProductionStack をデプロイした後は、Export しているリソースを作り直す変更はできない。
  - 研修環境の LaunchTemplatesStack は確認中（ProductionStack の前提ではない）。
- **確認（読み取りのみ）**:
  - `NetworkStack-VpcId`・`-PublicSubnetIds`・`-PrivateSubnetIds` の Export は連絡どおりだった。
  - ロール `alphacmc-prod-training-instance-role` もあった。
  - `.env.prod` の `MMS_INSTANCE_ROLE_ARN` は、すでに同じ ARN だった。
- **見つけた問題**:
  - `lib/constructs/code-pipeline.ts` は、GitHub 接続を `Fn.importValue("pipeline-connection-arn")` で引いている。
  - この Export は、共有アカウント（staging）の SharedStack にしか無い。本番アカウントには無い（`list-exports` で確認）。
  - このままだと、`deploy:prod` が「その名前の Export が無い」で失敗する見込み。
  - 仕様 4 章の「GitHub 接続の承認は不要」も当てはまらない可能性がある。
  - 直し方の案をユーザーに出す（了解待ち）。
- **追加の確認**: 本番アカウントには GitHub 接続そのものが無い（`codestar-connections list-connections --profile prod` が空）。
- **提示した案（了解待ち）**:
  1. ProductionStack で、本番アカウントに GitHub 接続（`CfnConnection`、作成直後は PENDING）を作る。
  2. CodePipelineConstruct には、importValue ではなくその接続を渡す。staging は今のまま。
  3. 人の作業として、デプロイの後に本番のコンソールで接続を 1 回承認する。承認までパイプラインは動かない（デプロイ自体は通る）。
  - 了解が出たら、alphasystem に「仕様 4 章の『GitHub 接続の承認は不要』を直す必要がある」と伝える。
- **失敗**: 記録の push 前に PR #135 がマージ済みだったのに、`gh pr view && git push` で push してしまった。同じブランチから PR #137 を作り直した。今後は OPEN を文字列で判定してから push する。

## 2026-11-14 本番スタックに SES を入れる依頼（alphasystem-62 から、ユーザー承認済み）

- **決定（ユーザー、alphasystem で 2026-11-14）**: 本番の送信元ドメインは `alphasys.alphacmc.com`（本番の実ドメイン）に統一する。SES 設計書 5 章の `alphasystem.alphacmc.com` 系は誤記として直す。
- **依頼（alphasystem-62）**: ProductionStack に staging と同じ SES 構成（SesConstruct・MAIL_FROM・タスクロールへの送信許可）を入れる。DKIM・MAIL FROM・DMARC のレコードが本番のホストゾーン `alphasys.alphacmc.com` に作られることを `diff:prod` 等で確かめる。サンドボックスの間は identity/* の許可（設計書 3 章）を staging と同様に扱う。設計書 5 章の更新も PR に含める。8-1（DnsConstruct の apex 対応）・8-3 は別途依頼。
- **調査**:
  - 本番アカウントに `alphasys.alphacmc.com` のホストゾーン（Z01029762HO9GEN1GXBMI）があり、公開 DNS の NS 委譲も通っている。
  - 今の `cdk.json` の本番コンテキストは `alphacmc.com` + `alphasys` のため、DnsConstruct は本番アカウントに無い `alphacmc.com` ゾーンを引きに行く。8-1 の前は、SES のレコードを `alphasys.alphacmc.com` ゾーンに置く diff は取れない（SES は DnsConstruct のゾーンを使う）。
  - `cdk synth ProductionStack` は `template-ids.prod.json` が空のため止まる（既知）。
  - `.env.prod` の `AUTH_URL` が `https://alphasystem.alphacmc.com` のまま（ドメイン統一と食い違う）。
- **方式案を alphasyscdk のユーザーに提示し、了解待ち**（下の「了解」の節に結果を書く）。

### 了解（alphasyscdk のユーザー、2026-11-14）

- **8-1（DnsConstruct・A レコードの apex 対応、`cdk.json` の本番コンテキスト更新）も同じ PR に入れる。** SES のレコードは DnsConstruct のゾーンに作るため。
- diff:prod の止まり（`template-ids.prod.json` が空）は、判断を任された。確認の間だけローカルでダミーの ID を入れて diff を取り、すぐ元に戻す（コミットしない）。

### 実装と確認（`feature/prod-ses`）

- **変更**:
  - `lib/constructs/dns.ts`: `siteDomain` を足した。`subDomain` が空ならゾーン apex（8-1）。証明書は `siteDomain` で取る。
  - `cdk.json`: 本番は `{"domainName": "alphasys.alphacmc.com", "subDomain": ""}`。
  - `lib/prod-stack.ts`: A レコードの `recordName` を `siteDomain` にした。SesConstruct（送信元 `no-reply@alphasys.alphacmc.com`）を入れ、ECS の `mail`（`MAIL_DRIVER`・`MAIL_FROM`・`ALPHASYS_BASE_URL`）と `grantSend`（`identity/*`、`ses:FromAddress` で絞る）を足した。
  - `cdk.context.json`: 本番のゾーンの検索結果（Z01029762HO9GEN1GXBMI）と、本番の Bastion の AMI（ami-089bd5e642b45bf4b）が記録された。本番の AMI も固定される。
  - SES 設計書 5 章・1 章、構築・メンテナンス手順 2-1 のドメイン表を更新した。
- **確認**:
  - tsc は通り、テスト 7 件も通った。
  - `diff:prod` は、確認の間だけ `template-ids.prod.json` にダミーの ID を入れて流し、すぐ元に戻した。合成したテンプレートで、証明書の検証・A レコード（`alphasys.alphacmc.com.`）・DKIM の CNAME 3件・`bounce.alphasys.alphacmc.com` の MX と SPF・`_dmarc.alphasys.alphacmc.com` の TXT が、すべてゾーン Z01029762HO9GEN1GXBMI に作られる。
  - `diff:staging` は差分なし。
  - 本番の `AUTH_URL` が `https://alphasystem.alphacmc.com` のまま（`.env.prod` 由来）。直すのは別の作業（8-3 と合わせて案を出す）。
- **追加の連絡（alphasystem-62、ユーザー承認「進めてください」）**:
  - 8-1（今回の PR に含めた）・8-3（シークレット件数を 26 件にし、付録 A の「ゲート②-1」を削除）・`.env.prod` の `AUTH_URL` の修正の依頼が来た。
  - 本番の SES サンドボックス解除は承認済み（ケース ID 179466012600694）。
- **PR**: https://github.com/alphacmc/alphasyscdk/pull/134 （Draft、base=staging）。alphasystem-62 にリンクと確認結果を知らせた。
- **`.env.prod` の `AUTH_URL`**: PR を作った後に見直すと、`https://alphasys.alphacmc.com` に直っていた（ファイルの更新は 2026-11-14 21:54。diff:prod の後）。`API_URL` は `.env` の共通値 `http://localhost:3001` を使う。フロントとバックが同じタスクにいるので、staging と同じ。ほかの URL 系に食い違いは無い。
- **8-3**: 了解を取ってから、別の PR にする（ユーザーに案を出す）。

## 2026-11-14 8-3（手順書のシークレット件数）の案を提示（了解待ち）

- **調べて分かったこと**:
  - 登録スクリプト（`alphasystem/scripts/register-secret-parameters.py` の `MAPPING`）は 26 件。共有 2・alphasys 1・alphaexapi 3・営業メール Track1 5・MF クラウド連動 15。仕様の数と合う。
  - ECS が起動時に読む SecureString は **27 件**（`lib/constructs/ecs.ts` の `secureParam`）。スクリプトの 26 件に `alphaexapi/GOOGLE_CREDENTIALS_JSON`（googledrivemanager の鍵）が加わる。この鍵はスクリプトの対象外で、本番では別の鍵を後で登録する決定済みのもの。
- **提示した案（別 PR）**:
  1. 1-3 の「機密7件」「対象は11件」を 26 件に直し、表に MF クラウド連動の 15 件を足す。
  2. `GOOGLE_CREDENTIALS_JSON` は「スクリプトの対象外・手で登録・未登録だと本番タスクが起動しない」と別に書く。
  3. 付録 A の前提の「11件」も直す。
  4. 付録 A の「ゲート②-1 初回リリース前（1.0.0 上書き運用）」を削除する。
  - 27 件目のことは、alphasystem の仕様 4.2（26 件）にも関わるので、alphasystem にも伝える。

## 2026-11-15 本番アカウントに GitHub 接続を作る（ユーザー承認「A」）

- **経緯**:
  - 本番の CodePipeline は、GitHub 接続を共有アカウント（staging）の Export `pipeline-connection-arn` から引いていた。本番アカウントからは引けない。
  - ユーザーから「本番は ECR を読むだけでは？ GitHub は要るのか」と質問があった。
  - 説明: 本番の GitHub 接続は、ビルドのためではない。`alphasysdeploy` の `main` の `version.json` を読み、本番に出す版を決めて、パイプラインを動かすため（仕様 6.2 の手順 5）。
  - 3 案を出した。A: 本番に GitHub 接続を作る。B: 本番のパイプラインをやめ、`.env.prod` の版で `deploy:prod`。C: staging のパイプラインから本番へデプロイする。
- **決定（ユーザー）**: **A**。B は、どの版を出したかが git に残らなくなる。C は、別アカウントへのデプロイでロールの設定が複雑になる。
- **変更**（`feature/prod-github-connection`）:
  - `lib/constructs/code-pipeline.ts`: `connectionArn` を渡せるようにした。省略時は、今までどおり Export を引く（staging は変わらない）。
  - `lib/prod-stack.ts`: 本番アカウントに `CfnConnection`（`prod-github-connection`、GitHub）を作り、パイプラインに渡す。RETAIN にはしていない（スタックを作り直したら承認し直す）。
  - `docs/構築・メンテナンス手順.md` 1-3-B-1: 本番は別の接続を承認すること、承認後にパイプラインを手動で 1 回動かすことを書いた。
- **確認**:
  - tsc は通り、テスト 7 件も通った。
  - `diff:prod`（確認の間だけダミーのテンプレート ID を入れ、元に戻した）: `AWS::CodeStarConnections::Connection` が加わる。パイプラインの Source は、この接続で `alphacmc/alphasysdeploy` の `main` を読む。テンプレートに `pipeline-connection-arn` は残っていない。
  - `diff:staging` は差分なし。
- **人の作業（ProductionStack の初回デプロイの後）**:
  1. 本番アカウントのコンソールで `prod-github-connection` を承認する。
  2. `MainEcsDeployPipeline` を手動で 1 回動かす。
- **連絡**: alphasystem に、仕様 4 章の「GitHub 接続の承認は不要」を直す必要があることを伝える。
- **PR**: https://github.com/alphacmc/alphasyscdk/pull/139 （Draft、base=staging）。
- **連絡済み**: alphasystem-62 に、仕様 4 章の「GitHub 接続の承認は不要」と 5 章のデプロイ手順を直すよう依頼した。
- **片付け**: マージ済みのローカルブランチ `feature/prod-ses`（#134）と `feature/doc-secret-count`（#135・#137）を削除した。

## 2026-11-15 営業メールの取り込みの on/off を ECS に渡す（仕様 8-2、ユーザー承認「この案で着手する」）

- **依頼（alphaexapi-16、ユーザーの了解は alphasystem-62 経由で 2026-11-15）**: backend の ECS に `SALES_MAIL_POLLING_ENABLED` を足す。値が `true` のときだけ、営業メールの取り込み（10 分ごとの @Cron）が動く。今は staging `true`・本番 `false`。リリース時に逆にする（staging `false`・本番 `true`）。
  - **順番**: 先に staging に `true` を反映し、その後で alphaexapi の修正（8-2 と 0.5.0）を staging に入れる。逆にすると、その間 staging の取り込みが止まる。今の alphaexapi のイメージはこの変数を読まないので、先に足しても影響は無い。staging に入ったら、alphaexapi-16 に知らせる。
- **方式（ユーザー承認）**: `cdk.json` の staging・prod に `salesMailPollingEnabled`（true / false）を持たせ、`ecs.ts` で `"true"` / `"false"` の文字列にして渡す。本番も `false` を明示する。切り替えは、`cdk.json` の値を変えて deploy する。
- **変更**（`feature/sales-mail-polling-toggle`）: `cdk.json`、`lib/constructs/ecs.ts`（必須の prop `salesMailPollingEnabled`）、`lib/staging-stack.ts`、`lib/prod-stack.ts`。context が無いときは `=== true` で OFF になる。
- **確認**:
  - tsc は通り、テスト 7 件も通った。
  - `diff:staging`: タスク定義に `SALES_MAIL_POLLING_ENABLED=true` が加わるだけ（新しいリビジョン）。
  - 本番の synth: `false`。
- **段取り**: PR をマージ → 人が `deploy:staging` → alphaexapi-16 に「staging に反映した」と知らせる → alphaexapi が 8-2 と 0.5.0 を staging に入れる。
- **気づいたこと**: 作業ツリーの `templates/drive-folders.json`（prod のフォルダ ID）と `templates/template-ids.prod.json`（本番のテンプレート ID 3 つ）が書き換わっていた（2026-11-15 13:14〜13:15）。本番の `templates:deploy` を流した結果と見られる。このブランチのコミットには含めず、扱いはユーザーに確認する。
- **PR**: https://github.com/alphacmc/alphasyscdk/pull/142 （Draft、base=staging）。
- **連絡**: alphaexapi-16 に PR のリンクを知らせた。staging に反映して合図するまで、8-2・0.5.0 を staging に入れないよう伝えた。
- **返事（alphaexapi-16）**: 合図が来るまで、8-2・0.5.0 は staging に入れないと了承した。リリース時の切り替え（`cdk.json` の値を逆にして deploy する）は、alphaexapi の PR の説明と docs にも書く。

## 2026-11-15 deploy:prod の失敗（S3 バケット名の衝突）

- **報告（ユーザー）**: `npm run deploy:prod` でエラーが出た。
- **調査（読み取りのみ）**:
  - ProductionStack は ROLLBACK_COMPLETE（作成 13:26:53 JST）。
  - 根本原因は `CodePipelinePipelineArtifactBucket` の作成の失敗。CloudTrail では `CreateBucket` が `BucketAlreadyExists`（13:27:30）だった。バケット名 `prod-alphasyscdk-pipeline-artifacts-bucket` を、私たちのアカウント以外の誰かが持っていた（自分のアカウントのものなら `BucketAlreadyOwnedByYou` になる）。ほかのリソースは、作成が取り消されただけ。
  - 本番の以前のスタック 3 件（11-14 21:51、11-15 09:56・13:21）は、diff の変更セット（REVIEW_IN_PROGRESS → 削除）で、バケットは作っていない。
  - 今は staging・本番の両方から `head-bucket` が 404 で、この名前のバケットは見当たらない。持ち主は分からない。
- **提示した案（了解待ち）**:
  - 本番のバケット名にアカウント ID を入れる（`prod-alphasyscdk-pipeline-artifacts-938812705475`）。本番のバケットは一度も作られていないので、影響は無い。
  - staging は変えない（名前を変えると作り直しになる）。
  - 同じ名前で流し直すのは勧めない（持ち主が分からない名前のため）。
  - 修正をマージした後、`deploy:prod` を流し直す。CDK は、ROLLBACK_COMPLETE のスタックを消してから作り直す。

## 2026-11-15 ECR を IMMUTABLE に戻す依頼（alphasystem-62 から、ユーザー承認「0.5.0 の統一でお願いします」）

- **依頼（alphasystem-62）**: 仕様 3.3 の手順 0。共有アカウントの ECR `alphasys-frontend`・`alphasys-backend` が MUTABLE のままで、仕様 6.5（タグは immutable）に反する。①経緯の確認、②IMMUTABLE に戻す（コードの修正が要るなら方式案を出し了解を得る）、③戻した後に CI が同じ版を 2 回 push しないかの確認。webhook が届かなかった件も、分かれば知らせる。
  - 0.5.0 の統一の順序（仕様 3.3）: alphadb の publish → alphaexapi・alphasys を 0.5.0 に → alphasyscdk の `.env` の `FRONTEND/BACKEND_PACKAGE_VERSION` を 0.5.0 にして StagingStack をデプロイ → alphasysdeploy の staging の `version.json`。`.env` を変える時期は、別途知らせが来る。
- **調査**:
  - ① 手作業ではなく、CDK の設定。`cdk.json` の context `"imageTagMutability": "MUTABLE"`（8ac9443、2026-09-24）。正式リリース前は同じタグを上書きする運用で、「正式運用を始めたら IMMUTABLE に変える」と `shared-stack.ts` のコメントにある。`EcrConstruct` の既定値は IMMUTABLE。
  - ③ alphaexapi・alphasys の buildspec は、docs だけの push 以外では、毎回 version のタグ（と 7 桁のコミットハッシュのタグ）を push する。
    - IMMUTABLE にすると、同じ版で 2 回目に push したとき（版を上げずにコードを直してマージしたとき）、version のタグの push が失敗する。同じコミットでビルドをやり直したときは、ハッシュのタグの push も失敗する。
    - **しかも、失敗が隠れる。** push は `post_build` の複数行ブロック（`|`）の中にあり、ブロックの終了コードは最後の `printf` のものになる。そのため docker push が失敗してもビルドは成功と表示され、古いイメージがそのままデプロイされる（手順書 2-5 の注意書きどおり）。
  - webhook の件: 2026-11-09 の調査の結論のまま（GitHub 側で、staging への push の配信が作られなかった。CDK の設定では防げない）。ECR の MUTABLE とは関係ない。
- **方式案をユーザーに提示し、了解待ち**。
- **提示した案（了解待ち）**:
  1. alphaexapi・alphasys のセッション: buildspec で、push が失敗したらビルドも失敗にする（`docker push ... || exit 1`）。
  2. alphasyscdk: `cdk.json` を `"imageTagMutability": "IMMUTABLE"` にし、`shared-stack.ts` のコメントを直す PR。
  3. 人: 2 のマージ後に `cdk deploy SharedStack`。時期は、alphaexapi・alphasys の 0.5.0 のイメージを push する直前（早すぎると、0.5.0 までの 0.1.0 での修正が push できない）。
  4. 以後は、staging にコードをマージするたびに版を上げる（0.5.1、0.5.2…）。
  - 了解が出たら、2 の PR を作り、alphasystem に 1 の依頼と 3・4 の段取りを伝える。

### 保留（alphasystem-62 から、2026-11-15）

- **連絡**: ECR を IMMUTABLE に戻す変更は、保留する。経緯の確認までにとどめる。
  - alphasys から指摘があった。IMMUTABLE にすると、版を上げずに staging にマージするたびに、版のタグの push が拒否される。
  - 仕様 6.2 は「区切りごとに版を上げる」前提で、区切りの間の staging へのマージを想定していなかった。運用の設計をユーザーに確認する（判断が出たら連絡が来る）。
- **回答（alphasystem-62 へ送信済み）**:
  - ① MUTABLE の経緯（上の調査のとおり）。
  - ② CI は、別々の `docker push` を 2 回する（版 → コミットハッシュ）。`set -e` が無いので、版のタグが拒否されてもハッシュのタグは入る。ブロックの終了コードは最後の `printf` のものなので、ビルドは成功になる。その結果、古い `<version>` のイメージがデプロイされる（alphasys の言う「ビルドが失敗する」は、今の buildspec では起きない）。
  - 運用をどう決めても、buildspec で push の失敗をビルドの失敗にすることを先にやる方が安全、と伝えた。
- **状態**: `cdk.json` は変えていない。Draft PR #141 は記録だけ。ユーザーの判断を待つ。

## 2026-11-15 2 回目の deploy:prod の失敗（ロググループ名）

- **報告（ユーザー）**: 2 回目の `deploy:prod` が、変更セットの事前チェックで止まった。`AWS::Logs::LogGroup '/alphasys/staging/nightly-migration' already exists`。
- **原因**:
  - `lib/constructs/ssm-ec2.ts` が、ロググループ名を `/alphasys/staging/nightly-migration` と固定で持っている。
  - 1 回目（13:27:29）にこれが本番アカウントに作られ、LogGroup の既定の RETAIN のため、ロールバックの後も残った（0 バイト）。
  - 本番アカウントに残ったものは、これ 1 つだけ（ECS のロググループなどは作られていない）。
- **提示した案（了解待ち。バケット名の修正と 1 つの PR）**:
  1. ロググループ名を `/alphasys/${env}/nightly-migration` にする（本番は `/alphasys/prod/nightly-migration`。staging は変わらない）。
  2. 本番のバケット名にアカウント ID を入れる（前の案）。
  3. 本番に残った空のロググループ `/alphasys/staging/nightly-migration` を、了解の後に `aws logs delete-log-group --profile prod` で消す。
  4. 本番の夜間移行を配備するとき（仕様 6.4）、Bastion の `LOG_GROUP` を `/alphasys/prod/nightly-migration` にするよう、alphadb に伝える（設定ファイルで変えられるので、alphadb のコードの修正は要らない）。
  - マージの後に `deploy:prod` を流し直す。
- **承認（ユーザー）**: 上の 4 点の案で進める。`deploy:staging`（PR #142 の分）はまだ流していない。
- **変更**（`feature/prod-deploy-fixes`）:
  - `lib/constructs/ssm-ec2.ts`: `environmentType` を受け取り、ロググループ名を `/alphasys/${environmentType}/nightly-migration` にした。
  - `lib/staging-stack.ts`・`lib/prod-stack.ts`: `environmentType` を渡す。
  - `lib/prod-stack.ts`: パイプラインのバケット名を `prod-alphasyscdk-pipeline-artifacts-${this.account}`（＝`…-938812705475`）にした。
- **確認**:
  - tsc は通り、テスト 7 件も通った。
  - `diff:staging`: 差分は、まだデプロイしていない PR #142 の `SALES_MAIL_POLLING_ENABLED` だけ（今回の修正は staging を変えない）。
  - 本番の synth: ロググループは `/alphasys/prod/nightly-migration`、バケットは `prod-alphasyscdk-pipeline-artifacts-938812705475`。
- **実施（承認済み）**: 本番アカウントに残っていた空のロググループ `/alphasys/staging/nightly-migration`（0 バイト、ストリーム 0）を削除した。
- **段取り**: この PR をマージ → `deploy:prod` を流し直す。`deploy:staging`（PR #142・今回の分）は、別途ユーザーが流す。その後、alphaexapi-16 に知らせる。
- **未コミット**: `templates/drive-folders.json`・`templates/template-ids.prod.json`（本番の templates:deploy の結果）。本番の deploy には要るファイルで、扱いをユーザーに確認中。
- **PR**: https://github.com/alphacmc/alphasyscdk/pull/144 （Draft、base=staging）。
- **連絡**: alphadb-86 に、本番の夜間移行を配備するとき `/etc/alphadb-migration.env` の `LOG_GROUP` を `/alphasys/prod/nightly-migration` にするよう伝えた（本番の Bastion の書き込み権限も、この名前に対してだけ）。
- **段取り（ユーザーに提示）**: ① PR #144 をマージ → ② `deploy:prod` を流し直す → ③ `deploy:staging`（PR #142 と #144 の分）→ 終わったら alphaexapi-16 に知らせる。
- **返事（alphadb-86）**: 本番に配備するとき（仕様 6.4）は `LOG_GROUP=/alphasys/prod/nightly-migration` にする。`nightly_automation.md` の staging 名の記述は staging 向けの手順で、直す誤記は無い。本番向けの手順を足すかは、alphadb がユーザーに確認中（alphadb PR #116）。
- **問い合わせ（alphaexapi-16）**: PR #142 の staging への反映の状況。staging のタスク定義 `staging-alphasys-unified` は、最新の revision 86（11/10 15:10）のままで、`SALES_MAIL_POLLING_ENABLED` が入っていない。alphadb 0.5.0 は publish 済みで、反映が済めば 8-2・0.5.0 の PR に取りかかる。
  - 回答: `deploy:staging` はまだ（人が流す）。反映したら知らせるので、それまで staging には入れない（PR の準備は進めてよい）、と伝えた。
  - ユーザーへの補足: `deploy:staging` は、PR #144・`deploy:prod` を待たずに先に流してよい（#144 は staging を変えない）。

## 2026-11-15 本番のテンプレート ID の取り込みと、取り込みの切り替え手順（ユーザー承認）

- **報告（ユーザー）**: PR #144 をマージした。本番のテンプレート ID 2 件も取り込んだ。
- **確認**: その 2 件（コミット 9082adf「template取込」）は main に直接入っていて、staging には無かった。main は staging の内容をすべて含んでいる（#145 で staging → main 済み）。手元の staging で `deploy:prod` を流すと、テンプレート ID が無くて synth が止まる。
- **決定（ユーザー）**:
  - staging にも取り込む。9082adf を cherry-pick する（`feature/sync-prod-template-ids`）。
  - alphaexapi-16 から依頼された、営業メールの取り込みをリリース時に切り替える順番を、構築・メンテナンス手順に書き足す（5-2-2）。順番は「staging を false にして deploy:staging → 本番を true にして deploy:prod」。両方 ON の時間があると、同じメールボックスの未読メールが staging と本番に分かれる（両方 OFF は問題ない）。
- **PR**: https://github.com/alphacmc/alphasyscdk/pull/146 （Draft、base=staging）。alphaexapi-16 に、5-2-2 に書いたことを知らせた。

## 2026-11-15 本番のデプロイの順番の見直し（alphasystem-62 の指摘、ユーザーの了解待ち）

- **指摘（alphasystem-62）**:
  - 本番は、8-2 が入った 0.5.0 のイメージが ECR に入ってからデプロイする。
  - 8-2 の無いイメージで本番が起動すると、`SALES_MAIL_POLLING_ENABLED=false` でも、登録済みの `SALES_MAIL_IMAP_*` で取り込みが動き、staging とメールボックスを取り合う。
  - 本番は未デプロイで、ECS も無い（alphasystem が読み取りで確認）。
  - また、「deploy:staging は deploy:prod の後」だと、alphaexapi #218 のマージ条件（staging への反映）と循環する。
- **回答（alphasystem-62 へ送信済み）**: deploy:staging を後にした技術的な理由は無い（段取りを並べた順番だっただけ）。提案の順序に支障は無い。ユーザーに確認する。
- **提示した順番（2026-11-15 ユーザーが了承し deploy:staging を実行。段取りとして確定）**:
  1. `deploy:staging`（差分は `SALES_MAIL_POLLING_ENABLED=true` だけ）。
  2. alphaexapi に知らせる → alphaexapi #218（8-2・0.5.0）をマージ。
  3. CI が 0.5.0 のイメージを ECR に push。
  4. `.env` の `FRONTEND/BACKEND_PACKAGE_VERSION` を 0.5.0 にする（時期は alphasystem から連絡）。
  5. `deploy:prod`（main で流す）。
  - **それまで `deploy:prod` は流さない**よう、ユーザーに伝えた。

## 2026-11-15 deploy:staging が終わらない件（19:01〜）

- 原因: `.env` の FRONTEND/BACKEND_PACKAGE_VERSION が 0.5.0 だったが、staging の ECR に 0.5.0 のイメージが無い（最新は 0.1.0）。新しいタスク定義 :87 が CannotPullContainerError で起動できず、ECS サービスの更新が安定しない。サーキットブレーカーが無いため、CloudFormation はタイムアウトまで待ち続ける。
- 影響: 旧タスク :86 が動き続けるので、staging のサービス停止は無い。
- 提案（了解待ち）: cancel-update-stack で :86 に戻す → `.env` を 0.1.0 に戻す → deploy:staging を流し直す。0.5.0 にするのは、段取り 4 番目（0.5.0 の push 後）。
- ユーザー了解（「対処案了解しました」）→ cancel-update-stack を実行し、UPDATE_ROLLBACK_COMPLETE になった。`.env` の 2 行を 0.1.0 に戻した。次はユーザーが deploy:staging を流し直す。
- ロールバック後のサービスはタスク定義 :81（CFN 管理の版）で稼働。:86（パイプラインが登録した版）と同じく frontend/backend とも 0.1.0 のイメージなので、中身は変わらない。
- 流し直した deploy:staging が完了。StagingStack は UPDATE_COMPLETE、タスク定義は :88（frontend/backend とも 0.1.0）、backend に SALES_MAIL_POLLING_ENABLED=true が入ったことを確認。これで段取り (1) は完了。
- alphaexapi-16 に #218（8-2 / 0.5.0）へ進んでよいと伝え、alphasystem-62 に順番の了承と (1) の完了を報告した。deploy:prod はまだ流していない（(3) の 0.5.0 push と (4) の .env 変更の後に流す）。
- alphaexapi-16 から返信: staging の :88 で SALES_MAIL_POLLING_ENABLED=true を確認した。#218 のマージをユーザーに依頼済み。0.5.0 が ECR に push されたら連絡する。
- ユーザーが alphaexapi #218 をマージ。backend のビルド（19:36〜19:39、SUCCEEDED）で、staging の ECR に alphasys-backend:0.5.0（8381871）が push された → 段取り (2)(3) は完了。
- frontend は 0.1.0 のまま（今日 13:48 のビルドはドキュメントだけの push と判定され、設計どおり skip。push の失敗ではない）。.env を両方 0.5.0 にすると frontend のイメージが無くて ECS が起動しないため、(4) は BACKEND だけ 0.5.0 にして FRONTEND は 0.1.0 のまま、と alphasystem-62 に提案し、指示を待っている。
- alphasystem-62 から: alphasys（frontend）の 0.5.0 の PR がまだ無い（origin/staging は version 0.1.0・alphadb ^0.2.7）。「3 つとも 0.5.0 で統一」とし、frontend の 0.5.0 を待ってから (4) で両方を 0.5.0 にする。BACKEND だけ 0.5.0 にする案は取らない（本番が alphadb ^0.2.7 の画面で起動するため）。alphasys-1e に版上げを依頼する。**alphasystem の提案で、ユーザーの了解はまだ。** それまで .env は変えず、deploy:prod も止めておく。
- 訂正として返信した: PACKAGE_VERSION があるのは .env だけ（.env.staging / .env.prod には無い。bin/app.js は .env.<環境> → .env の順に読む）。.env を 0.5.0 にすると deploy:staging と deploy:prod の両方に効く。
- PR #146 は 19:35 にマージ済みだったので、追記したコミットは PR #148 に移した。旧ブランチ feature/sync-prod-template-ids は #148 のマージ後に削除する。
- alphasystem-62 から: .env.staging の件は訂正を受け入れ、記録を直した（(4) は `.env` の 1 か所）。staging の ECS の時期の提案: frontend と backend の 0.5.0 が両方とも ECR にあることを確認してから、(4) の直後に deploy:staging を流して版をそろえる。両方そろうまでは流さない（今日の障害の再発防止）。時期は alphasys の PR のマージ後に alphasystem から指示が来る。**alphasystem の提案で、ユーザーの了解はまだ。**
- alphaexapi-16 から: backend の 0.5.0 の push を報告（digest sha256:6e92e961…、8381871 は #218 のマージコミット）。staging を 0.5.0 にした後に、backend のログに「営業メール取り込みは有効」が出るかを確認したいとのこと。→ staging を 0.5.0 にするのは frontend の 0.5.0 が ECR に入ってからと返信し、デプロイ後に知らせると伝えた。
- alphasystem-62 から: frontend の 0.5.0（7862d78、21:17）が ECR に入り、0.5.0 が 2 つともそろった。`.env` を 0.5.0 にして diff を報告するよう依頼された（deploy はユーザーの了解の後。順序は deploy:staging（alphaexapi-16 がログを確認）→ deploy:prod）。
- `.env` の FRONTEND/BACKEND_PACKAGE_VERSION を 0.5.0 にした（ローカルのみ、deploy はしていない）。diff の結果:
  - staging: StagingStack はタスク定義のイメージのタグ 2 か所（:0.1.0 → :0.5.0）だけ。SharedStack は差分なし。
  - prod: 新規作成なので 138 件がすべて追加（置き換え・削除なし）。タスク定義は frontend/backend とも :0.5.0、SALES_MAIL_POLLING_ENABLED=false、MAIL_FROM=no-reply@alphasys.alphacmc.com、ECS の DesiredCount は 2。
  - 結果を alphasystem-62 に報告した。deploy:staging → deploy:prod はユーザーの了解を待つ。本番の GOOGLE_CREDENTIALS_JSON が SSM に登録されているかを deploy:prod の前に確かめる。
- 本番の SSM: テンプレートが参照する /alpha/prod 配下のパラメータ 27 件が、すべて SSM に存在することを突き合わせて確認した（値は読んでいない）。GOOGLE_CREDENTIALS_JSON は SecureString（12:21 登録）。
- alphasystem-62 から: 残る確認は、本番のサービスアカウントが本番の共有ドライブ・テンプレートフォルダーに書き込めること（ユーザーに確認する）。deploy:staging と deploy:prod は、ユーザーの go が出るまで止めておく。
- ユーザーが deploy:staging（0.5.0）を実行した（21:27 完了）。これで 0.5.0 にそろえる方針を実質了承したと扱う。StagingStack は UPDATE_COMPLETE、タスク定義は :89（frontend/backend とも 0.5.0、SALES_MAIL_POLLING_ENABLED=true）。backend のログに 12:28:25Z「営業メール取り込みは有効」が出ていて、ERROR は無い。
- alphaexapi-16 に取り込みの動作確認を頼み、alphasystem-62 に完了を報告した。deploy:prod は、ユーザーの go と、本番のサービスアカウントの共有ドライブ書き込み権限の確認を待つ。
- alphaexapi-16 から: staging の 0.5.0 で取り込みのジョブが動いた（12:30:00Z「新規0件…失敗0件」、IMAP 接続とロックの取得・解放がエラー無く 1 周）。入れ替えの途中で、古いタスク（:88）も同時に取り込みを実行していた。メールを実際に処理できるかは、テストメールを送って確かめる予定（送るかはユーザーに確認する）。
- こちらから確認を依頼: 本番は ECS の DesiredCount が 2 で、常に 2 タスクが同時に取り込むことになる。ロックがタスクをまたいで効くか（二重取り込みを防げるか）を、本番でポーラーを true にする前（5-2-2）の確認事項にする。今は本番のポーラーが false なので、deploy:prod を止める理由にはならない。
- alphaexapi-16 から回答: ロックはタスクをまたいで効く。共有 DB の advisory lock（pg_try_advisory_lock、固定キー 728193045、ロック専用の接続 1 本、取れなければその回をスキップ、異常終了時は接続が切れたときに解放）。今日の staging で 2 タスクとも「完了」を出したのは、0 件で 0.35 秒で終わってロックを放した後に、もう一方が取ったため（順番に動いている）。既読化と「重複スキップ」で、二重取り込みも防がれる。→ 本番が DesiredCount 2 のままでも、ポーラーを true にする前の対策は不要。ON にした後は、10 分ごとに片方が「取り込み完了」、もう片方が「スキップ」か 0 件で完了、になることをログで確かめる。
- ユーザーから「deploy:prod を実行してよいか」の確認があり、実行してよいと回答した。手元のコードは docs 以外 main と同じで、未コミットの変更も無い。前提（ECR 0.5.0 がそろっている、.env 0.5.0、diff:prod はすべて追加、SSM 27 件）は確認済み。本番のサービスアカウントの共有ドライブ書き込み権限は未確認だが、デプロイには関係しないので、本番を使い始める前に設定する。デプロイの後は、prod-github-connection の承認 → MainEcsDeployPipeline を 1 回実行（1-3-B-1）。
- PR #148 は 21:36 にマージ済みだったため、その後の記録は PR #150 に移した。中身が staging に取り込み済みの feature/sync-prod-template-ids を削除した。feature/record-backend-050 は #150 のマージ後に削除する。

## 2026-11-15 deploy:prod の 3 回目の失敗（CodeBuild の GitHub 認証情報が無い）

- 21:42 頃、ProductionStack の作成が失敗し、ROLLBACK_COMPLETE になった。原因は FrontendCodeBuild の CREATE_FAILED「Access token not found in CodeBuild project for server type github」。ほかのリソースは巻き添えで取り消されただけ。
- 本番の CodeBuild プロジェクトは GitHub の webhook（main への push）を使う。CodeBuild の webhook には、アカウントに GitHub のソース認証情報が必要。staging アカウントには PAT（PERSONAL_ACCESS_TOKEN）が登録されているが、本番アカウントには何も無い。手順書にも書かれていなかった。prod-github-connection は CodePipeline 用で、これとは別。
- 空のロググループ /alphasys/prod/nightly-migration（0 バイト、RETAIN）が、また残っている。このまま流し直すと already exists で失敗する。
- 提案（了解待ち）: (1) ユーザーが本番アカウントに GitHub の PAT を import-source-credentials で登録する（repo と admin:repo_hook の権限。トークンはチャットに貼らない） → (2) 私が空のロググループを削除する → (3) deploy:prod を流し直す → (4) 手順書の 1-3-B に PAT の登録を前提作業として書き足す。
- ユーザーの依頼で、(1) の PAT の登録を Windows（PowerShell）で行うコマンドを示した。Read-Host -AsSecureString で入力を受け、import-source-credentials を --profile prod で実行する（トークンは画面にも履歴にも残らない）。手順書に書き足すとき（(4)）も、この PowerShell 版を載せる。(2)(4) の了解はまだ。
- ユーザーが本番アカウントに PAT を登録した。list-source-credentials で、arn:aws:codebuild:ap-northeast-1:938812705475:token/github（GITHUB / PERSONAL_ACCESS_TOKEN）があることを確認した。(1) は完了。(2) のロググループの削除と (4) の手順書は、まだ了解待ち。
- ユーザー了解（「2,4 お願いします」）→ (2) 空のロググループ /alphasys/prod/nightly-migration（0 バイト）を削除した。(4) 手順書に「1-3-B-2. CodeBuild 用の GitHub トークンの登録（アカウントごとに1回）」を新設し（トークンの条件、PowerShell での登録、確認の CLI、未登録だと失敗すること）、「個別にデプロイ」の deploy:prod にも前提として注記した。次はユーザーが deploy:prod を流し直す。

## 2026-11-16 本番の初回デプロイの完了を確認

- 2026-11-15 の夜に流し直した deploy:prod は成功していた（ProductionStack は 2026-11-15 21:56 JST に CREATE_COMPLETE）。2026-11-16 朝に確認した。
- ECS: prod-alphasys-unified-service は 2/2 で steady state（イメージは 0.5.0）。
- backend のログ: 22:00〜22:02 に P1001 と alphasys_app の認証失敗が出ていたが、DB と app ユーザーを作っている途中のもの。22:07 に 2 タスクとも「Nest application successfully started」が出ていて、「営業メール取り込みは無効」（想定どおり false）。
- https://alphasys.alphacmc.com/ は 307（ログインへのリダイレクト）。SES の alphasys.alphacmc.com は、送信可・DKIM・MAIL FROM とも SUCCESS。
- alphasystem-62 に報告した。
- 残り: (a) prod-github-connection は PENDING → ユーザーがコンソールで承認し、MainEcsDeployPipeline を 1 回動かす（1-3-B-1）。(b) 本番のサービスアカウントの共有ドライブ書き込み権限は未確認。(c) DB のスキーマとデータ（マイグレーション・移行）の状態は、alphasyscdk では見ていない。

## 2026-11-16 本番のパイプラインが 0.1.0 に戻した件

- ユーザーが prod-github-connection を承認し（AVAILABLE）、MainEcsDeployPipeline を手で動かした（08:26、Source / ImageBuild / Deploy とも Succeeded）。
- ユーザーの指摘「alphasysdeploy が 0.1.0 のまま」で確認したところ、パイプラインが alphasysdeploy の main の version.json（0.1.0）を読み、本番の ECS をタスク定義 :2（frontend/backend とも 0.1.0）に入れ替えていた。
- 0.1.0 は SALES_MAIL_POLLING_ENABLED を見ないため、本番が共有のメールボックスを取り込み始めた（08:30 に IMAP に接続し、UID SEARCH UNSEEN を実行した）。10 分ごとに動く。staging の未読メールが本番に取られるおそれがある。
- 手順書の 1-3-B-1 にある「承認した後に、パイプラインを手で 1 回動かす」は、alphasysdeploy の version.json がリリースする版になっていることが前提だった。この前提が抜けていた。
- 提案（了解待ち）: (1) 今すぐ `aws ecs update-service --task-definition prod-alphasys-unified:1`（CDK が作った版。0.5.0、取り込みは false）で戻す。(2) alphasysdeploy の main の version.json を 0.5.0 にする（担当と時期は alphasystem と調整する）。それまではパイプラインを手で動かさない。
- ユーザー承認（「今すぐの対処案、承認します」）→ 08:35 に update-service で本番をタスク定義 :1（0.5.0、取り込みは false）に戻した。08:40 に 2 タスクとも :1 で RUNNING。
- 影響の確認: 0.1.0 のタスクは 08:30 と 08:40 に取り込みを実行していたが、2 回とも UID SEARCH UNSEEN の結果が空で、FETCH も STORE も無い。メールは取られていない。
- alphasystem-62 に報告し、alphasysdeploy の main の version.json を 0.5.0 にするよう依頼した（担当と時期は先方で調整）。直るまではパイプラインを手で動かさない。
- 手順書の 1-3-B-1 に「パイプラインを動かす前に version.json の版を確かめる」を書き足すことを、ユーザーに提案する（了解待ち）。
- alphasystem-62 から: alphasysdeploy の main と staging は、どちらも version.json が 0.1.0 のまま。alphasysdeploy に担当のセッションは無く、修正はユーザーの了解を取ってから alphasystem が行う。案: staging の version.json を 0.5.0 にして staging のパイプラインの成功を確かめ、その後 main にも反映する。それまで alphasysdeploy には push せず、パイプラインも手で動かさない。手順書 1-3-B-1 の追記には同意（ユーザーに提案する）。
- 補足（こちらの気づき）: staging も、パイプラインが今の version.json（0.1.0）で動くと、0.1.0 に戻る。staging の 0.1.0 は取り込みのフラグを見ないが、staging はもともと取り込み ON なので、メールの面では影響しない。
- ユーザー承認（「1> 修正案で進めてください。2> 書き足してください。」）:
  - (1) alphasysdeploy の version.json の修正案（staging を 0.5.0 にする → staging のパイプラインの成功を確かめる → main に反映）を了承。alphasystem-62 に伝えた。main に反映したら、本番の ECS が 0.5.0 で安定するかをこちらで確かめる。
  - (2) 手順書の 1-3-B-1 に「パイプラインを動かす前に alphasysdeploy の version.json を確かめる」を書き足した（今回の経緯と、戻し方も添えた）。
- alphasystem-62 から: alphasysdeploy の PR #4（staging）と #5（main）をユーザーがマージした。staging のパイプラインは成功（タスク定義 :90、0.5.0、取り込み true）。本番の MainEcsDeployPipeline は 08:59 に自動で動いて成功した（タスク定義 :3、2/2、0.5.0、取り込み false）。
- こちらで本番を確認した（09:05）: タスク定義 :3、frontend/backend とも 0.5.0、SALES_MAIL_POLLING_ENABLED=false。09:01 に新しいタスク 2 つが「営業メール取り込みは無効」を出している。IMAP の接続は 0.1.0 のタスクの 08:30 と 08:40 の 2 回だけで、それ以降は無い。直近 20 分の ERROR は 0 件。alphasystem-62 に報告し、手順書の追記が済んでいることも伝えた。→ 本番のパイプラインが 0.1.0 に戻した件は解決。

## 2026-11-23 ECS サービスの再起動スクリプトの方式案（了解待ち）

- ユーザーの依頼: scripts 配下に、staging と本番の ECS サービスを再起動するスクリプトを作る。
- 方式案（了解待ち）: backup-db と同じく、環境を引数で受ける `scripts/restart-ecs.sh <staging|prod>` と `scripts/win/restart-ecs.ps1 <staging|prod>`（BOM 付き・CRLF）。アカウント ID を照合する（staging 570024666076 / prod 938812705475）。今のタスク定義・イメージ・タスク数を表示する。prod は `prod` と打ち込んで確認する。タスク数が 0 なら再起動せずに start-staging.sh を案内する。`update-service --force-new-deployment` で、タスク定義とタスク数は変えずにタスクを入れ替える。`wait services-stable` で待ち、結果を表示する。手順書の運用の章に使い方を書き足す。ブランチは staging から feature/restart-ecs-scripts。
- ユーザー承認（「この方式で作成してください。」）→ feature/restart-ecs-scripts で作成した。
  - `scripts/restart-ecs.sh` と `scripts/win/restart-ecs.ps1`（BOM 付き・CRLF）。README の「5. 個別操作コマンド」に使い方を足し、手順書の force-new-deployment の箇所から参照した。
  - 確認: 構文チェックは両方 OK。両方を prod で動かし、確認で「no」と答えて、アカウント照合・状態表示・中止まで正しく動くことを確かめた（再起動はしていない）。引数が不正なときは使い方を表示して終わる。実際の再起動（update-service と wait）は未実行。
  - 取り込み済みの旧ブランチ feature/record-backend-050 を削除した。

## 2026-11-24 PR ＃152（ECS 再起動スクリプト）のマージを確認

- PR #152 はマージ済みだった。ローカルの feature/restart-ecs-scripts は残っていなかった。
- 実際の再起動（update-service と wait）は、まだ一度も動かしていない（11/23 の記録のとおり）。

## 2026-11-24 WAF 導入と警告の日次レビューの方式案（ユーザー了承待ち）

- alphasystem から依頼が来た（ユーザー了承済み。記録先は alphasystem `docs/conversations/2026-11-24.md`）。今回は方式案の作成まで。**実装は、方式案をユーザーが了承してから。**
- 依頼の前提（ユーザー決定）: 既存の ALB に WAF（REGIONAL）を付ける。まず Count で運用する。AWS マネージドルール 3 種とレート制限を使う。ログは CloudWatch Logs。通知は Google Chat に日次。staging → 本番 → Block の順。証憑表示（alphasys PR #340）の本番反映を先にする。
- 方式案: [docs/superpowers/specs/2026-11-24-waf-design.md](../superpowers/specs/2026-11-24-waf-design.md)。要点は次のとおり。
  - WAF は本体とは別のスタック（`StagingWafStack`／`ProductionWafStack`、`deploy:waf:*`）にする。本番の WAF の反映が ECS に触れないので、PR #340 と干渉しない。
  - 日次レポートは EventBridge Scheduler（9:00 JST）から Lambda を動かす。CloudWatch メトリクスと Logs Insights で集計し、Google Chat の Webhook に送る。「問題あり」の基準案は A〜E（誤検知の疑い・レート制限の発動・同一 IP への集中・検知の急増・仕組みの異常）。
  - Webhook URL は SSM SecureString の `/alpha/<stg|prod>/alphasyscdk/WAF_REPORT_WEBHOOK_URL` に置き、ユーザーが `Read-Host -AsSecureString` で登録する。
  - ALB アクセスログ（S3）は有効にする案。サイズ制限の例外を決める実測（`received_bytes`）にも使う。本体スタックの変更なので、本番では PR #340 の後の deploy:prod で入れる。
  - 費用は約 $10〜11／月・環境（2 環境で約 $20〜23）。
  - ユーザーに決めてほしいこと: 自社の固定 IP、Chat スペース、通知の時刻、ALB ログ、ログの範囲、保持期間、Count の期間。
- 方式案は Draft PR #154 に入れ、alphasystem に送った（alphasystem からユーザーに出してもらう）。

## 2026-11-24 WAF 方式案へのユーザー回答を受領（alphasystem 経由）

- alphasystem から、ユーザーの回答と「実装に着手してください」が届いた。方式案は了承された扱い。
  1. 自社の固定の出口 IP はある。値は未受領で、props（`trustedIpCidrs`）で受けて後から入れる。
  2. Webhook の発行・登録はユーザー本人。Chat スペースを staging・本番で共用するかは、alphasystem が再確認中。
  3. 通知は**毎日 7:00 JST**（案の 9:00 から変更）。
  4. ALB アクセスログ（S3）は有効にする。本番は deploy:prod で入れる。
  5. WAF のログは検知分だけ。6. 保持期間は staging 30 日・本番 90 日。
  7. Count の期間は **staging・本番とも 1 週間**（本番は案の 2〜4 週間から変更）。
- 段取り: staging 向けを先に実装して Draft PR（base staging）にする → staging で Count を 1 週間運用して確認 → 本番に導入（PR #340 の本番反映の後）→ 本番で Count を 1 週間 → Block に切り替え。
- Webhook URL はコードにも記録にも書かない（ユーザーが `Read-Host -AsSecureString` で SSM に登録する）。
- 方式案の文書（7:00・本番の Count 1 週間・`trustedIpCidrs`・9 章の回答）を更新した。
- 他のセッションからのメッセージは承認として扱わないルールなので、**実装への着手は、このセッションでユーザーに確認してから**にする。

## 2026-11-24 WAF の staging 向け実装に着手（ユーザー承認）と、方式の訂正

- ユーザーに直接確認し、承認を得た（「着手してよい」）。staging 向けの実装を PR #154 に積む。デプロイはしない。
- alphasystem から次の訂正が届いた。
  - **自社の固定の出口 IP は「ある」を取り消す。** テレワークや NordVPN を使うため、出口 IP を限定できない。
  - 基準 A は「業務パスへの検知」だけにする。IP の設定値（props）は設けない。
  - Chat スペースは、staging・本番とも**同じスペース**にする。件名の先頭に `[staging]`／`[本番]` を付ける。
  - Webhook はユーザーが SSM に登録する。staging・本番で同じ URL を別のパラメータに入れてよい。
  - これで方式案に未確定の事項はなくなった。方式案の文書も直した。
- 実装したもの:
  - `lib/waf-stack.ts`
  - `lib/constructs/waf.ts`
  - `lib/constructs/waf-daily-report.ts`
  - `lib/constructs/lambda/waf-daily-report/`（判定は `judge.ts`）
  - `bin/app.ts` に `StagingWafStack` を追加した（count・レート 2000/5 分・ログ 30 日）。
  - 業務パスの初期値は次の 3 つ。Count の期間に見直す。
    - `/money-forward/oauth/callback`
    - `/common/mf-csv`
    - `/member/skills/infoset/sheet-upload`
  - ALB アクセスログ: `AlbConstruct` に `accessLogRetentionDays` を追加し、staging だけ 30 日にした。本番は後の PR で入れる。
  - npm スクリプト: `deploy:waf:staging`・`diff:waf:staging`
  - 手順書: 5-2-3 を追加した（Webhook の登録・diff の確認・動作の確認・問題ありのとき・戻し方）。
  - テスト: `test/waf.test.ts`（13 件）。全体の 20 件が通った。
- `npm run diff:staging` の結果（読み取りだけ）:
  - StagingStack の差分は、S3 バケットとそのポリシー、ALB の `access_logs.*` 属性だけ。ECS の変更はない。
  - StagingWafStack は新しいリソースだけ。
  - ALB の検索結果は `cdk.context.json` にキャッシュされた。
- 未確認（staging にデプロイしてから確かめる）:
  - WAF のログのフィルタ（COUNT・BLOCK・EXCLUDED_AS_COUNT）が、マネージドルール群を Count にしたときの検知を拾えるか
  - ALB のログの配信が、`enforceSSL` を付けたバケットで通るか
- 次の段取り:
  1. ユーザーが PR をマージする。
  2. ユーザーが Webhook を `/alpha/stg/alphasyscdk/WAF_REPORT_WEBHOOK_URL` に登録する。
  3. `diff:staging` を確かめてから `deploy:staging` を流す。
  4. `aws lambda invoke` で通知が届くことを確かめる。
  5. staging で Count を 1 週間運用する。
  6. 本番（PR #340 の本番反映の後）に入れる。

## 2026-11-24 WAF の業務パス（基準 A）を追加

- alphasystem から追加の候補が届いた（alphasys-bb が staging のコードで確認した）。PR #154 に反映した。
  - 外部サービスからの戻り: `/api/auth/callback/google`（NextAuth の Google ログイン）・`/money-forward/oauth/callback`
  - ファイルを Server Actions で送るページ:
    - `/common/mf-csv`
    - `/member/skills/infoset/sheet-upload`
    - `/sales/bill/add`
    - `/sales/bill/edit/`
    - `/sales/contract/confirm`
    - `/sales/contract/edit/`
- パスは前方一致で書く。可変部分（`{billNo}`・`{contractNo}`）は、その手前までを書く。
- 受領請求書の証憑（`/api/money-forward/payable/bill-recipts/{billNo}/e-doc-file`）は対象外。GET で、大きいのは応答のほうなので。
- Server Actions の本文は既定で 1MB まで送れる。WAF の検査上限 8KB を超えるので、ファイルを送るページは SizeRestrictions_BODY に当たる見込み。
- **Google ログインの戻りは、止まると誰もログインできない。** Count の期間は、ここへの検知を特に注意して見る。手順書 5-2-3 と方式案に書いた。

## 2026-11-24 PR ＃154 のマージと、staging の Webhook の登録

- ユーザーが PR #154 をマージした。取り込み済みの feature/waf-design は削除した。
- ユーザーが、マージ前に staging の Webhook URL を SSM に登録した。
  - パラメータは `/alpha/stg/alphasyscdk/WAF_REPORT_WEBHOOK_URL`（SecureString、Version 1）。
  - CDK とは別に置いてあり、Lambda が実行時に読むだけなので、マージより先に登録しても問題ない。
- マージ後に `npm run diff:staging` を確かめた（読み取りだけ）。マージ前と同じだった。
  - StagingStack は、S3 バケット・ポリシー・ALB の属性だけ。
  - StagingWafStack は、新しいリソースだけ。
- 次の段取り（未実施）:
  1. `npm run deploy:staging` を流す。
  2. `aws lambda invoke` で通知が届くことを確かめる。
  3. WAF のログと ALB のログが出ることを確かめる。
  4. staging で Count を 1 週間運用する。
- 気になる点: 登録時の入力欄の伏せ字は 44 個だった。Google Chat の Webhook URL は普通 150 文字を超えるので、貼り付けの途中で切れたかもしれない。
  - ユーザーに、値を表示せずに長さと形だけを確かめるコマンドを渡した。結果はまだ聞いていない。
  - おかしければ、手順書 5-2-3 の 1 で上書き登録する。デプロイ後の `aws lambda invoke` でも確かめられる。
- デプロイをユーザーと私のどちらが流すかは、ユーザーの回答待ち。
- 原因: ユーザーが登録したのは、スペースの URL（画面を開くリンク）だった。Webhook の URL ではなかった。
  - Webhook の URL の取得手順（スペース名の「▼」→「アプリと統合」→「Webhook を追加」）を案内した。
  - ユーザーが登録し直す。
  - 同じ間違いが起きないよう、手順書 5-2-3 の 1 に、取得手順と登録後の確認コマンドを書き足した。
- ユーザーが Webhook の URL を登録し直した（Version 2）。確認コマンドの結果は長さ 152・形 True で、正しい Webhook の URL が入った。

## 2026-11-24 WAF を staging に反映（ユーザーの指示で Claude が deploy:staging を流した）

- ユーザーの指示:「Claude が流す」。
- デプロイ前の確認: `.env` も、staging で動いている版も 0.5.0 で一致していた（タスク定義 :90）。
- 12:01〜12:04 に `npm run deploy:staging` を流した。
  - StagingWafStack を作成した（WebAclArn `…/regional/webacl/staging-alphasys-waf/ef7adde9-…`）。
  - StagingStack は、S3 バケット・ポリシー・ALB の属性の更新だけ。ECS はタスク定義 :90 のまま。
- 動作の確認:
  - WAF が `staging-alphasys-alb` に関連付けられた。
  - WAF のログのフィルタ（検知分だけ）は、Count の検知を拾えた。外部のスキャン（AWSManagedIPReputationList・NoUserAgent_HEADER）が記録された。Cookie と Authorization のヘッダーは記録されていない。
  - ALB アクセスログは S3（`stagingstack-albaccesslogbucket049f3881-…/alb/`）に届いた。`enforceSSL` を付けたバケットでも配信できた。
  - テストの XSS リクエスト（`?q=<script>…`）は Count なので通った（307）。ログに出たかは、配信を待って確かめる。
- **不具合**: 日次レポートの Lambda を手で動かしたら、`MalformedQueryException` で失敗した。
  - 原因: Logs Insights は、ロググループの作成時刻（今日の 12:01）より前に終わる範囲のクエリを受け付けない。前日分と直近 7 日分のクエリがこれに当たった。
  - このままだと、明日 11/25 7:00 の定期実行でも、直近 7 日分のクエリで失敗する。
  - 修正案（ユーザーの了承待ち）:
    1. ロググループの作成時刻を調べ、クエリの開始をそれ以降に切り詰める。作成より前に終わる範囲は、クエリせずに 0 件とする。
    2. 7 日平均は、データのある日数で割る。データが 1 日分もないときは、基準 D を判定しない。
    3. IAM に `logs:DescribeLogGroups` を足す。
    4. テストを足し、`deploy:waf:staging` だけを流す（ECS には触れない）。

## 2026-11-24 WAF 日次レポートの不具合を修正して staging に反映（ユーザー承認）

- ユーザー承認:「この方針で直す」。マージ前でも `deploy:waf:staging` で反映し、明日 7:00 に間に合わせる。
- 修正（PR #156）:
  - クエリの開始を、ロググループの作成時刻以降に切り詰める（`clampToCreation`）。
  - 7 日平均は、データのある期間で割る（`averagePerDay`）。データが 1 日分もないときは、基準 D を判定しない。
  - IAM に `logs:DescribeLogGroups` を追加した。
  - テストは全体で 23 件すべて通過した。
- 12:30 に `deploy:waf:staging` を流した。差分は IAM ポリシーと Lambda のコードだけだった。
- 手で動かした結果: 成功した。前日 11/23 分として `{"totalRequests":0,"detections":0,"findings":["E"]}` を Chat に送った。
  - E になったのは、11/23 には WAF がまだ無かったため。想定どおり。
  - 11/25 7:00 の定期実行では、11/24 の 12:01 以降が集計される。
- 最初の失敗の実行でも、「集計に失敗しました」の通知が Chat に 1 通送られているはず。
- テストの XSS リクエストは、`CrossSiteScripting_QUERYARGUMENTS` で検知・記録された。1 時間で検知は 21 件（ほとんどが外部のスキャン）。
- 次の段取り: 11/25 から staging で Count を 1 週間運用する。毎朝 7:00 の通知を見る。その後、本番の PR を出す（PR #340 の本番反映の後）。

## 2026-11-24 WAF の本番反映のタイミング（案。ユーザーの確認待ち）

- ユーザーから、Chat に通知が 2 通届いた（失敗の通知と、11/23 分の E）と連絡があった。想定どおり。
- ユーザーの質問「本番への反映はどのタイミングか」に、次の案を出した。
  - **最短で 12/2（火）**。次の 3 つが揃ったら本番の PR を出す。
    1. staging で Count を 1 週間運用し終えている（11/25〜12/1 の 7 通。業務パス、特に Google ログインの戻りに致命的な誤検知がない）
    2. PR #340 が本番に反映済み。PR #340 は 11/23 に staging へマージ済みで、本番への反映は未確認。alphasystem に確認する。同じ日の作業は避ける。
    3. ユーザーが本番の Webhook（`/alpha/prod/alphasyscdk/WAF_REPORT_WEBHOOK_URL`、staging と同じ URL でよい）を登録している
  - 本番の反映の順番:
    1. 本番の PR を出す（`ProductionWafStack`・ログ 90 日、`deploy:waf:prod`、本番の ALB アクセスログ 90 日）。
    2. `deploy:waf:prod` で WAF を反映する（ECS には触れない）。
    3. 差分と `.env` の版を確かめてから、`deploy:prod` で ALB アクセスログを入れる（2 と同じ日でも別の日でもよい）。
    4. 本番で Count を 1 週間運用する（例: 12/3〜12/9）。
    5. staging → 本番の順に Block に切り替える（12/10 以降）。
- alphasystem に、PR #340 が本番に反映済みか（予定日があればそれも）を問い合わせた。回答待ち。
- PR #156 はユーザーがマージ済みだった。この記録は、新しいブランチ feature/record-waf-prod-timing の Draft PR #158 に移した。
- alphasystem の回答: 証憑表示は本番に反映済み。
  - alphasys #338/#340/#342 はマージ済みで、staging と本番の ECS の再起動も済んでいる。alphaexapi #227/#229 と alphadb 0.5.1/0.5.2 も本番に反映済み。反映は 11/24 以前。
  - → **12/2 案の条件 2 は満たした。** 残る条件は、1（staging の Count 1 週間）と 3（本番の Webhook の登録）。
  - 実機の確認（AP1354 の PDF 表示、MF 未連携ユーザーへの案内）の報告は、まだ届いていない。ただし WAF のタイミングを妨げるものではない。

## 2026-11-24 WAF の本番反映の段取りを確定（ユーザー承認）

- ユーザー承認:「その段取りで進めてください。」
- 確定した段取り:
  1. 11/25〜12/1: staging で Count を運用する。毎朝 7:00 の通知（11/24 分〜11/30 分）で、業務パス（特に Google ログインの戻り）の検知を見る。
  2. 12/2 まで: ユーザーが本番の Webhook を `/alpha/prod/alphasyscdk/WAF_REPORT_WEBHOOK_URL` に登録する（staging と同じ URL でよい）。
  3. 12/1 の結果を見て、本番の PR を準備する（`ProductionWafStack`・ログ 90 日、`deploy:waf:prod`・`diff:waf:prod`、本番の ALB アクセスログ 90 日）。
  4. 最短で 12/2（火）: `deploy:waf:prod` で WAF を反映する。差分と `.env` の版を確かめてから、`deploy:prod` で ALB アクセスログを入れる。
  5. 本番で Count を 1 週間運用する（例: 12/3〜12/9）。
  6. 12/10 以降: staging → 本番の順に Block に切り替える。
- 条件 2（PR #340 の本番反映）は満たしている。

## 2026-11-26 本番移行（カットオーバー 12/3）の依頼と、WAF の本番反映の延期

- alphasystem から依頼が来た。本番移行の計画書（`alphasystem/docs/design/2026-11-26-本番移行-計画.md`、ユーザーの最終了承済み）の alphasyscdk 担当分。
  - 日程: 12/2（水）19:00 に旧システムを凍結 → 12/3（木）01:00 に夜間移行の最終実行 → 午前に停止・確認 → 9:00 に業務開始。準備は 12/2 まで。
  - alphasyscdk の作業:
    - 0-1 日次バックアップの S3（本番専用、SSE-KMS、7 日、他アカウントを拒否、書込は本番 Bastion）と、失敗の監視
    - 0-2 リレーバケット（マスキング済みだけ、書込は本番 Bastion、読取は staging Bastion、短期）
    - 0-5 staging の Drive（本番ドライブは閲覧のみ、staging 用の共有ドライブ、`SHARED_DRIVE` の差し替え。既存フォルダの更新は staging では失敗する扱い）
  - 方式案を先に出し、ユーザーの了解を得てから着手する。本番へのデプロイと確認はユーザーが行う。
- **WAF の本番反映は延期する（ユーザー決定）。** カットオーバーの前後は避ける。11/24 に確定した「最短 12/2」の段取りは取り下げ。日付はカットオーバーの後に改めて決める。staging の Count 運用はそのまま続ける。
- 訂正: 11/24 の記録で「12/2（火）」と書いたが、12/2 は**水曜**。
- 方式案（ユーザー了承待ち）: [docs/superpowers/specs/2026-11-26-db-backup-relay-design.md](../superpowers/specs/2026-11-26-db-backup-relay-design.md)
  - バックアップとリレーは、本体とは別のスタック（`ProductionBackupStack`・`StagingRelayAccessStack`）にする。本番の ECS・Bastion に触れず、Bastion のロールに IAM ポリシーを付け足すだけ。
  - 本番への反映は 12/1（火）の日中に、ユーザーが行う。12/2 19:00〜12/3 は alphasyscdk のデプロイをしない。
  - 失敗の監視: 毎朝 7:30 に確認の Lambda が、S3 の最新のダンプとログの `RESULT:` を見て、Google Chat に送る。「動かなかった」ことも拾う。
  - **staging と本番は同じサービスアカウント（googledrivemanager。鍵だけ別）を使っている。** そのため、staging だけを本番ドライブの閲覧のみにできない。staging 専用のサービスアカウントを新しく作る案を出した。CDK の変更は要らない（SSM の値の差し替えと ECS の再起動だけ）。
  - ユーザーに決めてほしいこと（方式案 7 章）: 別スタック、反映日、通知、staging 専用のサービスアカウント、テンプレートの置き場所、KMS キー。

## 2026-11-27 本番移行の準備の方式案を了承（ユーザー）と、alphadb との取り決め

- ユーザーが方式案 7 章を次のとおり決めた。
  1. **この方式で着手する**: 別スタックにする。本番への反映は 12/1（火）の日中にユーザーが行う。12/2 19:00〜12/3 はデプロイしない。KMS キーはバックアップとリレーで別々にする。
  2. バックアップの確認の通知は、**毎朝 7:30 に 1 通**（問題なしでも短く送る。WAF と同じスペース）。
  3. **staging 専用の Google サービスアカウントを作る**（ユーザーが Google Cloud で作る）。
  4. staging のテンプレートは、**staging 用の共有ドライブに移す**（`template-ids.staging.json` を更新して `deploy:staging`）。
- alphadb-da から、取り決めのすり合わせが届いた（alphadb の方式案はユーザーの了承待ち）。
  - 置き場所は `daily/YYYY-MM-DD/alphasys-YYYYMMDD-HHMMSS.dump`（`pg_dump -Fc`）。
  - ログは `/alphasys/prod/db-backup`。ストリーム名は `backup-YYYYMMDD-HHMMSS`。最後の 1 行が `RESULT: SUCCESS` か `RESULT: FAILED (STEP …) rc=N`。
  - 取得は毎日 2:00 JST。削除の権限は要らない。
  - 12/1〜12/2 昼に、スクリプトを配布して手で 1 回動かす（ユーザーが実行）。タイマーの有効化は 12/3 夜。
  - alphadb の質問への回答:
    1. 暗号化のヘッダーを付けない PutObject（既定の暗号化に任せる）は許す書き方にする（`StringNotEqualsIfExists`）。
    2. マルチパートに必要な権限（`s3:PutObject` に含まれる・`kms:GenerateDataKey`・`kms:Decrypt`）を付ける。`s3:AbortMultipartUpload` も付ける。
    3. 設定値（BACKUP_BUCKET・LOG_GROUP・夜間移行と同じ DB の export）は、これで足りる。

## 2026-11-27 日次バックアップ・リレーバケットを実装（PR ＃160）

- 実装したもの（ユーザーの了承に基づく）:
  - `lib/backup-stack.ts`（`ProductionBackupStack`）と `lib/constructs/db-backup.ts`
    - S3 ×2（SSE-KMS・バケットキー・パブリックアクセス遮断・TLS 強制・7 日／3 日・RETAIN）
    - KMS ×2（ローテーションあり）
    - ロググループ `/alphasys/prod/db-backup`
    - 確認の Lambda と、毎朝 7:30 JST のスケジュール
  - `lib/relay-access-stack.ts`（`StagingRelayAccessStack`）: staging の Bastion に、リレーの読取と、S3 経由の復号だけを付ける。
  - 判定: `lib/constructs/lambda/db-backup-check/check.ts`。直近 26 時間の最新のダンプが 0 バイトでないことと、最後の `RESULT:` が SUCCESS であることを見る。
  - `cdk.json` に `bastionRoleName` を追加した。
    - staging は `StagingStack-SsmEc2BastionInstanceRole3094ABFF-hsR02A1lWWHI`。
    - **本番は空**。空の間は `ProductionBackupStack` を作らないので、`deploy:prod` は止まらない。
  - npm スクリプト: `deploy:backup:prod`・`diff:backup:prod`・`deploy:backup:staging`・`diff:backup:staging`
  - 手順書: 5-2-4 を追加した。
  - テスト: `test/backup.test.ts`。全体の 35 件が通った。
- `npm run diff:staging`（読み取りだけ）: StagingStack・SharedStack・StagingWafStack は差分なし。StagingRelayAccessStack は IAM ポリシー 1 つの追加だけ。
- 未了:
  - **本番の Bastion のロール名**（ユーザーに読取専用のコマンドで確かめてもらう）。`cdk.json` に入れてから、本番の diff を見る。
  - staging の Drive は、ユーザーが staging 専用のサービスアカウントを作った後に行う。
    - 手順書 `google-service-account-key.md` の書き直し
    - テンプレートの配置スクリプトを、環境ごとに親フォルダを持てるように直す（今は親フォルダが 1 つ）

## 2026-11-27 バックアップの確認の通知は 12/4 から（ユーザー決定）と、alphadb のスクリプト

- alphadb-da が、日次バックアップのスクリプトを Draft PR alphacmc/alphadb#147 にした。
  - 暗号化のヘッダーは付けない。
  - 使う API は `s3 cp`（分割アップロード）と `s3api head-object`（`s3:GetObject` の権限で通る。KMS の復号は要らない）。削除はしない。
  - staging で試した。DB 71MB → ダンプ 4MB。存在しないバケットを指定したので、アップロードで想定どおり FAILED になった。
  - 段取り:
    1. 12/1 の本番反映の後、12/1〜12/2 昼に、ユーザーがスクリプトを配布して手で 1 回動かす。
    2. 12/3 夕方、夜間移行を止めた後に、タイマーを有効にする。
    3. 初回の取得は 12/4 2:00。
- 気づいた点: 確認の Lambda は 12/1 の反映直後から毎朝動く。そのため、12/2 の朝と 12/3（カットオーバー当日）の朝に「問題あり」を送ってしまう。
- **ユーザー決定: 確認の通知は 12/4 から動かす。**
  - スケジュールに開始日 12/4 7:00 JST を入れた（初回の通知は 12/4 7:30）。
  - 開始日を過ぎた後のデプロイでは、開始日を指定しない。
  - 手で 1 回動かしたときの確認は、`aws lambda invoke` で行う。
  - テストは 35 件すべて通過した。手順書 5-2-4 と方式案 2.2 にも書いた。
