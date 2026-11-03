# alphacdk 作業ログ

## 2026-07-29 READMEに運用パターン別コマンド一覧を追加

- **経緯**: 「README.md に、運用パターン別にどの契機にどのコマンドを発行するかをまとめてほしい」との依頼。既存READMEはKeyPairsStack/NetworkStack/LaunchTemplatesStack/Ec2NativeTemplateStackそれぞれのデプロイ手順は書かれているが、契機(いつ実行するか)を軸にした整理はなかった。
- **調査**:
  - `package.json`のスクリプト、`bin/alphacdk.ts`のスタック構成(AlphacdkStack/Ec2NativeTemplateStack/LaunchTemplatesStack/NetworkStack/KeyPairsStack)を確認。
  - 隣接プロジェクト`~/git/alphasyscdk`(alphasys/alphaexapiのECS/RDS/ALB/CI-CDインフラ)との関係を調査したところ、コード上の連携(VPC importやCloudFormation Export参照)は見当たらず、alphasyscdk側は自前でVPCを作成していることを確認。
  - **⚠️ 訂正(2026-07-31)**: 上記「連携は見当たらない」は誤り。alphaexapi の研修用EC2払い出し機能(`instance-create.service.ts`)が alphacdk の `Ec2NativeTemplateStack` テンプレートと `alphacmc-linux`/`alphacmc-windows` Launch Template に直接依存していることが後続セッションで判明。下記 2026-07-31 の記録を参照。
