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
