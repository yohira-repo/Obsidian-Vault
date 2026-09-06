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