- **結論**:
  - alphacdkとalphasyscdkの関係性の記載は本READMEには不要と判断(ユーザー確認済み)。関係を書くなら`alphasyscdk`側に書いた方がわかりやすい、との方針。
  - README冒頭に「運用パターン別コマンド一覧」の表(7パターン: 初回環境構築/NetworkStack設定変更/KeyPairs再デプロイ・鍵取得/LaunchTemplate新規作成/LaunchTemplate更新/EC2動的払い出し/テンプレート妥当性確認)を追加し、各行から既存の詳細手順セクションへアンカーリンクを張った。
  - CLAUDE.mdの運用ルールに従い、`feature/readme-ops-patterns`ブランチを作成し、Draft PR([#3](https://github.com/alphacmc/alphacdk/pull/3))を作成。Draft解除・マージはユーザー側で実施。
- **次のアクション**: 特になし。Draft PRのレビュー・マージ判断はユーザー待ち。

## 2026-07-31 alphasyscdk との照合と環境体系の整合

- **経緯**: 「alphacdkについてもalphasyscdkと照合して、矛盾ないかチェックお願いします」との依頼。前セッションの「技術連携なし」という結論を再検証した。
- **判明した事実(前回の訂正)**:
  - alphaexapi の `src/admin/aws-instance/instance-create/instance-create.service.ts` が `CreateStackCommand` で alphacdk の `Ec2NativeTemplateStack.template.json` を実行し、Launch Template 名 `alphacmc-linux`/`alphacmc-windows`(alphacdk の LaunchTemplatesStack が作成)を指定している。テンプレート内部は NetworkStack の CloudFormation Export(`NetworkStack-LinuxSgId` 等)を `Fn::ImportValue` で参照。**研修用EC2払い出し機能(設計A)は alphacdk のインフラに直接依存している。**
- **見つかった矛盾と対応(いずれもユーザー確認済み)**:
  1. **ブランチ運用**: alphasystem/docs の branch-strategy(2026-07-30確定)は「staging からブランチを作成し staging にマージ」。PR #3 は main 向けだったが確認時点で既にマージ済み(main=staging で実害なし)のため base 変更は不要。本件の修正から staging 起点のブランチ運用に切り替え。
  2. **本番アカウント不一致**: alphacdk は全環境 `570024666076` 固定だったが、alphasyscdk は staging=`570024666076` / prod=`938812705475`。→ alphasyscdk に合わせ、`.env.staging`/`.env.prod` でアカウントを分離。
  3. **.env の Git 管理**: secret-management-design(2026-07-28)の方針に反し `.env*` が Git 追跡されていた。→ alphasyscdk と同方式(`.env*` は Git 管理外、`*.example` のみ追跡)に変更。旧ファイルに秘密情報は無し(アカウントIDのみ)。
  4. **環境名の不一致**: alphacdk は `dev`/`stg`/`prd`(既定 prd)、alphasyscdk は `staging`/`prod`(既定 staging)。→ `staging`/`prod`(既定 staging)に統一。npm スクリプトも `deploy:net:staging`/`deploy:net:prod` 等にリネームし、`--profile` 固定指定は廃止(シェル側の AWS_PROFILE に委譲)。
  5. **軽微な不整合**: namePrefix のコード既定値 `alphasys` → 実運用値 `alphacmc` に変更。cdk.context.json から使途不明アカウント(525459588860)の AZ キャッシュを削除。`.env.prd` の `AWS_PROFILE=stg` 矛盾は .env 体系刷新で解消。ManagedBy タグ値 `alphasys` → `alphacmc`(コード依存なしを確認済み)。
  6. **Windows インスタンス名のタイポ(照合で新たに発見)**: Ec2NativeTemplateStack が Windows 機の Name タグを `clinect-${UserId}` としていたが、alphaexapi の instance-control は `client-${userId}` / `client-*` で検索しており、**Windows 機が一覧・操作機能から見えなくなる実バグ**。`clinect` は alphaexapi/alphasys のどこにも存在しないため alphacdk 側のタイポと判断し `client-` に修正。
- **重要な注意(未実施)**: 既存の NetworkStack は旧既定 `envType=prd` でデプロイ済み(リソース名 `alphacmc-prd-*`)。新体系で再デプロイすると `alphacmc-staging-*` へのリネームで SG・IAMロール等の**置換が発生**する。READMEに移行メモとして記載。デプロイ実施の判断はユーザー側。
  - **→ 解消済み(2026-07-31)**: ユーザーが旧スタックを削除し新体系で再作成する方式で移行完了(置換問題は発生せず)。詳細は同日の「初回環境構築手順の整備」の訂正記録を参照。
- **未決事項**: alphaexapi の研修用EC2払い出しは staging アカウントのインフラにしか存在しないため、本番(938812705475)で同機能を使う場合は alphacdk の各スタックを prod にもデプロイする必要がある。

## 2026-07-31 AWSプロファイルの staging/prod 統一と npm スクリプトへの --profile 埋め込み

- **経緯**: 「.env.xxx にアカウントIDとリージョンしか指定していないのにどうやってAWSへアクセスしているのか」との質問から、認証の仕組みを整理。`.env` の `CDK_DEFAULT_ACCOUNT`/`REGION` は認証情報ではなくデプロイ先の宣言(アカウント突き合わせガード)であり、実際の認証は AWS CLI と共通の `~/.aws/credentials` を CDK CLI が標準チェーン(`--profile` → `AWS_PROFILE` → `default`)で解決していることを説明。「都度 `AWS_PROFILE` を指定するのは煩雑」との要望を受け、方式を協議。
- **結論(ユーザー決定)**: 「プロファイル名を環境名に統一 + npm スクリプトに `--profile` 埋め込み」の複合方式を採用。alphasyscdk にも同方式を適用する。
  - `~/.aws/credentials` のプロファイルを改名: `stg` → `staging`(570024666076)、`prd` → `prod`(938812705475)。`~/.aws/config` に両プロファイルの region 設定を追加。改名前のファイルは `~/.aws/*.bak-20260731` にバックアップ。
  - npm スクリプトに `--profile staging` / `--profile prod` を埋め込み(環境名とプロファイル名が常にペアになるため指定忘れが構造的に起きない)。
  - 前提条件(環境名と同名のプロファイルが必要)を README「AWS 認証プロファイル」セクションと `.env.example` に記載。
- **改名の影響(要フォロー)**:
  - `alphasyscdk/docs/構築・メンテナンス手順.md` に旧プロファイル名(`--profile stg`/`prd`)と旧 alphacdk 環境体系(dev/stg/prd)の記述が多数 → alphasyscdk 側の対応で更新する。
  - `alpha-ai-system/README.md` に `--profile prd` が3箇所 → 旧名は既に無効のため、当該リポジトリを触る際に `--profile prod` へ更新が必要(未対応)。
- **補足**: cdk.context.json にあった使途不明アカウント 525459588860 は `alphacmc` プロファイルの向き先と判明(過去に同プロファイルで synth した際のAZキャッシュ)。

## 2026-07-31 「deploy:key:staging でエラー」の切り分け → エラーではなく成功と判明

- **経緯**: `npm run deploy:key:staging` 実行時のログを「エラーが発生した」として相談を受けたが、実際は KeyPairsStack のデプロイは成功していた(✅・Outputs・Stack ARN 出力あり)。
- **紛らわしかったメッセージの正体**:
  - dotenv の `"CDK_DEFAULT_ACCOUNT" is already defined and was NOT overwritten`(DEBUG行): CDK CLI が `--profile` の実クレデンシャルから `CDK_DEFAULT_ACCOUNT`/`REGION` を先に設定するため、dotenv が上書きしないという正常動作の報告。`bin/alphacdk.ts` の `debug: true` が原因で表示されていた。
  - `CfnEIPAssociationProps#eip is deprecated`(WARNING): nat-construct.ts が非推奨の `eip` プロパティを使用していたため。
  - CDK新バージョン案内・テレメトリNOTICES: 単なるお知らせ。
- **対応(ユーザー了承済み)**: dotenv の `debug: true` を削除、EIP関連付けを `eip: eip.ref` → `allocationId: eip.attrAllocationId` に変更(synth で警告消滅・`AllocationId` 出力を確認)。
- **注意**: `allocationId` への変更は CloudFormation 上 EIPAssociation リソースの**置換**になるため、デプロイ済み NetworkStack に適用する際は NAT の通信が一瞬切れる可能性がある。

## 2026-07-31 初回環境構築手順の整備と deploy:lts スクリプト追加

- **経緯**: `deploy:key:staging` 実行後「運用パターン表の初回環境構築はこれで良いのか、KeyPairsStackしかできていない」との指摘。表の行1には bootstrap・LaunchTemplatesStack・synth:native(alphaexapi連携用)が抜けており不完全だった。
- **対応(ユーザー了承済み)**:
  - README に「初回環境構築手順」セクションを新設(1.準備 → 2.bootstrap → 3.キーペア → 4.ネットワーク → 5.Launch Template → 6.synth:native)。表の行1はこのセクションへのリンクに変更。
  - `deploy:lts`/`deploy:lts:staging`/`deploy:lts:prod` スクリプトを追加。`bin/alphacdk.ts` で LaunchTemplatesStack の `stackName` を既存の手動 create-stack 由来のスタック名 `alphasys-launch-templates` に固定したため、`cdk deploy` が既存スタックの差分更新として機能する(create-stack/update-stack の使い分けが不要に)。表の行4(新規作成)・行5(更新)も同一コマンドに簡素化。
- **staging に関する注意(READMEにも記載)**: staging(570024666076)は既にインフラがあるため初回構築対象ではない。`deploy:net:staging` は旧名 `alphacmc-prd-*` → `alphacmc-staging-*` の置換を伴う更新になるため、実行前に `cdk diff` での確認を推奨。
- **⚠️ 上記注意の訂正(同日)**: この注意は実際のアカウント状態を確認せずに書いた推測で、誤りだった。ユーザーの実運用は「全スタックを削除して成功するまでやり直す」方式であり、CloudFormation を実確認した結果、旧 NetworkStack と `alphasys-launch-templates` は削除済み・新 NetworkStack は本日 `alphacmc-staging-*` 命名で新規作成済み(=旧体系からの移行は削除・再作成方式で完了)だった。README の注記と移行メモを実態に合わせて修正。教訓: **デプロイ済みリソースの状態に言及するときは、推測ではなく `aws cloudformation list-stacks` 等で実確認してから書く**。

## 2026-08-01 研修用インスタンスロールと共有S3バケットの追加

- **経緯**: 「研修用インスタンスのロールを作成しテンプレートのデフォルトに。研修インスタンスから共有アクセスできるS3バケットも作成。ポリシーは AmazonSSMDirectoryServiceAccess / AmazonSSMManagedInstanceCore / S3フルアクセス」との依頼。
- **方式(ユーザー決定)**: 既存 `alphacmc-MMSinstance-role` の改修ではなく**新規ロールを作成**。既存権限(/ssh-keys/* SSMパラメータ・CloudWatchAgentServerPolicy)は**両方維持**。バケットはスタック削除時に**中身ごと自動削除**(削除→再作成のやり直し運用に合わせる)。
- **実装**(NetworkStack 内の新規 `TrainingInstanceConstruct`):
  - IAMロール `alphacmc-{env}-training-instance-role`: AmazonSSMManagedInstanceCore + AmazonSSMDirectoryServiceAccess + CloudWatchAgentServerPolicy + 共有バケットへの `s3:*` + `/ssh-keys/*` SSMパラメータ読み書き(userdataのSSH鍵連携に必須のため維持)。
  - S3バケット `alphacmc-{env}-training-shared`: パブリックアクセス全ブロック・SSE-S3・enforceSSL・DESTROY+autoDeleteObjects。
  - LaunchTemplatesStack(Linux/Windows両方)と Ec2NativeTemplateStack の既定インスタンスプロファイルを新ロールに差し替え。旧 MMS ロールは当初互換のため残置としたが、**ユーザー指示により削除**(MMSInstanceRoleConstruct と Outputs を除去。使用中インスタンスが無いことは実確認済み)。
  - NetworkStack に TrainingInstanceRoleName/RoleArn/ProfileName/SharedBucketName の Output/Export を追加。
- **要フォロー(重要)**: alphasyscdk の ECS タスクロールは `MMS_INSTANCE_ROLE_ARN`(環境変数)への `iam:PassRole` を持つ。デフォルトロール変更に伴い、**alphasyscdk の `.env` の `MMS_INSTANCE_ROLE_ARN` を新ロールARN(NetworkStack Output `TrainingInstanceRoleArn`)に更新して StagingStack を再デプロイ**しないと、alphaexapi からのインスタンス作成が PassRole 不足で失敗する。READMEにも記載。

## 2026-10-30 alphasystem からの申し送り（2026-10-28、alphasys 課題表 5_5_3 / 5_5_4）の取り込み

- **出典**: alphasystem `docs/design/2026-10-28-alphasys課題表6件-設計.md`（PR #122、マージ済み）の「4. 5_5_3 / 5_5_4」。決定記録は alphasystem `docs/conversations/2026-10-28.md`。10/23 にユーザーが alphacdk 側の変更を含めて進めると決定済み。設計の質問は alphasystem へ。
- **alphacdk の担当（未着手）**:
  1. **5_5_4 AMI 指定**: Ec2NativeTemplateStack に `ImageIdParam`（既定は空 = Launch Template の AMI）を追加し、指定があれば Instance の `ImageId` で上書きする。OS 種別（`OsParam`）は AMI とは別に渡される（直接指定 AMI でのデフォルトユーザーの配慮はしない）。
  2. **5_5_3 初回ログイン時のパスワード変更（Windows のみ）**: `userdata/windows-user-setup.ps1` で、ユーザー作成後に `net user <ユーザー名> /logonpasswordchg:yes` を実行する。Windows Server 2022 実機で、標準のリモートデスクトップ接続で変更画面が出ることを検証する（Mac クライアントでは出ない場合あり）。Linux は `ec2-user` のため変更なし。
  3. **alphaexapi への取り込み**: alphaexapi は `cdk.template/Ec2NativeTemplateStack.template.json`（コンテナ同梱）で CreateStack しているため、`npm run synth:native` で生成したテンプレートを alphaexapi に取り込む手順を確認する。
- **関連プロジェクトの状況（2026-10-30 時点で確認）**:
  - alphaexapi: 5_5_3 のユーザー名・初期パスワード（NoEcho）の受け渡しは実装済み（PR #182）。5_5_4 の AMI 指定は alphacdk の `ImageIdParam` 待ち。
  - alphasyscdk: ECS タスクロールに `ec2:DescribeImages` は既にあり、インフラ変更は不要。
  - alphaexapi 側から、UserData 経由のパスワード露出（`ec2:DescribeInstanceAttribute` で UserData が読める）を alphacdk 対応時に検討するよう申し送りあり（alphaexapi `docs/conversations/2026-10-30.md`）。
- **取り込み時に判明した前提の不具合（2026-10-30 実確認）**: 現行の `npm run synth:native` の出力は、`SubnetIdParam` / `SecurityGroupIdsParam` / `IamInstanceProfileArnParam` の Default に `Fn::ImportValue` / `Fn::If` を入れているため、`aws cloudformation validate-template` で `Template format error: Every Default member must be a string` になり、**そのままでは CreateStack できない**（c728764「テンプレートの初期値連携」で混入）。alphaexapi 同梱のテンプレートはそれ以前の版（Default は空文字、ManagedBy=alphasys）で、validate は通る。Launch Template 側で OS 別の SG・研修用インスタンスプロファイルは既に設定済みのため、Default を空文字に戻して LT 継承にすれば意図どおり動く。5_5_4 のテンプレートを alphaexapi へ渡す前に修正が必要。
- **次のアクション**: 上記を含む実装方式案をユーザーに提示し、了承を得てから着手する。

## 2026-10-30 5_5_3 / 5_5_4 と synth:native テンプレート修正の実装方針を承認

- **経緯**: 申し送りの取り込み時に、現行の `synth:native` の出力が CloudFormation の検証を通らないことが判明。c728764 のうち誤りは `ec2-native-template-stack.ts` のパラメータ既定値（`SubnetIdParam` / `SecurityGroupIdsParam` / `IamInstanceProfileArnParam` に `Fn::ImportValue` / `Fn::If`）のみで、同コミットの Launch Template・Export の変更は正しいことをユーザーと確認した。
- **承認された方針（ユーザー「修正案で進めてください。確認も行ってください」）**:
  1. テンプレート修正: 上記 3 パラメータの既定値を `''` に戻し、Launch Template の SG・インスタンスプロファイルを継承させる。**5_5_3 / 5_5_4 とは別 PR** にする。
  2. 5_5_4: `ImageIdParam`（既定 `''`）を追加し、指定時のみ Instance の `ImageId` を設定する。ルートデバイス名が LT と異なる AMI では追加ディスクになる制約は、README への記載のみとする（設計どおり直接指定 AMI への配慮はしない）。
  3. 5_5_3: `windows-user-setup.ps1` でユーザー作成後に `net user $User /logonpasswordchg:yes` を実行する。NLA が既定で有効なため変更画面が出ない場合は、NLA 無効化か別方式かをユーザーに相談してから決める。
  4. UserData に初期パスワードが平文で残る件は、初回変更の強制で失効するため**当面許容し、SSM 格納には変えない**。
  5. alphaexapi への受け渡し: README の手順に `validate-template` での検証を追加する。テンプレートのコピーは alphaexapi のセッションに `SendMessage` で依頼し、alphaexapi の PR で行う。
- **確認（検証）**: staging（570024666076）でこちらが行う。

## 2026-10-30 staging での検証結果と windows-user-setup.ps1 の既存不具合

- **検証（staging 570024666076、テストスタック `cdktest-553-win` / `cdktest-554-lin`）**:
  - テンプレート修正（PR #18）: `validate-template` 成功。Linux / Windows とも、指定しなければ Launch Template の OS 別 SG・研修用インスタンスプロファイルを継承することを確認した。
  - 5_5_4: `ImageIdParam=ami-033faed40fe9ebd86` を指定すると、Launch Template の AMI（ami-03107d83a97af3820）が上書きされることを確認した（Linux）。`cdktest-554-lin` は削除済み。
  - 5_5_3: Windows Server 2022 Japanese（ami-03615e54111d296c0）で UserData は実行されたが、ユーザーが作成されなかった（下記 1）。修正版の処理を SSM Run Command で手動実行すると、ユーザー作成・Administrators への追加・`PasswordExpired=1`（次回ログオン時に変更が必須）を確認できた。NLA は有効（`UserAuthentication=1`）。リモートデスクトップでの変更画面の確認は GUI が必要なため、ユーザーに依頼中。`cdktest-553-win` は確認後に削除する。
- **windows-user-setup.ps1 の既存不具合（EC2Launch の err.tmp で確認）**:
  1. `Get-LocalUser` が非終了エラーのため `catch` に入らず、`New-LocalUser` が実行されない → **ユーザーが作成されない**。5_5_3 の前提なので修正が必要（`-ErrorAction Stop` を付ける）。
  2. Windows Server 2022 の AMI に `aws` CLI が無く、SSH 公開鍵を SSM に保存できない（Linux 側の鍵連携が機能しない）。
  3. `Restart-Service TermService` が失敗する（ポートが既定の 3389 以外のとき、変更が反映されない）。
  4. EC2Launch が BOM なしで書き出したスクリプトを PowerShell 5.1 が CP932 として読むため、日本語のコメントが文字化けする（今はコメントだけなので実害なし）。
- **次のアクション**: 1 を PR B で直すか、2〜4 を今直すか先送りするかを、ユーザーに確認中。

## 2026-10-30 キーペアの仕組みの確認と、不要な秘密鍵（SSM）2 件の削除を決定

- **経緯**: ユーザーから「キーペアはどのように作成され、どのように入手できるのか」「SSM の 4 つの鍵はどのキーに対応しているか」と質問があり、staging（570024666076）を実確認した。
- **キーの仕組み（2 種類）**:
  1. **EC2 キーペア（管理者用・全インスタンス共通）**: KeyPairsStack が `linux-admin`（ED25519、ec2-user の SSH 用）と `windows-admin`（RSA、Administrator の初期パスワード復号用）を作成する。秘密鍵は AWS が `/ec2/keypair/<キーID>`（SecureString）に自動保存する。Launch Template に組み込み済み。アプリ（alphaexapi / alphasys）は鍵を扱わず、管理者が `aws ssm get-parameter --with-decryption` で手動で取得する。
  2. **研修ユーザー用 SSH キー（Windows → Linux）**: Windows の UserData が鍵を生成し、公開鍵を `/ssh-keys/<ID>/public-key` に保存し、同じ ID の Linux の UserData が `authorized_keys` に追加する設計。**現状は機能していない**（Windows: AMI に `aws` CLI が無く保存に失敗。Linux: UserData は `LinuxUserSshPublicKeyParam` が空でないときだけ実行されるが、alphaexapi がこのパラメータを渡していないため一度も実行されない）。staging の `/ssh-keys/` は 0 件。
- **SSM の 4 つの鍵の対応**:
  - `key-0309227bf4a32e7f6`（2026-08-01、ED25519）= 現行 `linux-admin`（確定）
  - `key-093271f78febca7a4`（2026-08-01、RSA）= 現行 `windows-admin`（確定）
  - `key-07db9a4365ec2d2ce`（2026-03-02、ED25519）/ `key-028483426f9a0f777`（2026-03-02、RSA）= 旧 `linux-admin` / 旧 `windows-admin` と推定。キーペアは存在せず、使っているインスタンスも無い。7/31〜8/1 のスタック削除・再作成でパラメータだけが残ったとみられる。
- **決定（ユーザー指示「不要な鍵を削除お願いします」）**: 旧 2 件（`/ec2/keypair/key-07db9a4365ec2d2ce`、`/ec2/keypair/key-028483426f9a0f777`）を削除する。現行 2 件は残す。
  - Claude Code の自動許可の判定で `aws ssm delete-parameters` が拒否されたため、ユーザー自身が実行するか、確認ダイアログでの許可を得てこちらが実行する（未実施）。
- **未決**: ②（研修ユーザー用 SSH キー）を今後も使うかどうか。使う場合は、Windows 側（不具合 2）と alphaexapi のパラメータ受け渡しの両方を直す必要がある。

## 2026-10-30 windows-user-setup.ps1 の既存不具合の対応方針と、研修ユーザー用 SSH キーの継続利用を決定

- **決定（ユーザー回答）**:
  1. ユーザーが作成されない不具合（`Get-LocalUser` が `catch` に入らない）は、**PR B（5_5_3 / 5_5_4）で修正する**。
  2. 残りの不具合（SSH 公開鍵を SSM に保存できない、`Restart-Service TermService` の失敗、日本語コメントの文字化け）も**今回修正する**。**研修ユーザー用 SSH キー（Windows → Linux）の仕組みは今後も使う**。
  3. 検証用インスタンス `client-cdktest553`（staging）でのリモートデスクトップのパスワード変更画面の確認は、**ユーザーが行う**。確認後にテストスタック `cdktest-553-win` を削除する。
- **研修ユーザー用 SSH キーの Linux 側の方式（ユーザー選択）**:
  - Linux（`server-<ID>`）の UserData は、`LinuxUserSshPublicKeyParam` に関係なく**Linux なら常に実行する**（alphacdk だけで完結し、alphaexapi の変更は不要。パラメータは互換のため残す）。
  - 公開鍵は起動時の 1 回だけでなく、**systemd タイマーで定期的に SSM から取り込む**（Windows を後から作った場合や、作り直して鍵が変わった場合にも反映する）。
- **検証で追加で判明したこと**: Windows の UserData がユーザーの初回ログオン前に `C:\Users\<ユーザー>\.ssh` を作るが、プロファイルとして登録されていない（ProfileList に無い）。初回ログオン時に別フォルダー（`<ユーザー>.<コンピューター名>`）が作られ、鍵が見えなくなるおそれがあるため、鍵の生成前にプロファイルを作成する。AWS Tools for PowerShell（`Write-SSMParameter`）は AMI に入っている。

## 2026-10-30 PR ＃21（5_5_3 / 5_5_4 と UserData 修正）の staging 検証結果と、ネットワークの問題 2 件

- **PR**: #18（パラメータ既定値の修正）はマージ済み。#21（5_5_3 / 5_5_4、windows-user-setup.ps1 の不具合修正、Linux の SSH キーを定期的に取り込む）を Draft で作成。
- **検証（staging、`cdktest-555-lin` → `cdktest-555-win` の順に作成）**: Windows ではユーザーの作成、Administrators への追加、`PasswordExpired=1`、プロファイル登録（`C:\Users\cdktest555`）、秘密鍵の ACL（ユーザー・SYSTEM・Administrators のみ）、SSM への公開鍵の保存を確認し、UserData のエラーは無かった。Linux は Windows の作成後にタイマーが公開鍵を自動で取り込み、フィンガープリントの一致を確認した。
- **新たに判明したネットワークの問題（ユーザーに判断を依頼中）**:
  - A. Linux の SG は 22 番を EIC エンドポイントの SG からしか許可しておらず、研修用の Windows から Linux へ SSH できない（`Test-NetConnection` で失敗）。案: NetworkStack で、Linux の SG に Windows の SG からの 22 番を許可する。
  - B. SG と EIC のトンネルは RDP を **3381** だけ許可しているが、テンプレートの `WindowsRdpPortParam` の既定は **3389** で、alphaexapi も渡していない。案: テンプレートの既定を 3381 にする。
- **残っている検証用スタック**: `cdktest-553-win`（古いテンプレート、削除してよいか確認中）、`cdktest-555-win` / `cdktest-555-lin`（リモートデスクトップの確認用）。

## 2026-10-30 ネットワークの問題 2 件の対応を承認、リモートデスクトップの接続方法を確認

- **決定（ユーザー「OK」）**:
  - A. NetworkStack で、Linux の SG に **Windows の SG からの 22 番（SSH）を許可**する（研修用 Windows → Linux の SSH キーの仕組みを使えるようにする）。
  - B. テンプレートの **`WindowsRdpPortParam` の既定値を 3389 → 3381** にする（SG・EIC のトンネルの設計に合わせる。alphaexapi の変更は不要）。
- **リモートデスクトップの接続方法（ユーザー回答）**:
  1. SSM プラグイン（Session Manager のポートフォワード）。
  2. 社内ネットワークと仮想プライベートゲートウェイで接続済みの AWS VPC に VPC ピアリングし、社内からプライベート IP で直接接続する。
  3. Tailscale をインストールする。
- **補足（ユーザー）**: 上記のうち SSM プラグイン・Tailscale は現行の方法で、**本番環境では VPC ピアリングで社内から直接接続する予定**。
  - → 本番で VPC ピアリングを使う場合、Windows の SG に社内の IP 範囲（CIDR）からの 3381 番の許可が必要になる（現状は EIC の SG からのみ）。staging には VPC ピアリング・仮想プライベートゲートウェイとも無い（2026-10-30 確認）。本番の構築時に対応する（未着手）。
- **A / B の実施（PR #21 に追加）**: NetworkStack を staging にデプロイ済み（差分は Linux SG への ingress 1 件の追加のみ）。研修用 Windows（cdktest555）から Linux へ、Windows が生成した鍵で SSH ログインできることを確認した。B（RDP の既定ポート 3381）は検証中。

## 2026-10-30 RDP ポートを 3389 に統一（B の方針変更）

- **経緯**: B（RDP の既定ポートを 3381 に合わせる）の検証で、EIC のトンネルを 3381 に張ろうとすると `The specified RemotePort is not valid. Specify either 22 or 3389` となり、**EC2 Instance Connect エンドポイントは 22 / 3389 しか使えない**ことが判明した。SG・EIC の IAM ポリシーの 3381 は、もともと EIC では機能しない設定だった（EIC 経由の RDP はこれまでも使えなかった）。B の根拠（EIC に合わせる）は誤りだった。
- **決定（ユーザー選択）**: **3389 に戻す**。テンプレートの `WindowsRdpPortParam` の既定は 3389 のまま（PR #21 の 3381 への変更は取り消す）。NetworkStack の Windows SG・EIC SG の egress・EIC の IAM ポリシーを 3381 → 3389 に変更し、EIC 経由の RDP も使えるようにする。
- 参考: 3381 の検証（cdktest556）では、RDP が 3381 で待ち受け、TermService の再起動が再起動なしで成功し、ファイアウォールのルールも作成されていた（ポート変更時の UserData の処理は正しく動く）。

## 2026-10-30 検証用スタック・古い秘密鍵の削除と、alphaexapi へのテンプレート取り込み依頼

- **PR**: #23（RDP ポートを 3389 に統一。#21 のマージ後にプッシュして取り込まれなかった 2 コミットを作り直したもの）をユーザーがマージ。
- **実施（ユーザー指示）**:
  - 検証用スタック `cdktest-553-win`（古いテンプレート）・`cdktest-556-win`（3381 の確認用）を削除した。`cdktest-555-win` / `cdktest-555-lin` は、ユーザーがリモートデスクトップで変更画面を確認した後に削除する。
  - 古い秘密鍵の SSM パラメータ `/ec2/keypair/key-07db9a4365ec2d2ce`・`/ec2/keypair/key-028483426f9a0f777` を削除した（キーペアが存在しないことを確認のうえ）。残りは現行の `linux-admin`・`windows-admin` の 2 件。
  - alphaexapi のセッション（alphaexapi-d2）に `SendMessage` で、`cdk.template/Ec2NativeTemplateStack.template.json` の差し替えを依頼した。依頼内容: 生成・検証手順、`ImageIdParam`（AllowedPattern `^(ami-[0-9a-f]{8,17})?$`）、5_5_3 のユーザー作成、SG・インスタンスプロファイルは Launch Template から継承、`WindowsRdpPortParam` は 3389 のまま、`LinuxUserSshPublicKeyParam` は不要、ManagedBy タグが alphasys → alphacmc に変わること。
- **残り**: リモートデスクトップでの初回ログイン時のパスワード変更画面の確認（ユーザー）、`cdktest-555-*` の削除、本番での VPC ピアリング時の Windows SG への社内 CIDR の許可（本番構築時）、alphaexapi の取り込み結果の確認。
- **alphaexapi の返信（2026-10-30）**: 依頼を受領し、着手はユーザーの承認待ち。ManagedBy タグでは検索しておらず（`tag:Name` のみ）、タグの変更は影響なし。依頼内容は alphaexapi の `docs/conversations/2026-10-30.md`（PR #189）に記録済み。着手後に PR のリンクと結果を連絡してもらう。
- **リモートデスクトップでの確認結果（ユーザー、2026-10-30）**: `client-cdktest555` に SSM のポートフォワード経由で接続したところ、「最初にログオンする前にパスワードを変更する必要があります」（エラーコード 0x1207）となり、**変更画面は出なかった**。NLA（ネットワークレベル認証）が有効なため。対応方式（A: 初回変更までだけ NLA を無効にする / B: NLA を常に無効にする / C: NLA を残して変更の強制をやめる）をユーザーに確認中。
- **決定（ユーザー「A でお願いします」）**: **A. 初回のパスワード変更までだけ NLA を無効にする**。UserData で NLA を無効にし、ユーザーの初回ログオン時に動くタスク（SYSTEM）が NLA を有効に戻して自分自身を削除する。実装の前に、検証用インスタンス `client-cdktest555` の NLA を SSM Run Command で手作業で無効にし、変更画面が出るかをユーザーが確認する。
- **手作業の確認（2026-10-30）**: SSM Run Command で `client-cdktest555` の `UserAuthentication` を 1 → 0（NLA 無効）にしても、Windows 標準のリモートデスクトップ接続では**同じエラー（0x1207）**になった。サーバーが NLA を必須にしなくても、クライアントが CredSSP（事前認証）を使うため。次に、クライアント側で `.rdp` ファイルに `enablecredsspsupport:i:0` を指定して確認する（ユーザー確認中）。この方法で変更画面が出る場合、方式 A の実装では「研修生が初回だけこの .rdp を使う」か「サーバー側で初回変更まで CredSSP を提供しない（`SecurityLayer=0` など）」かを決める必要がある。
- **`.rdp` での確認結果（ユーザー、2026-10-31）**: `enablecredsspsupport:i:0`（CredSSP を使わない）を指定した `.rdp` ファイルで接続したところ、**パスワードの変更画面が出て、新しいパスワードでログインできた**。ログイン後、Windows の PowerShell から `ssh ec2-user@10.50.2.179` で Linux に入れた（研修ユーザー用 SSH キーの仕組みを実機で確認）。これで、初回の変更画面を出すには「クライアントが CredSSP を使わない」ことが必要だと分かった。方式 A の実装方法（クライアント側の `.rdp` か、サーバー側で初回変更まで CredSSP を提供しないか）はユーザーに確認中。
- **サーバー側の手作業確認（ユーザー、2026-10-31）**: `client-cdktest555` で、管理者の PowerShell から `net user cdktest555 /logonpasswordchg:yes`（変更必須に戻す）と `SecurityLayer=0`（CredSSP を受け付けない RDP 方式）を設定した（`UserAuthentication=0` のまま）。普段どおりの「リモートデスクトップ接続」（.rdp ファイルなし）で接続したところ、**パスワードの変更画面が出た**。TermService の再起動は不要だった。サーバー側の方式（②）で実現できる見込み。実装方法はユーザーに提示し、承認待ち。
- **alphasystem からの照会への回答（2026-11-01）**: alphasystem-4e から「NLA を無効にしただけで、標準の接続でも変更画面が出た（ユーザー確認 11/01）。10/30 の記録と食い違うので、再現を確認してほしい」と照会があった。SSM Run Command で `client-cdktest555` を読み取ると `UserAuthentication=0`・`SecurityLayer=0` で、10/31 に設定した `SecurityLayer=0` が残っていた。そのため食い違いではなく、条件は「NLA の無効化と `SecurityLayer=0` の両方」だと回答した（NLA を無効にしただけでは 0x1207 になる。10/30 に確認済み）。方式 A の実装案（② のサーバー側の方式）は、ユーザーの承認待ちであることも伝えた。
- **alphasystem の返信（2026-11-01）**: alphasystem 側の記録（`docs/conversations/2026-11-01.md`）で、「NLA を無効にするだけで済む」という見立てを訂正してもらった。設計ドキュメント（5_5_3）への反映は、方式 A の実装案がユーザーに承認され、staging で確認できてから行う。もう一度確かめるかどうかは、alphacdk 側でユーザーに確認する。
- **決定（ユーザー、2026-11-01）**: ② のサーバー側の方式で実装することを承認された。`userdata/windows-user-setup.ps1` だけを変更する。UserData で `SecurityLayer`・`UserAuthentication` の元の値を読み取ってから両方を 0 にし、研修ユーザーのログオン時に動くスケジュールタスク（SYSTEM）が元の値に戻して自分自身を削除する。「NLA を無効にしただけ」の条件の再確認は**不要**とした（10/30 に 0x1207 になることを確認済みのため）。staging での確認手順: 新しい検証用スタックを作る → 普段どおりのリモートデスクトップ接続で変更画面が出る → ログオン後に設定が元に戻り、タスクが消えていることを SSM で確認する → 2 回目は NLA ありで接続できる → `cdktest-555-*` と検証用スタックを削除する。
- **実装と staging での確認（2026-11-01、途中）**: `userdata/windows-user-setup.ps1` に、初回ログオンまで `SecurityLayer=0`・`UserAuthentication=0` にする処理と、元の値に戻すタスク `RestoreRdpSecurity` の登録を追加した。検証用スタック `cdktest-557-win`（`i-073183e182f499fa8`、ユーザー `cdktest557`）を作成し、SSM で次を確認した: `SecurityLayer=0`・`UserAuthentication=0`、タスクの起動条件は `cdktest557` のログオン時、戻す値は元の `SecurityLayer=2`・`UserAuthentication=1`、`/ssh-keys/cdktest557/public-key` を保存済み。残りの確認: 普段どおりの接続で変更画面が出るか、警告が出るか、2 回目の接続（ユーザー）→ 設定が元に戻り、タスクが消えたか（SSM）→ `cdktest-555-*`・`cdktest-557-win`・`/ssh-keys/cdktest555`・`/ssh-keys/cdktest557`・パスワードファイルを削除する。
- **staging での確認完了（2026-11-01）**: ユーザーが `cdktest557` で、普段どおりのリモートデスクトップ接続（.rdp なし）で確認した。変更画面が出て変更後にログインでき、サインアウト後の 2 回目の接続もできた。SSM で、ログオン後に `SecurityLayer=2`・`UserAuthentication=1` に戻り、タスク `RestoreRdpSecurity` が消えたことを確認した（パスワードの変更は 11:57）。5_5_3 は完了。
- **後片付け（2026-11-01）**: 検証用スタック `cdktest-557-win`・`cdktest-555-win`・`cdktest-555-lin`、SSM パラメータ `/ssh-keys/cdktest555`・`/ssh-keys/cdktest556`・`/ssh-keys/cdktest557`（`/public-key`）、手元のパスワードファイル（cdktest553/555/556/557）と検証用の .rdp ファイルを削除した。
- **連絡（2026-11-01 送信）**: alphasystem（alphasystem-73）に、5_5_3 の方式と確認結果を伝え、設計ドキュメントへの反映を依頼した。alphaexapi（alphaexapi-63）に、PR #27 のマージ後に `Ec2NativeTemplateStack.template.json` をもう一度取り込むよう依頼した（変わったのは Windows の UserData だけで、パラメータは 10/30 の依頼から変わっていない。生成・検証手順は前回と同じ）。返信待ち。
- **alphaexapi の返信（2026-11-01）**: 依頼を受領した。PR #27 のマージ後、10/30 の差し替え依頼（ImageIdParam など）と合わせて 1 回で取り込む。着手はユーザーの承認待ち。取り込み後に PR のリンクと結果が連絡される。
- **PR #27 マージ（ユーザー、2026-11-01）**: staging のマージコミットは `1eb4c61`。alphaexapi に、テンプレートの取り込みを始められることを連絡した（着手は alphaexapi 側でユーザーが承認してから）。取り込み結果の連絡待ち。
- **alphaexapi の取り込み完了（2026-11-01）**: alphaexapi の Draft PR #192（https://github.com/alphacmc/alphaexapi/pull/192）。生成元は alphacdk の staging `004498f`。`1eb4c61` からの差は conversations.md だけで、テンプレートへの影響はない。validate-template は通った。旧版とのパラメータの差は `ImageIdParam` の追加だけで、`RestoreRdpSecurity` と `ManagedBy=alphacmc` が入っていることも確認済み。alphaexapi のコードは、SG のコメントを「Launch Template から継承」に直しただけで、jest 25 件はすべて成功。10/30 の依頼もこの PR で取り込み済み。`ImageIdParam` を渡す処理（5_5_4）は alphaexapi の次の PR で入れる（`^ami-[0-9a-f]{8,17}$`、DescribeImages で存在して使える状態かを確認する）。staging での実機確認は、マージとデプロイの後に alphaexapi が行う。
