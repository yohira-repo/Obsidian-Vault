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
