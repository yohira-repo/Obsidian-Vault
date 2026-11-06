# coop 作業ログ

## 2026-09-24 全体状況確認・データマスキング課題の確認

### 状況

- 現時点で、coop配下全プロジェクト（coopinf/coopcdeweb/coopcdebatch/coopcdeinput/coopcdealert/coopbatch/coops3view）に緊急の懸案事項はなし。
- 継続課題: データのマスキング
  - `support/stgenv_test_procedure.md` の「対象データのマスキング」節（検討中・枠のみ確保の状態）に対応する課題。
  - STG環境試験でDBバックアップ・CSV等の本番由来データを使う際のマスキング方式が未確定のまま。

## 2026-09-24 データマスキング対応のタスク化に着手

### 決定事項

- ユーザーより、データマスキング課題について以下のスコープで課題化・タスク化まで進める指示あり。
  1. DBの個人情報項目の洗い出し
  2. CSVの個人情報項目の洗い出し
  3. マスキングを行うタイミングの検討
  4. 既存ツールを使うか、独自に作成するかの検討
  5. 上記を課題化・タスク化するところまで実施
- 対応として、coopinf（DBスキーマ・マイグレーション）とcoopcdebatch/coopbatch（CSVフォーマット・取り込み処理）を対象に、個人情報項目と既存対応状況（重複作業防止のため）を横断調査するリサーチエージェントを起動（バックグラウンド実行中、結果待ち）。

## 2026-09-24 データマスキング課題のタスク化方針を決定

### 決定事項

- 調査結果（DB/CSVの個人情報項目一覧、既存対応なしの確認）を踏まえ、タスク化の方針についてユーザーに確認し、以下で決定。
  1. タスクの記録先: GitHub Issueではなく、**マークダウン文書**（`coop/support/data_masking_tasks.md`）とする。
  2. マスキング対象範囲: DB・CSVのみとし、副次的に見つかった **ログ出力（coopcdebatch等のエラー時に組合員番号・契約番号が平文出力される問題）は今回のスコープに含めない**。別課題として切り出し、フォローアップ扱いとする。
- 上記方針に基づき `coop/support/data_masking_tasks.md` を作成し、Task 1〜6（対象項目確定→粒度決定→タイミング決定→方式選定→実装→手順書反映）に分解済み。Task 4（既存ツール利用 or 自作）の候補調査はまだ未着手。

## 2026-09-24 データマスキング Task1・Task2 を決定

### 決定事項

- **Task 1（対象個人情報項目の確定）**
  - `admin_user`テーブル、`input_backup`テーブルはマスキング対象外とする。
  - 契約番号・組合員番号（識別子項目）もマスキング対象外とする。
  - 結果、マスキング対象は `contract`テーブルの氏名・カナ・住所・郵便番号・電話番号、および CSV(AGREEMENT)の契約名義・カナ・住所・電話番号に確定。
- **Task 2（マスキング粒度）**
  - 部分マスクではなく **完全マスク**（固定値/ダミー値への置換）を採用する。
- `coop/support/data_masking_tasks.md` に反映済み。残タスクはTask 3（タイミング決定）・Task 4（既存ツール利用 or 自作）。

## 2026-09-24 データマスキング対応、本日はここで区切りと決定

### 決定事項

- Task 4の既存ツール調査を実施。PostgreSQL AnonymizerはAmazon RDS/Aurora未サポートのため不可、Greenmask/AWS DMSは機能過多・導入コスト大と判明。自作（`restore-stg-db.sh`へのUPDATE文追加、CSV用軽量スクリプト）を推奨候補として提示したが、**最終決定はまだ行わず次回に持ち越し**とユーザーが明示。
- ユーザーより「本日はここまでとします」と指示があり、Task 4の最終決定・Task 5（実装）・Task 6（手順書反映）は**未着手のまま次回に継続**することが確定。
- ドキュメント（`conversations.md`, `support/data_masking_tasks.md`）をブランチ`feature/data-masking-tasks`にコミットし、Draft PRを作成済み: https://github.com/alphacmc/coop/pull/8

## 2026-09-24 データマスキングTask2「固定値/ダミー値」の認識合わせ

### 決定事項

- ユーザーより、Task 2で決定した「完全マスク（固定値/ダミー値）」について、**全レコードを`***`や`9999`のような同一値で埋める意味ではない**との明示的な指摘・方針明確化あり。
- 確認の結果、ダミー値の内容は以下の優先順位で決定:
  1. 第一希望: **行ごとに実在しそうな生成ダミーデータ**（Faker等による、氏名・住所・電話番号としてそれらしい値）。
  2. 作成コストが高い場合の妥協案: **行ごとに一意な連番ベースのダミー値**（同一値の使い回しは避ける）。
- これを受け、Task 4の推奨をGreenmask比較の上「自作 + `@faker-js/faker`」に更新（`support/data_masking_tasks.md`に反映済み）。最終決定はまだ次回持ち越し。

## 2026-10-17 セキュリティ監査の対象リポジトリを決定

### 決定事項

- 「最近セキュリティ事故が多数報告されている」ことを受け、インフラ・アプリのセキュリティ上の問題点を洗い出す監査を実施することになった。
- 監査対象はユーザー指示により **coopinf / coopcdeweb / coopcdealert / coopbatch の4リポジトリのみ**とし、**coopcdebatch（廃止予定）・coops3view は今回の対象外**とする。
- 読み取り専用の監査エージェントを4リポジトリ並行で起動（結果待ち）。指摘事項の修正は、方式案を提示しユーザー了解を得てから着手する（既存ルールどおり）。
- 監査完了（同日）。統合レポートを `support/security_audit_2026-10-17.md` に保存（未コミット）。High 指摘は全件、該当行を直接確認済み。修正は方針同意待ちで未着手。推奨着手順は「認証情報のローテーション（coopinf SFTP鍵・DBパスワード）」→「coopcdeweb の認可欠陥3件」→「stg の露出対策」→「個人情報のログ・通知経路」。
- ユーザー要望で High 指摘の実リスク再評価・対応可否を検討し、同レポート末尾「High 指摘の実リスク再評価と対応可否」に追記。再評価の要点: SFTP鍵漏えい・未認証API・stg露出は High 維持、旧DB接続文字列と coopcdealert の脆弱依存は引き下げ。着手順の提案（即日無影響の WAF/IP制限/ファイル削除 → ecubenet へ鍵ローテーション依頼 → コード修正）を提示し、ユーザーの判断待ち。未確認事項: stg を社外に見せる運用の有無、general 権限ユーザーの実在、SFTP のソース IP 制限の有無。

## 2026-10-17 SFTP 鍵: 定期ローテーションの仕組み化を方針として決定

### 決定事項

- ユーザーより、coopinf の SFTP 鍵・パスフレーズの Git 平文記載について「**Git 平文は過去のもの**」との見解。ただし「**ローテーションを定期的に実施する仕組みを作りたい**」と方針提示あり。
- これを受け、半自動ローテーション構成を提案: EventBridge Scheduler による期限監視通知 → `rotate-sftp-key.sh` で新鍵生成と Secrets Manager の保留バージョン登録 → ecubenet へ公開鍵登録依頼（人手） → coopbatch の `SFTP_CHECK_ONLY` で疎通確認 → 現行バージョンへ昇格、旧鍵は前バージョンとして保持しロールバック可能。設計の採否・ローテーション周期・ecubenet への確認事項（公開鍵 2 本同時登録の可否、登録窓口と所要日数）はユーザー判断待ち。
- Aurora マスターパスワードの標準ローテーション有効化は別件として提示（未決）。
- ローテーション済みかの確認（Secrets Manager の鍵指紋とテンプレートの鍵指紋の突き合わせ）は、シークレット値取得が権限制御でブロックされ**未実施**。
- 「未認証 API」「stg の露出」はユーザーから意味不明との指摘があり、平易な説明を提示。stg については初回報告の「認証スタブで誰でもログインできる」は誤り（スタブルートは 2023-09 から無効）と訂正し、実際の危険は「ログイン不要の URL で stg 内の本番実データが取得できる」点であると説明。対応方針は未決。

## 2026-10-17 coopcdeweb: ブラウザ→バックエンド直接呼び出し構成の是正方針

### 経緯

- 調査の結果、管理画面（`/web/admin/*`）はブラウザから ALB・WAF 経由で NestJS バックエンド（`/api/admin/*`、`/api/admin-auth/*`、`/api/members/getBillInfoByAdmin/*` の計 16 ルート）を直接呼んでいることを確認。Next.js の API ルート（`pages/api/*`）は `basePath: /web` のため `/web/api/*` であり、該当ハンドラは存在しない。組合員向け画面はサーバー側から localhost 経由で呼んでおりブラウザ露出なし。
- 「WAF で /api 配下を全ブロックできるか」との質問に対し、上記 3 系統を除く反転ルール案を提示（監査レポートに追記済み）。

### 決定事項

- ユーザーより「**作りが悪い。全てルートハンドラで受けた上でバックエンドに回すべき**」との方針表明。バックエンドをインターネットに直接さらさない構成へ是正する方向で合意。
- 実現方法として 2 案を提示し、**採否は未決**:
  - 案 A（推奨）: `next.config.js` の rewrites で `/web/api/backend/:path*` → `http://localhost:3001/api/:path*` にサーバー側プロキシし、ブラウザ用 URL の環境変数を差し替え、ALB の `/api/*` ルールを削除。呼び出しコード無改修、半日程度。
  - 案 B: `pages/api/admin/*` 等にルートハンドラ 16 本を実装し、セッション確認・ロール判定をフロント側で行ってからバックエンドを呼ぶ。数日規模。
- 注意点として共有: 経路を閉じてもバックエンドの認可欠陥（ロール判定なし、`change-pass-inlogin` の他人パスワード変更）は残るため、RolesGuard と `req.user` ベースの修正は別途必要。

## 2026-10-17 方針変更: BFF 化は見送り、最小修正で対応

### 決定事項

- ユーザーより「理想は BFF 化だが、**リリース後 3 年経過しており新リリース後の NG が許されない**ため、少し検討したい。**最小修正案で最も効果的な提案**を」との方針変更。案 A / 案 B（BFF 化）は当面見送り。
- 提案した最小修正案（監査レポート「最小修正・最大効果の提案」に記載、**採否は未決**）:
  - 原則: アプリのコード・デプロイに触らない。WAF ルールは Count モードで投入し、WAF ログ（365 日保持）で誤検知なしを確認してから Block。戻しは Count への 1 行変更で即時。
  - Step 1（coopinf のみ）: WAF を「`/api/` 配下は原則 Block、`/api/admin/`・`/api/admin-auth/`・`/api/members/getBillInfoByAdmin/` のみ許可」に反転、LOWERCASE 変換併用、stg・prd 両方。Count 1 週間 → Block。
  - Step 2（coopinf のみ）: WAF ログから管理画面の正規アクセス元 IP を抽出し IPSet 許可リスト化。`/web/admin/*` と上記 3 系統を IPSet 外から Block。Count → Block。
  - Step 3（任意・後回し可）: IpGuard の localhost 限定有効化（`::ffff:127.0.0.1` を含める、stg 実機確認必須）。
  - 今回やらない: BFF 化、Express の case sensitive routing、RolesGuard 等のアプリ側認可修正（Step 2 で社外からの悪用を遮断した上で別途計画）。

## 2026-10-17 Step 1 着手の go サイン / stg 環境の DB クリア・サービス停止の要望

### 決定事項

- ユーザーより「**Step 1 から対応したい**」と go サイン。coopinf に `feature/waf-api-allowlist-count` を作成し、`cf/waf-cf.yaml` に `ApiAllowList` ルール（Priority 10、`ApiAllowListAction` パラメータ、既定 Count）を追加。Draft PR 作成済み: https://github.com/alphacmc/coopinf/pull/42
  - 事前確認: validate-template OK。stg / prd の変更セットをプレビュー（実行せず削除）。prd は `WebACL.Rules` のみ変更。stg はデプロイ済みテンプレートが古く `WhitelistPathPatternSet` の差分も反映されるが、参照する `PathBlock` ルールは prd 専用のため stg の通信に影響なし。
  - デプロイ段取り（PR 本文に記載）: stg に Count → prd に Count → 1 週間観察（CountedRequests メトリクスと WAF ログ）→ 問題なければ Block に切替（stg → prd）。切り戻しは Count で再デプロイ。デプロイとマージはユーザーが実施。
  - 作業時に coopinf のマージ済みローカルブランチ 5 本を削除（恒常ルール）。
  - **PR #42 はユーザーがマージ済み（2026-10-17）**。「まずステージング環境で試したい」との指示で、同日 15:30 JST に `waf-stg-stack` へ `ApiAllowListAction=Count` でデプロイ（UPDATE_COMPLETE）。prd へのデプロイは未実施（stg の観察結果を見てから判断）。
  - stg 検証結果: WebACL に `coopcde-stg-ApiAllowList`（Priority 10、Count）を確認。疎通テスト（ダミー組合員番号 0000000000）で `/api/admin-auth/csrf` 200、`/api/members/getBillInfoByMember/...` 200、大文字混じり `/api/Members/GetBillInfoByMember/...` 200（Count のため通過、かつ Express の非区別を実機で確認）、`/api/admin/../members/...` は既存のマネージドルールで 403。CloudWatch `CountedRequests` = 2、サンプルリクエストに COUNT 記録あり。ダミー番号の応答本文は空データで個人情報なし。
  - 次の段取り（ユーザー指示で観察期間を短縮）: **stg の観察は半日で可**。ユーザーが stg の管理画面をしばらく操作する → その後 Claude が WAF ログ・`CountedRequests` を集計し、正規操作が `ApiAllowList` に当たっていないことを確認 → 問題なければ stg を Block に切替 → 管理画面の動作確認 → prd に Count でデプロイ → 同様に観察 → Block。
  - **stg 観察完了（2026-10-17 15:45 JST）**: ユーザーが管理画面を一通り操作（ログイン、会員検索、会員詳細、ユーザー一覧と作成・更新・削除、アクセス履歴、パスワード変更、ログアウト）。WAF ログ集計の結果、`ApiAllowList` のヒットは 3 件で全て Claude のテスト（ダミー番号、同一 IP）。ユーザー操作分 99 リクエストはヒットなし → 許可 3 プレフィックスの網羅を確認。
  - **prd へ Count でデプロイ（2026-10-17 15:45 JST）**: ユーザー指示「同じ設定を prd でも」を受け、`waf-prd-stack` に `ApiAllowListAction=Count` でデプロイ（UPDATE_COMPLETE）。既存 `PathBlock`（Priority 9、Block）は変更なし、`ApiAllowList` は Priority 10、Count。
  - prd 疎通テスト（ダミー番号）: `/api/admin-auth/csrf` 200、`/api/members/getBillInfoByMember/...` 403（既存 PathBlock）、**`/api/Members/GetBillInfoByMember/...` 200** → 大文字混じりによる WAF 迂回が prd でも成立することを実機で確定（応答は空データ）。`ApiAllowList` の CountedRequests=1（迂回リクエスト分）。Block 切替でこの迂回が塞がる。
  - ユーザー発見の不具合 2 件（ユーザー削除後に一覧が更新されない／パスワード変更後に画面が留まる）を `support/coopcdeweb_issues.md` に課題として登録。原因箇所と修正案を記載、未着手。
  - **stg を Block に切替（2026-10-17 15:55 JST、ユーザー指示）**: `waf-stg-stack` を `ApiAllowListAction=Block` で再デプロイ（UPDATE_COMPLETE、ルール Action=Block を確認）。疎通テスト: `/web/admin/login` 200、`/api/admin-auth/csrf` 200、`/api/members/getBillInfoByMember/...` 403、大文字混じり `/api/Members/...` 403、`/api/certif/dummy` 403、`/api/sample` 403。stg の組合員 API 露出はこれで遮断済み。
  - **stg Block 後の動作確認完了（ユーザー、2026-10-17）**: 管理画面で同じ一通りの操作を行い問題なしと確認。続いて prd の試験（Count のまま）に着手。
  - **prd 試験完了（ユーザー、2026-10-17 16:00 JST）「問題なし」**。WAF ログ集計: `ApiAllowList` ヒットは 1 件のみ（Claude の迂回テスト、ダミー番号、同一 IP）。ユーザー試験分 99 リクエストはヒットなし。
  - **prd を Block に切替（2026-10-17 16:03 JST）**: `waf-prd-stack` を `ApiAllowListAction=Block` で再デプロイ（UPDATE_COMPLETE、ルール Action=Block を確認）。疎通テスト: `/web/admin/login` 200、`/api/admin-auth/csrf` 200、`/api/members/getBillInfoByMember/...` 403、大文字混じり `/api/Members/...` 403、`/api/certif/dummy` 403、`/api/sample` 403。**Step 1 は stg / prd とも完了**。prd の大文字小文字迂回も遮断済み。
  - **prd Block 後の動作確認完了（ユーザー、2026-10-17 16:10 JST）「問題なし」**。Step 1 は完全に完了。
  - **Step 2（管理画面の IP 制限）は保留**: お客様の意向次第のため数日待ち。お客様がテレワークの場合は IP フィルターが難しい可能性あり（代替案の検討余地: VPN 出口 IP、または IP 制限を諦めて Step 3 の IpGuard とアプリ側認可修正を優先）。
  - **stg DB クリア・サービス停止も保留**: 数日待ち。
  - **本日はここで区切り**（ユーザー指示）。coop リポジトリの変更（監査レポート、課題ファイル、conversations.md）をブランチ `feature/security-audit-2026-10-17` にコミットし Draft PR 作成済み: https://github.com/alphacmc/coop/pull/10
  - **管理画面の MFA 方針（2026-10-17、方向性のみ）**: ユーザー質問「パスワード認証のみは危険ではないか」→ 危険と回答し、A（WAF レート制限）/ B（ALB + Cognito MFA）/ C（アプリ側強化）を提示。ユーザーより「**Cognito はユーザー管理が二重になる。現在のアプリユーザー管理をベースに MFA を付加したい**」との意向 → **B（Cognito）は不採用方向**、代替として **B2（アプリ内 TOTP、`admin_user` に mfa 列追加、`MFA_REQUIRED` で段階適用）** を推奨案として提示（監査レポートに詳細記載）。採否はお客様確認（認証アプリを使えるか）待ち。A は B2 と併用可能として先行候補。
  - **A 案（ログイン API レート制限）を stg に導入（2026-10-17、ユーザー指示「stg に導入して確認したい」）**: coopinf `feature/waf-login-rate-limit` に `LoginRateLimit` ルール（Priority 11、RateBased、送信元 IP ごとに POST `/api/admin-auth/login` を 300 秒あたり 10 回、`LoginRateLimitAction` Count|Block）を追加。Draft PR: https://github.com/alphacmc/coopinf/pull/43
    - 20:5x JST: stg に Count で投入（`ApiAllowListAction=Block` は維持）。ダミー認証 15 回で送信元 IP が超過登録され、追加 3 回が COUNT 記録（CountedRequests=3）。
    - 21:04 JST: stg を **Block** に切替。超過中の送信元からのログイン POST は WAF の 403（BlockedRequests=12 以上）、同じ IP からの `/api/admin-auth/csrf` と `/web/admin/login` は 200（ログイン以外は影響なし）を確認。超過状態はレート低下後に自動解除。
    - **21:10 JST 障害: ユーザーが stg にログインできず**。原因: Claude のテスト送信はユーザーの Mac から出ており、ユーザーと同一の送信元 IP がレート超過として登録されたまま。ユーザーのログイン試行（21:07〜21:09）が `LoginRateLimit` で遮断され、遮断されたリクエストもレート集計に含まれるため再試行で解除が遠のいていた。**対処: 切り戻しプランどおり stg の `LoginRateLimitAction=Count` に戻し即時解除**。
    - 教訓: レート制限の動作確認は、利用者と異なる送信元 IP（別回線・モバイル等）から行うか、確認後に Count へ戻してから利用者確認に進む。Block 中の再試行は逆効果。
    - **21:12 JST: ユーザーが stg ログイン成功を確認** → 超過登録の解除を確認した上で stg の `LoginRateLimitAction` を **Block に復帰**（UPDATE_COMPLETE、テスト送信なし）。stg は `ApiAllowList`=Block、`LoginRateLimit`=Block で稼働中。
    - **coopinf PR #43 はユーザーがマージ済み。21:17 JST: prd に `LoginRateLimitAction=Count` で投入**（UPDATE_COMPLETE、`ApiAllowListAction=Block` 維持、Priority 11、10 回/300 秒）。`/web/admin/login`・`/api/admin-auth/csrf` は 200。
    - ユーザー質問「ログインできない申し出時にレート制限に掛かっているか調べる方法」→ 運用手順書 `support/waf_login_ratelimit_runbook.md` を作成（遮断中 IP の即時確認 `get-rate-based-statement-managed-keys`、WAF ログ検索、メトリクス、対処と Count への切り戻し）。
    - **prd 試験完了（ユーザー、21:21 JST）**。Count 期間の集計: CountedRequests=0、ログイン POST は 5 件（ユーザー IP 4 件 + 他 1 件、すべて ALLOW）、超過登録 IP なし。
    - **21:21 JST: prd を `LoginRateLimitAction=Block` に切替**（UPDATE_COMPLETE、テスト送信なし）。prd は PathBlock / ApiAllowList / LoginRateLimit の 3 ルールすべて Block。`/web/admin/login`・`/api/admin-auth/csrf` は 200。**A 案は stg / prd とも完了**。
    - 残: Step 2（IP 制限 or B2 の MFA）と stg DB クリアはお客様回答待ち。
  - **本日はここで区切り（2026-10-17 21:30 JST、ユーザー指示）**: 次の対応は MFA（B2 案）だが、お客様への説明が必要なため着手せず。coop の Draft PR #10 を本日分の最終内容に更新し、Draft 解除・マージはユーザーが実施。再開時はお客様の回答（MFA の可否、IP 制限の可否、stg DB の扱い）から。
  - **訂正（21:35 JST）**: PR #10 は 16:12 JST に既にマージ済みだった。その後に同ブランチへ push した 10 コミット（管理画面認証の強化案、A 案の実施記録、stg ログイン不可事故、運用手順書、区切り）は main 未反映だったため、ユーザー指摘を受けて main から `feature/security-audit-2026-10-17-followup` を切り直して載せ替え、**Draft PR #11 を作成**: https://github.com/alphacmc/coop/pull/11 。旧ローカルブランチは削除。push 前の PR 状態確認を怠った点は再発防止としてメモリに記録。社内 NAT で複数管理者が同一 IP の場合は閾値（10 回/5 分）の妥当性を Count 期間で確認。
  - 課題 3（ユーザー削除の論理削除・同一 ID 再登録不可）: ユーザーより「**お客様はユーザー ID に社員番号を使う予定で、復活・同一 ID 再登録は不要。選択肢 1（現状維持）で OK**」と決定。仕様確定、メッセージ改善のみ任意で未着手（`support/coopcdeweb_issues.md` に反映）。
  - ユーザーからの実装確認依頼「ユーザー削除は論理削除か。同じユーザーで再登録できない」→ 論理削除（`authority=deleted`）で、作成時の存在チェックが権限を問わないため再登録不可と確認。仕様判断事項として `support/coopcdeweb_issues.md` に課題 3 として登録（推奨: 現状維持 + メッセージ改善。選択肢 2: 削除済み ID の復活許可、3: 物理削除）。ユーザー判断待ち。
  - ユーザー要望で切り戻しプランを PR #42 本文に追記: A) Count 投入時のスタック更新失敗は自動ロールバック、B) Block 後の誤遮断は `ApiAllowListAction=Count` で再デプロイ（1〜3 分、第一選択）、C) 緊急時は WAF コンソールでルールの Action を Count に変更（30 秒、後で B で再同期）、D) ルール撤去はマージ前 main のテンプレートで再デプロイ、E) 最終手段は WebACL の ALB からの解除。切り戻し後は管理画面の動作と BlockedRequests=0 を確認。
- ユーザーより「**stg 環境の DB を特に使用しない場合、テーブルをクリアし、サービスを停止したい**」との要望。現状確認結果: stg バッチスケジュール 2 本はいずれも DISABLED、stg DB 接続数は 2026-10-12 以降ゼロ、稼働中は stg Web サービス（2 タスク）のみ。破壊的操作のため、手順を提示した上で**明示的な go を待つ**。未実施。
  - 提示した手順: (1) Aurora 手動スナップショット取得 → (2) 本番由来 4 テーブル（contract / gas_bill / denki_bill / early_bill）を `restore-stg-db.sh` と同じ経路・ガードで TRUNCATE（admin_user / access_log は残す） → (3) CloudFormation の `ECSTaskDesiredCount=0` で stg Web サービス停止 → (4) Aurora stg クラスタ停止（7 日で自動再起動するため、長期ならスナップショット後に削除）。
  - ユーザーに確認中: TRUNCATE 対象は 4 テーブルでよいか（全テーブルなら admin_user も含む）／Aurora は停止か削除か／stg を外部（ecubenet 等）に見せる運用の有無（無ければ Step 2 の IP 制限は prd のみ）。

## 2026-10-18 JPCERT-AT-2026-0030 を受けた追加対策（お客様依頼）

### 決定・実施

- お客様より JPCERT 注意喚起（https://www.jpcert.or.jp/at/2026/at260030.html 、国内組織の不正アクセス相次ぎ）を踏まえ「できる対策を加えてください」との依頼。
- 痕跡調査（prd WAF ログ 90 日）: 注意喚起記載の攻撃元 IP のうち 20.210.128.125 が 10/3〜10/8 に 387 回アクセス（`.php` 系の既知脆弱性スキャン、全件 WAF 遮断）。Metabase 型の探索 `/api/session/properties` 約 80 件（10/17 の ApiAllowList 以降は遮断）。管理者ログイン POST 810 件はすべて JP。GuardDuty 検出なし。
- 推奨対策との対照表を `support/jpcert_at260030_mapping.md` に作成（対応済み / 今回追加 / お客様判断・アプリ改修 / 該当なし）。
- **インフラで追加できる対策を coopinf Draft PR #44 に実装（Count 既定、未デプロイ）**: https://github.com/alphacmc/coopinf/pull/44
  - `AdminGeoRestrict`（P12）: 管理画面・管理 API への日本以外からのアクセス
  - `AdminSensitiveRateLimit`（P13）: 会員検索・請求詳細・パスワード変更 API を 30 回 / 5 分 / IP（正規実績最大 6）
  - `ApiRateLimit`（P14）: `/api/` 全体を 100 回 / 5 分 / IP（正規実績最大 27、スキャナ 117）
  - CloudWatch アラーム 4 本 → 既存 SNS（エラー通知メール）
- **やらないと決めたこと**: 組合員向け画面の地域制限（海外からの正規利用の可能性があるためお客様判断待ち）、`AnonymousIpList` の Block 化（管理者の VPN 経由ログインが該当しテレワーク時に遮断の恐れ）。
- 段取り: ユーザーの go → stg に Count 投入 → prd に Count 投入 → 観察（アラームメール・WAF ログ）→ ルールごとに Block。アプリ側（ロール認可、JWT 短縮、MFA、フレームワーク更新）と CloudTrail はお客様判断待ち。

## 2026-10-18 管理画面アクセス IP ランキングの提示と PR ＃44 の修正

### 決定・実施

- ユーザー依頼で本番・検証の WAF ログ 90 日から管理画面アクセス IP ランキングを作成（`support/jpcert_at260030_mapping.md` 第 5 節）。
- 発見: `GET /api/admin-auth/csrf` は組合員向け画面を含む全ページから呼ばれており（`_app.tsx`）、管理者アクセスの集計からは除外が必要。本当の管理者アクセスは KDDI の 1 IP（お客様拠点と推定、ログイン 776 件）に集中、他は在宅と思われる国内 8 IP と海外スキャン。
- **PR #44 を修正**: `AdminGeoRestrict` の対象を `/api/admin-auth/` から `login` / `logout` に限定（csrf を除外）。海外の組合員（90 日で US 49 IP 等）のアクセスでアラームが誤検知するのを防ぐ。遮断自体は組合員画面に実害なし（コード確認済み）。PR にコメントで経緯を記載。
- Step 2（管理画面の IP 制限）について: 管理者が在宅の複数 IP・VPN 経由で利用している実績があり、固定 IP 許可リストは困難との見立てを強化。MFA（B2 案）優先が妥当。

## 2026-10-18 IP ランキングの訂正（60.87.89.210）と stg ランキングの提示

### 決定・実施

- ユーザーより「60.87.89.210 は弊社ではない」との指摘。確認の結果、この IP はセキュリティ対応の作業端末（この Mac）が 10/17〜18 に接続していた SoftBank 回線の出口 IP（checkip で現在も同値）。本番 10 ログイン・stg 49 ログインはいずれもこの端末からのテストと確認作業。対照表の記載を「アルファ CMC」から「作業端末の回線、会社拠点ではない」に訂正。
- stg の管理者アクセスランキング（CSRF 取得除外）を `support/jpcert_at260030_mapping.md` 第 5 節に追記。stg のログインはすべて国内 IP で、8 月上旬の移行試験期間（BIGLOBE / ARTERIA / So-net）に集中、10 月は作業端末のみ。187.15.x（LACNIC 割当、WAF は JP 判定、AnonymousIpList 該当）は VPN/プロキシ経由と推定。

## 2026-10-18 PR ＃44 マージ → stg に Count 投入

### 決定・実施

- ユーザーが coopinf PR #44 をマージ（11:45 JST 頃）。記録済みの段取りに従い、**11:50 JST に `waf-stg-stack` へ新 3 ルール（AdminGeoRestrict / AdminSensitiveRateLimit / ApiRateLimit）を Count で投入**（UPDATE_COMPLETE）。既存の ApiAllowList / LoginRateLimit は Block のまま。CloudWatch アラーム 4 本（`coopcde-stg-waf-*`）が作成され、通知先は stg のエラー通知 SNS（メール 2 件）。
- 確認: ルール Priority 10〜14 の Action と閾値（10 / 30 / 100）が意図どおり。`/web/admin/login`・`/api/admin-auth/csrf` は 200。テスト送信は行っていない（レート制限の動作確認は Count の記録で済ませる方針）。
- 次: stg で数日観察（アラームメールの頻度と CountedRequests に正規利用が混ざらないこと）→ prd に Count 投入（ユーザー go 待ち）→ ルールごとに Block。

## 2026-10-18 stg の警告メール宛先を coopcde-support@alphacmc.co.jp に変更

### 決定・実施

- 宛先の現状（ユーザー照会への回答）: prd は `coopcde-send-error-alart-topic-prd` → coopcde-support@alphacmc.co.jp。stg は `coopcde-send-error-alart-topic-stg` → naruseh@ / susumagok@（個人 2 件）。WAF アラームは同トピックに通知。
- ユーザー指示「**stg を coopcde-support@alphacmc.co.jp に変更**」。stg トピックは coopcdealert のエラー通知とも共用のため、エラー通知の宛先も同時に変わる旨を伝えた上で実施。
- 段取り: (1) 12:00 JST に stg トピックへ coopcde-support@ を購読追加（PendingConfirmation、確認メールのリンク押下待ち）→ (2) 確認完了を確認後、既存の個人 2 件を購読解除。先に解除すると宛先ゼロの期間ができるため、この順序とする。(2) は未実施。
- **完了（12:10 JST）**: coopcde-support@ の購読確認完了（確認メールのリンク先ページで「Confirm Subscription」ボタン押下が必要だった。リンクを開くだけでは未確認のまま）。確認後、naruseh@ / susumagok@ の 2 件を購読解除。stg トピックの宛先は coopcde-support@alphacmc.co.jp のみ。疎通テストメールを 1 通送信。

## 2026-10-18 PR ＃44 の 3 ルールを prd に Count 投入

### 決定・実施

- ユーザー指示「prd にも Count 投入お願いします」を受け、**12:19 JST に `waf-prd-stack` へ AdminGeoRestrict / AdminSensitiveRateLimit / ApiRateLimit を Count で投入**（UPDATE_COMPLETE）。PathBlock / ApiAllowList / LoginRateLimit は Block のまま。アラーム 4 本（`coopcde-prd-waf-*`）は coopcde-send-error-alart-topic-prd（coopcde-support@）に通知。
- 確認: Priority 9〜14 の Action と閾値（10 / 30 / 100）が意図どおり。`/web/admin/login`・`/api/admin-auth/csrf` は 200。テスト送信なし。
- 次: stg / prd とも Count で数日観察（アラームメールの頻度、CountedRequests に正規利用が混ざらないこと。特に prd の ApiRateLimit は組合員トラフィックが対象）→ ルールごとに Block（ユーザー go 待ち）。

## 2026-10-18 stg データ削除とマスキングの統合方針を決定

### 経緯・現状確認

- stg データ削除とデータマスキングは「stg を今後も本番データで試験する環境として使うか」で決まる同一問題として統合検討。
- 現状: 本番バックアップ `backup-prd-db.sh`(prd側cron)は**今も毎晩稼働**し、リレーバケット `coop-migration-relay-725011976834/db-copy-to-stg/` に本番4テーブルの日次ダンプ(約180MB/日、18件・約3.3GB、ライフサイクル無し・AES256・KMS不使用・PAB有効)を出し続けている。供給先の `restore-stg-db.sh`(stg側restore cron)は2026-09-09停止済みだが、供給元は止まっていなかった。stg DB の4テーブルには旧い本番PIIが残存(10/12以降アクセス0)。stg CSV バケット `treated/` に本番由来CSV 2,337件(PII含む)。
- マスキングの見直し: 旧Task4案「stg側 pg_restore後UPDATE」では、本番生データが stg に届く前にリレーバケットへ毎晩平文で置かれるため不十分という点を指摘。

### 決定事項（ユーザー、2026-10-18）

- **方針は B（stg存続・コールド化）に近い**。確定した内容:
  1. **バックアップは取り続ける**（`backup-prd-db.sh` は停止しない）。
  2. **S3 上からは 1 週間で削除**する → リレーバケット `db-copy-to-stg/` に **7日expireのライフサイクルを設定済み**（2026-10-18実施、`latest.dump`は毎日更新のため残る、日付付きダンプが7日超で自動削除）。
  3. **試験投入の際にデータマスキングする** → マスキングのタイミング(Task 3)は「stg への投入時」で確定。DB は `restore-stg-db.sh` の `pg_restore` 後 UPDATE、CSV は stg バケット配置前に変換。本番側ダンプ生成時マスキングは採用しない。
- `support/data_masking_tasks.md` の Task 3 を決定済みに更新。

### 残論点（未確定・次アクション）

- Task 4（マスキング方式）: 自作 + `@faker-js/faker`（実在しそうなダミー生成、第一希望）で確定してよいか。実装は coopinf `restore-stg-db.sh` 改修 + CSV変換スクリプトで、設計を伴うため方式同意後に着手。
- 現在 stg DB に残る未マスクの本番PII(4テーブル)を今クリアするか（破壊的操作のため要確認）。
- stg CSV バケット `treated/` の本番由来CSV 2,337件の扱い（1週間ライフサイクル追加 or 投入時のみマスク済みを置く運用に切替）。
- リレーバケット `compare/`(不一致行の全列JSON、PII)にもライフサイクルを及ぼすか。

## 2026-10-18 マスキング実装（DB・SQL方式）と残承認済み作業の実施

### 実施

- 承認4点のうち実施:
  1. **stg CSV バケット `coopcde-stg-batch-csv-backup` に 7日expireライフサイクル設定**（本番由来CSV 2,337件等を漸次削除。今後の試験はマスク済みCSVを配置）。
  2. **リレーバケット `compare/`（不一致行JSON・PII）に 7日expireライフサイクル追加**（既存 db-copy-to-stg ルールは保持）。
  3. **現 stg DB の4テーブルをクリア**（SSM経由、stg接続ガード付き。contract 107,606 / gas_bill 734,955 / denki_bill 2,322,699 / early_bill 2,742,591 → 全て0件）。未マスクの本番PIIをstg DBから除去。
  4. **マスキング実装（DB分）**: coopinf PR #45。`restore-stg-db.sh` に pg_restore 直後のマスキングを追加 + `mask-stg-contract.sql`。
- **方式変更（要確認）**: 了解は「faker」だったが coop-stg-manage に **Node が無い**ため、追加依存なしの **SQL方式**で実装。行ごとに異なる実在風ダミー・電話番号一意・識別子温存・決定的。PostgreSQL 15 でローカル検証済み。faker 相当が必要なら Node 追加で差し替え可能。

### 注意・残作業

- **デプロイ未実施**: PR #45 の2ファイルは coop-stg-manage へ配置するまで無効。配置前に `restore-stg-db.sh` を実行すると旧版（マスクなし）が動くため、マージ後にデプロイするまで手動実行しないこと。デプロイはマージ後に SSM で実施予定（ユーザー判断）。
- CSV（AGREEMENT/K010）マスキングは未着手。仕様（列位置）と手動S3配置フロー上の実施場所を決めてから対応。
- 確認したい点: (a) SQL方式で確定か（faker=Node追加を要する）、(b) PR #45 マージ後にデプロイを Claude が SSM で行ってよいか、(c) CSV マスキングの進め方。

## 2026-10-18 restore-stg-db.sh に --no-mask オプション追加

### 決定・実施

- ユーザー決定: 「引数なしなら従来どおりマスク（安全側の既定）、**--no-mask 方式**で選べるように」。
- 実装（coopinf PR #45 に追加コミット）: `restore-stg-db.sh` の引数解析を拡張。既定 `DO_MASK=1`、`--no-mask` 指定時のみスキップし警告ログを出力。ダンプ名と `--no-mask` は順不同、不明オプションはエラー中止。`sh -n` と引数解析ドライランで全ケース検証済み。
- `support/data_masking_tasks.md` Task 5 に反映。

## 2026-10-18 マスキングを stg-manage にデプロイ

### 実施

- ユーザー承認を受け、coopinf main の `restore-stg-db.sh`（マスキング対応版 + --no-mask）と新規 `mask-stg-contract.sql` を SSM 経由で coop-stg-manage:/home/ssm-user/coop-migration/ に配置。
- 旧 `restore-stg-db.sh` は `.bak_20261018_121510` に退避。配置後 sha256 がローカル正本と両ファイル一致、`sh -n` 構文チェック OK。
- これで次回 `restore-stg-db.sh` 実行時にリストア直後マスキングが動作する（`--no-mask` でスキップ可）。

### 残作業・確認

- 実データでの通し確認（stg-manage で `restore-stg-db.sh` を実行しリストア＋マスクを検証、stg DB にマスク済みデータが入る）はユーザー判断待ち。現在 stg DB は空。
- CSV（AGREEMENT/K010）マスキングは未着手（仕様の列位置確認 + 手動S3配置フロー上の実施場所決定が必要）。

## 2026-10-18 CSV（AGREEMENT/K010）マスキングの実装

### 決定（ユーザー）

- 範囲: **案A**（ファイルに存在する個人情報列すべてをマスク。バッチ非参照列も含む）。
- DB マスキング値との一致: **不要**。
- **マスクしないモード（--no-mask）も追加**してほしい。

### 実施

- 仕様確認: AGREEMENT は SJIS(cp932)・1行目ヘッダ・バッチは列名参照。stg-manage に python3.9+cp932 あり(Node無し)。対象は AGREEMENT/K010 のみ（INVOICE/EARLY は個人情報なし）。
- 実装（coopinf PR #46）: `migration/script/mask-agreement-csv.py`。Python3標準ライブラリのみ、ヘッダ列名で判定し列順非依存。個人情報列（名義/カナ/郵便/住所各部/電話/メール/受付担当者/立会者/事前連絡先/旧契約名義/停電通知先/需要者窓口/電気主任技術者/申込者/移転先/ご請求先）をダミー化。識別子・空欄・非個人情報列は保持。契約番号ベースで決定的。`--no-mask` あり。ローカルSJISサンプルで全項目検証。
- 手順書: `support/stgenv_test_procedure.md` の「対象データのマスキング」節を確定（DB=restore-stg-db.sh 自動マスク、CSV=mask-agreement-csv.py を untreated 配置前に実行、いずれも --no-mask で未マスク可）。
- `support/data_masking_tasks.md` Task 5(CSV)・Task 6 を更新。

### 残作業

- coopinf PR #46 マージ後に mask-agreement-csv.py を stg-manage へ配置（DB分と同様 SSM 予定、ユーザー判断）。
- 実データでの通し確認（stg 再投入＝restore-stg-db.sh 実行、CSV 1本をマスクして投入）はユーザー判断待ち。
- 既知の軽微点: 名義（漢字）と名義カナは独立生成のため姓が対応しない場合あり（ダミーのため実害なし、要望あれば対応）。

## 2026-10-18 マスキング: stg-manage へ配置と実データ通し確認（完了）

### 実施

- **CSV スクリプト配置**: coopinf PR #46 マージ後、`mask-agreement-csv.py` を SSM で coop-stg-manage:/home/ssm-user/coop-migration/ へ配置（sha256 一致・構文OK）。DB分(PR #45)は配置済み。
- **DB 通し確認（実データ）**: stg-manage で `restore-stg-db.sh latest.dump` を実行。contract 107,778 件を投入時マスク。検証: ダミー10姓以外の氏名=0、電話は全件 090-XXXX-XXXX で重複0、郵便は全件7桁、識別子(contract_number/member_code)は全件保持。漢字氏名とカナも対応（例 鈴木/スズキ）。
- **CSV 通し確認（実データ）**: stg バケットの実 AGREEMENT(110610997IF-K010、189列22行)を `mask-agreement-csv.py` で処理。結果: 構造保持(22→22)、本番ヘッダに想定列がすべて存在、名義22件すべてダミー化(非ダミー姓0)、電話22件すべて090形式、契約番号・需要家提示お客さま番号は全件不変、cp932 で読み出し可、計53列マスク（案Aにより取次先・停電通知先・ご請求先・移転先・申込者・電気主任技術者等も実データがありマスク対象になった）。個人情報は一切ログ出力せず集計値のみで検証。

### 状態

- stg DB は現在、本日の prd スナップショットを**マスク済み**で保持（通し確認で再投入。実PIIなし）。
- マスキング（DB・CSV）は実装・配置・実データ検証まで完了。data_masking_tasks.md の全 Task 完了。
- stg CSV バケットの旧 K010(1,423件)等は 7日ライフサイクルで順次削除見込み（設定直後のため削除はこれから）。

## 2026-10-19 stg 環境のワンコマンド起動/停止（通常時は停止運用）

### 決定（ユーザー）

- stg は通常時、DB（Aurora）も ECS サービスも停止。試験時にワンコマンドで起動したい。実行場所は **案A（coop-stg-manage 上、IAM 付与）**。

### 実施

- `coop-stg-manage-role`（CF管理外・手動作成）に stg 限定のインラインポリシー `stg-env-control` を CLI で付与（rds:Start/Stop/Describe、ecs:UpdateService/DescribeServices、対象 ARN・ecs:cluster 条件で限定）。
- coopinf PR #47: `stg-env-up.sh`（Aurora起動→available待ち[既定最大60分/STG_UP_WAIT_SEC]→ECS desired=2→安定待ち、`--with-restore [dump] [--no-mask]` で restore-stg-db.sh も連続実行）、`stg-env-down.sh`（ECS desired=0→Aurora stop、データ保持）。識別子に stg を含むリソースのみ操作する安全ガード付き。stg-manage へ配置済み（ハッシュ一致）。
- coop PR #(docs): `stgenv_test_procedure.md` に「stg環境の起動・停止」節を追加。
- 実機検証（SSM）: down→Aurora stopped（約9分）→up（start→available、ECS2/2）→down→stopping。初回 up は待機上限20分では Aurora コールドスタートに足りずタイムアウト→上限を60分に修正・再配置して完走確認。**最終状態＝停止**。

### 注意・運用

- Aurora は停止後 7 日で AWS が自動再起動するため、その際は `stg-env-down.sh` を再実行する。
- 停止からの初回起動は 20〜30 分程度かかる。
- stg DB のデータは停止で消えない（起動で復帰）。現状はマスク済みデータを保持したまま停止。

## 2026-10-19 stg 日次down スケジュールと1コマンド有効/無効化

### 決定（ユーザー）

- 1) 日次 down の時刻 = **JST 04:00**（OK）。2) up/down への **スケジュール自動連動あり**（OK）。

### 実施（coopinf PR #47 に追加 + AWS 設定）

- EventBridge Rule `coopcde-stg-daily-down`（cron(0 19 * * ? *)=JST04:00、既定 ENABLED）を作成。ターゲットは SSM RunCommand で coop-stg-manage 上の `stg-env-down.sh` を実行。
- IAM: Rule 用ロール `coopcde-stg-daily-down-events-role`（events→ssm:SendCommand、対象ドキュメント/インスタンス限定）を新規作成。`coop-stg-manage-role` に `events:Enable/Disable/DescribeRule`（当ルール限定）を追加。
- スクリプト: `stg-schedule.sh enable|disable|status`（`aws events enable-rule/disable-rule` を1コマンド化）。`stg-env-up.sh` は冒頭でルールを自動 disable、`stg-env-down.sh` は末尾で自動 enable（いずれも非致命的）。
- 実機検証: status/disable/enable の遷移、up.sh 冒頭での自動 disable を確認。検証で up を中断し Aurora が起動したため、available 待ち後に down.sh で停止＋スケジュール自動 enable。**最終状態＝ECS0・Rule ENABLED・Aurora stopping→stopped（通常運用状態）**。

### 運用

- 通常: スケジュール ENABLED（毎日停止を維持）。
- 試験: `stg-env-up.sh`（自動で schedule disable）→試験→`stg-env-down.sh`（自動で schedule enable）。日をまたぐ長時間試験などで手動 disable も可。
- 注意: 停止からの初回起動は20〜30分。

## 2026-10-19 運用(ops)リソースを本番サービス定義と分離し coopinf に IaC 保存

### 決定・実施

- ユーザー方針: 本番サービス関連と運用ベースの定義を分け、EventBridge Rule 等の運用リソースを coopinf に保存する。
- 対応: 新テンプレート `coopinf/cf/stg-ops-cf.yaml` を作成（本番サービス定義とは別ファイル）。内容は 2026-10-18〜19 に CLI 作成した運用リソースを定義化（名称は実リソースと一致）:
  - EventBridge Rule `coopcde-stg-daily-down`（JST04:00、SSM RunCommand で stg-env-down.sh）
  - その実行用 IAM ロール（events→ssm:SendCommand）
  - 既存 coop-stg-manage-role（CF管理外）へ付与する `stg-env-control` ポリシー
  - `validate-template` OK。Draft PR: coopinf #48。

### 未決（ユーザー確認待ち）

- 実リソースのスタック化方法: 案1 保存のみ / **案2 削除→デプロイ(推奨)** / 案3 CloudFormation import。
- リレーバケットのライフサイクル（CF管理外バケット）と coop-stg-manage-role 本体（手動作成）を ops テンプレートに取り込むかは別途相談。

## 2026-10-19 stg-ops リソースをスタック化（案2 実施）

### 実施

- ユーザー決定: 案2（削除→デプロイ）。
- 手動作成していた運用リソースを削除（Rule coopcde-stg-daily-down、events ロール coopcde-stg-daily-down-events-role、coop-stg-manage-role のインライン stg-env-control）→ `cf/stg-ops-cf.yaml` を **`coopcde-stg-ops-stack`** としてデプロイ（CREATE_COMPLETE、CAPABILITY_NAMED_IAM）。3 リソース作成。
- 検証: Rule ENABLED（JST04:00・SSM ターゲット再現）、manage-role の stg-env-control 復活、stg-schedule.sh の status/disable/enable 正常。
- これで運用(ops)リソースは本番サービス定義と分離した IaC（coopinf PR #48）かつスタック管理下となり、リポジトリと実体が一致。

### 残件

- coopinf PR #48（stg-ops-cf.yaml）マージでリポジトリ main と実デプロイが一致（デプロイはブランチのテンプレートから実施済み、内容は同一）。
- リレーバケットのライフサイクル（CF管理外バケット）と coop-stg-manage-role 本体（手動作成）の IaC 化は別途相談。

## 2026-10-20 alphasystem の運用規則を coop 系に適用

- **経緯**: ユーザーから「alphasystem 配下プロジェクトで決まった規則を coop 配下にも適用したい」。alphasystem 側では同日、coop への展開依頼を撤回し「coop 系の運用は coop 側のセッションで判断する」としていたため、coop のセッションで適用範囲を決めた。
- **承認（ユーザー）**: 候補 A〜G のうち次を採用。
  - **A セッション間連携**: 起動中の相手には `ListAgents`/`SendMessage`、未起動なら相手リポジトリ直下に未追跡の `INBOX_FROM_COOP.md` を置く。サブエージェントは閉じた調査・軽作業に限る。
  - **B 会話記録の日付別化**: `conversations/YYYY-MM-DD.md`。旧 `conversations.md` はアーカイブとして残し追記しない。対象は coop・coopinf・coopbatch（既に会話記録があるもの）。coopcdebatch（廃止予定）・coopcdeinput（廃止）は対象外。coopcdeweb・coopcdealert・coops3view は会話記録がないため変更なし。
  - **C 記録の置き場**: 設計の決定は coop に置き、実装計画以降は各プロジェクトに置く。結合試験は設計者（coop）が担当する。
  - **D 作業エージェントの担当分け**: 全体調整（coop）／インフラ・移行（coopinf）／バッチ（coopbatch）／Web（coopcdeweb・coops3view）。
  - **E `/project-status` と SessionStart フック**: alphasystem のスクリプトを移植。Windows（Git Bash）向けに、`.gitattributes`（`*.sh` を LF に固定）、`CLAUDE_PROJECT_DIR` と `git rev-parse --show-toplevel` のパス形式の正規化を追加した。
- **やらないと決めたこと**:
  - **F `/save-session`・`/resume-session`**（別 PC 再開用）は採用しない。
  - **G ブランチ運用（main/staging の 2 本立て）は見送る**。coop 系には staging が無く、CI・デプロイのトリガーが変わるため。coop 系は従来どおり main をベースにする。
- **実施**: coop は CLAUDE.md に「作業エージェント」「記録の置き場と結合試験」「セッション間の連携ルール」の節を追加し、`conversations/` を作成、`.claude/`（settings.json・hooks・commands）と `.gitattributes` を追加した。Windows 形式のパスを渡した場合も含め、スクリプトで 8 プロジェクト分の表が出ることを確認済み。
- **申し送り**: coopinf・coopbatch の日付別への切り替えは、A の規則に従いそれぞれのセッションで行ってもらう（未起動のため `INBOX_FROM_COOP.md` を置いた）。
- **有効化の注意**: SessionStart フックは、設定ファイルがあった状態で始まったセッションでしか発火しない。マージして取り込んだ後、VS Code で `Developer: Reload Window` を実行してから新しい会話を始める。

## 2026-10-20 coopcdeinput・coopcdebatch を coop の構成から外す

- **指示（ユーザー）**: 実質使っていない coopcdeinput・coopcdebatch を外す。
- **対応**: CLAUDE.md の「構成」表から 2 行を削除し、`/project-status`・SessionStart フックの一覧にも出ないようにした（表から自動で拾う仕組みのため）。作業エージェントの担当からも外した。
- **残したもの**: coopcdebatch は「coopcdebatch のロジックを再現する」原則（ユーザー共通ルール）の参照元になるため、表の外に「参照元としてのみ読む」旨の一文を残した。リポジトリ自体（~/git 配下の clone）は削除していない。

## 2026-10-20 coopcdeweb・coops3view・coopcdealert にも運用規則を申し送る

- **承認（ユーザー）**: 「お願いします」。最初の申し送り（日付別記録への切り替え）は会話記録がある coopinf・coopbatch だけに送っていた。しかし CLAUDE.md の無いリポジトリのセッションは coop の規則を知る手段がないため、残りの 3 リポジトリにも送ることにした。
- **実施**: 3 つとも未起動（`ListAgents` で確認）だったため、各リポジトリ直下に `INBOX_FROM_COOP.md`（未追跡）を置いた。内容は次のとおり。
  - 規則の要約: 位置付け（coopcdeweb・coops3view は Web担当、coopcdealert は担当未定）、連携ルール、記録の置き場、結合試験、ブランチ運用（main のまま）、coopcdeinput・coopcdebatch の除外
  - 依頼: 会話記録は最初から `conversations/YYYY-MM-DD.md` 形式で作る。余裕があれば自リポジトリの CLAUDE.md に「coop の CLAUDE.md の規則に従う」旨の一文とリンクを足す
- **残り**: 各セッションの起動待ち（coopinf・coopbatch を含め計 5 リポジトリ）。

## 2026-10-22 coopcdeweb から申し送り: Node 24 への更新と、他リポジトリと揃えるかの判断依頼

- **受信**: coopcdeweb から `INBOX_FROM_COOPCDEWEB.md`（coop 直下、未追跡）。内容を本記録に取り込んだのでファイルは削除した。詳細は coopcdeweb の `conversations/2026-10-22.md`、PR alphacmc/coopcdeweb#110（Node 24 への更新、マージ済み）・#111（記録、Draft）。
- **coopcdeweb の状況**: Node 18（2025-04 に EOL）から **Node 24（2028-04 に EOL）** に更新した（`node:24-alpine3.24`）。stg には 1.5.0 として反映し、確認も済んでいる。prd は未反映（1.4.1 = Node 18 のまま）。
- **各リポジトリの Node（coop で origin/main を確認、2026-10-22 時点）**:

  | リポジトリ | Node | EOL | 指定箇所 |
  |---|---|---|---|
  | coopcdeweb | 24 | 2028-04 | `apps/{backend,frontend}/Dockerfile`（`node:24-alpine3.24`） |
  | coopbatch | 20 | **2026-04（EOL 済み）** | `Dockerfile`（`node:20-alpine`） |
  | coops3view | 22 | 2027-04 | `Dockerfile`（`node:22-alpine`） |
  | coopcdealert | 22（申し送りでは推定） | 2027-04 | Lambda `nodejs22.x`（`coopcde-send-error-alart-stg/prd-index`）。coopcdealert にも coopinf にもランタイムの指定は無い |

- **判断依頼（未決）**:
  1. coopbatch・coops3view・coopcdealert を Node 24 に揃えるか。揃える場合は、各リポジトリへ申し送る。
  2. coopcdeweb を prd に反映（1.5.0）する時期。
- **他リポジトリで更新するときに効く知見（coopcdeweb より）**:
  - Prisma と alpine: 新しい alpine では `libssl.so.3` が `/usr/lib` にしか無く、Prisma が OpenSSL のバージョンを判定できない。その結果 OpenSSL 1.1 用のエンジンを入れ、DB に接続できなくなる。`RUN apk add --no-cache openssl` で解消する（coopbatch では PR #3 で同じ対応が済んでいる）。
  - bcrypt: 5.x には Node 24 / musl 向けのビルド済みファイルが無いため、6.x に上げた。ハッシュ形式は `$2b$` のままで互換性がある。
  - CloudFormation: `ecs-alb-stg-stack` を更新すると、ECS のタスク数が `ECSTaskDesiredCount`（=2）に戻る。stg を止めたままスタックを更新すると、DB が止まった状態でタスクが起動するので注意。
- **stg の状態**: coopcdeweb の確認のため stg を起動しており、ユーザーの判断で**しばらく起動したまま**にする。日次の停止スケジュール `coopcde-stg-daily-down` は DISABLED のまま。止めるときは `stg-env-down.sh` を使う（停止スケジュールも有効に戻る）。

## 2026-10-22 Node バージョン統一の方針（ユーザー、coopcdeweb 経由）と、定期的なバージョンアップの必要性

- **受信**: coopcdeweb のセッション（coopcdeweb-b5）から `SendMessage` で追送があった。先の申し送り（coopcdeweb 2623dc2）の続き。詳細は coopcdeweb の `conversations/2026-10-22.md`（PR alphacmc/coopcdeweb#111）。
- **方針（ユーザー、coopcdeweb で表明）**:
  - Node の統一は coop と相談して決める。統一先は**おそらく Node 24**（最終決定は coop で行う）。
  - **coopcdeweb は急ぐ**（インターネットに公開されているため）。
  - coopbatch・coops3view・coopcdealert は直接インターネットに公開されていないので、**後日対応**とする。
    → 先の判断依頼 1 の推奨（coopbatch を至急）とは優先度の考え方が異なる。インターネットに公開されているかどうかを優先度の基準にする。
- **新しい課題: 定期的・継続的なバージョンアップのスケジュールを組む**（Node と依存ライブラリの両方。全体調整として coop で扱う。スケジュールは未定）。
  - 参考（coopcdeweb の現状）: 依存ライブラリは 2023 年ごろのまま。`npm audit --omit=dev` で既知の脆弱性が 59 件ある（critical 4 / high 29 / moderate 19 / low 7）。Next 13.4.7 と NestJS 9.4.3 はすでに更新が終わっている。Prisma は backend が 4.16.2、frontend が 5.1.1 でバージョンがずれている。
- **訂正（coopcdeweb より）**: 先の申し送りにあった「backend の Dockerfile が package-lock を使っていない」は誤り。`turbo prune --docker` を経由して、実際には lock どおりにインストールされている。turbo のバージョンが固定されていない（ビルドのたびに最新が入る。現在は 2.11.10）のは事実。
- **coopcdeweb 側で決めること**: 脆弱性への対応と、prd への反映（1.5.0）の進め方。決まったら coop に連絡が来る（先の判断依頼 2 は coopcdeweb 側で決まる）。

## 2026-10-28 coopbatch から事後の申し送り: Node 24 / Prisma 7（1.2.0）に更新し、prd まで反映済み

- **受信**: coopbatch から `INBOX_FROM_COOPBATCH.md`（coop 直下、未追跡）。内容を本記録に取り込んだのでファイルは削除した。詳細は coopbatch の `conversations/2026-10-23.md`・`2026-10-26.md`・`2026-10-28.md`。
- **方針との関係**: 2026-10-22 の方針では、coopbatch は「インターネット非公開のため後日対応、統一先はおそらく Node 24（最終決定は coop）」としていた。**ユーザーの判断で、coop の正式決定を待たずに先行して対応した**（事後の申し送り）。
- **coopbatch の現状（prd・stg とも 1.2.0。coop で origin/main を確認済み）**:

  | 項目 | 変更前 | 変更後 |
  |---|---|---|
  | Node | 20（`node:20-alpine`） | **24**（`node:24-alpine3.24`、coopcdeweb と同じ） |
  | Prisma | 5.22 | **7.10.1**（`prisma-client` を CommonJS で生成、`@prisma/adapter-pg`） |
  | DB 接続の SSL | Prisma のエンジン任せ（TLS 1.3、証明書の検証なし） | **RDS の CA 証明書束で検証して暗号化**（TLS 1.3）。既定で有効、ローカルだけ `DB_SSL=false` |
  | version | 1.0.2 | 1.2.0（途中の 1.1.0 = Node 24 / Prisma 6 は stg のみ） |

  - 経緯: 2026-10-23 PR #30（Node 24・Prisma 6、1.1.0）→ 2026-10-26 PR #33（Prisma 7、1.2.0）。
  - これで Prisma 6 のサポート終了（2026-11-19）は、coopbatch には影響しなくなった。
  - Prisma 7 への対応は、coopcdeweb から共有されたノウハウ（PrismaPg、検証付き SSL、Aurora の CA は `rds-ca-ecc384-g1`）に沿っている。
- **確認済み（coopbatch より）**:
  - stg: 1.1.0・1.2.0 とも、オンデマンド実行（SFTP の確認だけの実行と通常の実行）が正常に終了した。1.2.0 では、アプリ本体から自分の接続の `pg_stat_ssl` を読み、`TLSv1.3`・`TLS_AES_256_GCM_SHA384` で接続していることを確認した。
  - prd: 2026-10-26 17:50 JST に `coop-ecs-batch-prd` を ImageTag 1.2.0 に更新した。**2026-10-27 09:30 JST の定期実行が 1.2.0 で正常に終了した**（契約 56 件・速報値 3,517 件、エラー 0 件）。
- **Node の統一状況（更新）**: coopcdeweb・coopbatch が Node 24 になった（EOL 2028-04）。残りは coops3view（22）と coopcdealert（22、Lambda）で、どちらも EOL は 2027-04。統一先を Node 24 に確定するかと、定期的なバージョンアップのスケジュールは、引き続き coop で未決。
- **prd の定期実行の設定ずれを解消**: `coop-prd-batch-schedule` は実際には ENABLED だったが、stack `coop-ecs-batch-prd` のパラメータ `ScheduleState` は DISABLED のままだった（手作業で有効にしたものと思われる）。ImageTag だけを変える更新で定期実行が止まる危険があったため、1.2.0 の反映時に `ScheduleState=ENABLED` を明示してずれを解消した。今後 stack を更新するときも ENABLED のままでよい。
- **旧 coopcdebatch の ECR タグの付け替え（Claude のミス、ユーザー了承済み）**: 2026-10-26、coopbatch の作業中に、誤って旧 coopcdebatch 用の CodeBuild `coopcde-stg-batch-codebuild` を起動した。その結果、`coopcde-batch:1.4.4` が同じコミット（`b44f1090`、2026-08-31）から作り直したイメージに付け替わった。このタグを参照するのは旧 stg のタスク定義だけ（旧 stg の定期実行は DISABLED、prd は 1.4.3）。**ユーザーの判断で元には戻さない**。coopbatch 用の CodeBuild は `coop-stg-batch-codebuild`（名前が似ているので注意）。

## 2026-11-02 お客様から管理画面 MFA の見積もり依頼、組合員向け機能の点検で High の欠陥を発見

- **依頼（ユーザー）**: お客様から管理画面への MFA 導入の見積もりを求められた。方式別のおおよその工数をまとめてほしい。また、利用者（組合員）向け機能は今のままでセキュリティホールが無いか。
- **成果物**: `support/admin_mfa_estimate.md`（社内検討資料）。
  - MFA の方式別概算: アプリ内 TOTP 6〜8 人日（推奨）、ALB + Cognito 5〜7、メール OTP 7〜9（SES のドメイン認証でお客様の DNS 作業が要る）、SMS 8〜10（非推奨）、パスキー 12〜15。どの方式でも、ロール判定・`change-pass-inlogin` の修正・JWT の確認の強化を同時に行う（+2〜3 人日）ことを推奨する。前提として 1.8 系の prd リリースが先。`admin_user` の列追加は coopbatch のマイグレーションが要る。
  - 10/17 の B2 案の「2〜3 日」は開発だけの数字で、今回は試験・リリース・手順書まで含めた。
- **発見（High、新規）**: 組合員画面 `/web/members` がチケットをエンコードせずに `/api/certif/${ticket}` へ連結しており、`../members/getBillInfoByMember/<コード>` を入れると、チケット認証を通らずに他人の請求情報を表示できる流れがコード上で成立する。prd（1.4.1）・main（1.8.1）とも該当。サーバー内部の呼び出しのため WAF の `ApiAllowList` では防げない。マネージドルールで止まるかは**未確認**（実機にはまだリクエストを送っていない）。
- **ほかに prd で High**: Next 13.4.7 の画像最適化 API の重大脆弱性（PR #113 の暫定対策は 1.4.1 に入っていない）。
- **ユーザーの判断待ち**: (1) stg（必要なら prd）での無害な成立確認と、prd の WAF ログでの悪用痕跡の調査をしてよいか。(2) 4.1 の hotfix（1.4.1 と 1.8 系）・WAF の暫定ルールを coopcdeweb・coopinf に依頼するか。(3) お客様への見積もりの出し方（MFA と、今回の欠陥の修正を分けるか）。

## 2026-11-02 方針変更: MFA は保留し、組合員向けのセキュリティホールの修正を先に行う

- **決定（ユーザー）**: 「MFA はおいておいて、セキュリティホールを修正したい」。MFA の見積もり（`support/admin_mfa_estimate.md` §2〜3）は保留とする。
- **対応状況の確認**: coopcdeweb の PR（〜#131）に該当の修正は無い。origin/main（1.8.1）の `members/index.tsx:55, 95` は未修正のまま。1.8.1 の prd リリース時期はお客様と調整中（coopcdeweb の記録）。
- **補足（調査）**: チケットの形式は coop・coopcdeweb の仕様書に記載が無い（外部の ticketService の仕様）。そのため、許可文字を厳しく絞る正規表現は正規のチケットを弾くおそれがあり、エンコードと `.`/`..` の拒否を基本とする案にした。memberCode は DB 上 `VarChar(15)`、stg スタブは `^\d{1,15}$` で検査している。`/web/sample/members/[memberCode]` にも同じ連結があるが、prd では WAF で遮断している。
- **修正方針は提示中（ユーザーの同意待ち）**。同意後、実装は coopcdeweb、WAF は coopinf のセッションに依頼する。
- **提示した方針（同意待ち）**:
  - ① frontend でチケットを `encodeURIComponent` で連結し、`.`・`..`・配列を拒否する。memberCode は `^\d{1,15}$` で確かめる。テストも追加する。
  - ② `IpGuard` を localhost 限定にする。ECS で frontend からの呼び出しが localhost から届くかを stg で確認してから入れる。①とは別のコミットにする。
  - ③ WAF の暫定ルール（coopinf）。`ticket` を 2 回デコードし、`..` か `/` を含むものを Block する。Count で様子を見てから Block にする。
  - ④ Next の重大脆弱性は 1.8 系の prd リリースで解消する。
  - 判断を依頼した点:
    - リリース方法。推奨は (a): 1.8.2 として、1.8.1 の prd リリースと一緒に出し、それまでは WAF で守る。(b) は 1.4.2 の hotfix も出す案。
    - ②を今回のリリースに含めるか。
    - stg での成立確認と、prd の WAF ログの調査をしてよいか。

## 2026-11-02 セキュリティホール修正の方針: (a) で進める、成立確認と WAF ログ調査を承認

- **決定（ユーザー）**:
  1. リリース方法は **(a)**。①（②を含めるかは下記）を **1.8.2** とし、調整中の 1.8.1 の prd リリースと一緒に出す。それまでは③の WAF 暫定ルールで守る。1.4.2 の hotfix は**出さない**。④（Next の重大脆弱性）も 1.8 系の prd リリースで解消する。
  2. ②（IpGuard の localhost 限定）について、ユーザーから「localhost には限定できないのではなかったか」と確認があった。記録と設定を確認した結果は次のとおり。
     - coopinf の `cf/ecs-alb-cf.yaml` では、frontend と backend が同じタスク（awsvpc）で動いている。`BACKEND_API_URL` は stg・prd とも `http://localhost:3001/api`。監査（`support/security_audit_2026-10-17.md` #4）の結論も「localhost 限定にしても動作に影響なし（trust proxy 未設定なので `request.ip` は偽装できない）。ただし `::ffff:127.0.0.1` を許可に含め、stg で実機確認が必要」。
     - 「IP 制限が難しい」とされていたのは、**管理画面の IP 制限**（お客様のテレワークの可能性、conversations.md 2025 年分の Step 2 の保留）で、別件と思われる。
     - → ②を入れるかは、この説明に対するユーザーの回答を待つ。
  3. stg での無害な成立確認と、prd の WAF ログ調査を**承認**。

## 2026-11-02 stg での成立確認と prd WAF ログ調査の結果

- **実施（profile coop、2026-11-02）**: stg ALB（`coopcde-stg-alb`、1.8.1 稼働中）へ無害なリクエスト 3 本。組合員コードは存在しない `0000000000`。
  - `ticket=..%2Fmembers%2FgetBillInfoByMember%2F0000000000` → **403（WAF BLOCK）**
  - `ticket=%252e%252e%252fmembers%252f...`（二重エンコード） → **403（WAF BLOCK）**
  - `ticket=dummy-invalid-ticket` → 307 で coopデリ（`https://www.coopdeli.jp/`）へ転送（正規の未認証動作）
- **BLOCK の主体（stg WAF ログで確認）**: どちらも `AWSManagedRulesCommonRuleSet` の **`GenericLFI_QUERYARGUMENTS`** が terminating。**二重エンコードも BLOCK された**（資料 §4.1 の「`%252e%252e` はすり抜ける可能性」という推測は、実機では当たらなかった）。WAF が 1 回デコードした `%2e%2e%2f` を LFI として検知している。
- **prd WAF ログ調査（過去 14 日、Logs Insights）**:
  - `/web/members` へのアクセスは 14 日で 2527 件。全体の BLOCK は 14987 件。
  - `members`/`certif` を URI に含み、args に traversal マーカー（`%2e`/`%2f`/`%5c`/`InfoByMember`）を持つものは **0 件**。
  - args に `..` を含む 47 件はすべて無差別ボット探索（`/index.php?lang=../..`、`/userfiles?path=../../.env`、`wp-config.php`、`/etc/passwd`、FortiOS `fgt_lang`、Cisco AnyConnect 等）で、`/web/members`・`certif` を狙ったものは**無い**。
  - → **本件の欠陥が prd で悪用された痕跡は見つからなかった。**
- **評価の更新**: この経路は現在、WAF のマネージドルール（CommonRuleSet が Block で、`GenericLFI_QUERYARGUMENTS` が有効）によって実際に遮断されている。ただし依存先はマネージドルールであり、CommonRuleSet を Count に戻す・ルール除外を入れる等で容易に外れる。アプリ側の恒久修正（①）は引き続き必要。③の WAF 専用ルールは、GenericLFI が既に効いているため優先度は下がる（二重防御として任意）。

## 2026-11-03 セキュリティホール修正: ②を含める・③は不要、認証基盤の資料でチケット形式が確定

- **決定（ユーザー）**:
  1. **②（IpGuard の localhost 限定）を 1.8.2 に含める。** frontend と backend は同一タスクで、frontend は `http://localhost:3001/api` で backend を呼ぶ。NestJS は trust proxy 未設定で `request.ip` は偽装できない。ECS では `::ffff:127.0.0.1`（IPv4 射影）になり得るので許可リストに含め、**stg で実機確認してから**入れる。①とは別コミット。
  2. **③（WAF 専用ルール、coopinf）は不要。** stg 実測で CommonRuleSet の `GenericLFI_QUERYARGUMENTS` が既に単純/二重エンコードとも BLOCK しているため。
- **認証基盤の資料を入手・確認（`C:\Users\yohira\Documents\20230303_認証基盤`、NEC 作成、外部連携仕様 3.12 版 2019-07-02）**。①の形式チェックの根拠が確定した。
  - **チケット（`ticket`）の形式**: チケット認証サービス（WGSGFE04）の入力仕様で **固定 40 桁・半角英数字（数字＋英字）**。例値 `3d516042473f…` と整合。本来は `POST https://ec.coopdeli.jp/auth/ticketService`、`application/x-www-form-urlencoded`、ボディ `ticket=...`（coopcdeweb は自前 backend へ GET パス `/certif/:ticket` で渡す実装）。
  - **戻り値**: `result=1` が正常（0 はエラー）。`associationMemberCode`（= memberCode）は**数字 10 桁**。`cwsMemberStatus=3` が正会員。エラー時は `result=0` と `errorMsg`/`errorCode`。XML を返せないシステムエラーは HTTP 500。
  - → これまで「チケット形式は仕様書に無い」としていたが、**実際には仕様がある**。許可文字を絞る形式チェックが可能になった。
- **①の修正方針の更新（確定前。実装詳細は coopcdeweb セッションで決める）**:
  - **主たる修正**: `encodeURIComponent(ticket)` で連結する。これだけで traversal は無効化される（`/` が `%2F` になり、Nest/Express は既定でパスセグメント内の `%2F` を区切りに復元しないため `/certif/:ticket` に留まる）。
  - **ガード**: `ticket` が未指定・配列（複数指定）なら未認証扱い。
  - **形式チェック（仕様準拠・多重防御）**: 実チケットは `^[0-9A-Za-z]{40}$`。ただし **stg スタブ `stub-<数字15桁以内>`（1.7.0 の stg 専用機能、`certif.service.ts:207-208`）は frontend を素通りする**ため、stg では `^stub-\d{1,15}$` も許可する必要がある（frontend の APP_ENV で分岐）。ここは実装時に coopcdeweb で確認。
  - **memberCode の確認**: 2 回目の呼び出し前に `^\d{1,15}$`（既存スタブ・DB `VarChar(15)` と同条件。仕様上は 10 桁）。
  - テスト追加（`..` を含むチケットが getBillInfoByMember に到達しないこと）。
- **リリース**: 方針 (a)。①②を **1.8.2** として、調整中の 1.8.1 の prd リリースと一緒に出す。1.4.2 の hotfix は出さない。④（Next 重大脆弱性）も 1.8 系の prd リリースで解消。
- **申し送り（未送信）**: 実装は coopcdeweb、WAF は③不要のため coopinf への依頼は無し。coopcdeweb セッションは未起動のため、承認後に `INBOX_FROM_COOP.md` を置く。

## 2026-11-03 訂正: memberCode の検証は `^\d{10}$`（10 桁）

- **指摘（ユーザー）**: 「memberCode を `^\d{1,15}$` で確認」は 10 桁ではないのか。
- **確認結果**: ご指摘が正しい。frontend が `getBillInfoByMember/${memberCode}` に渡すのは、チケット認証が返す `associationMemberCode` で、認証基盤 外部連携仕様では **10 桁**。DB 列 `member_code` は varchar(15)（`document/database.md:69`、取得元は契約データの「需要家提示お客さま番号」）だが、ここを流れる値は 10 桁。`^\d{1,15}$` は DB 列と stg スタブから借りた緩い値だった。
- **訂正後**: 検証は **`^\d{10}$`**。ただし stg スタブは `stub-<数字>` の数字部をそのまま memberCode にする（例 `stub-1006526` → 7 桁）ため、stg では桁数を固定せず stub の桁を許容する（ticket の形式チェックと同様、frontend の APP_ENV で分岐。実装時に coopcdeweb で確認）。

## 2026-11-03 業務知識: COOP の組合員番号は 10 桁（CDE 需要家提示お客さま番号エリアを流用）

- **ユーザーより**: CDE の「需要家提示お客さま番号」は最大 12 桁。COOP さまはこのエリアを**組合員番号**として利用しており、**COOP さまの組合員番号は 10 桁**。
- → DB 列 `member_code`（varchar(15)）は CDE 由来の器（最大 12 桁）だが、本システムで実際に入るのは COOP の組合員番号＝10 桁。前セクションの「memberCode 検証は `^\d{10}$`」の業務的裏付けとなる。
- （coop に LEARNINGS.md が無いためここに記録。CDE=coopでんき・ガスの契約データ基盤、COOP=コープ生協側。）

## 2026-11-03 チケット形式を実データで裏取り（prd WAF ログ）

- **確認方法**: prd WAF ログ（`aws-waf-logs-coopcde-prd`）の `httpRequest.args` にチケットが残る。チケットは認証情報のため集計のみ行い、値は記録・保存しない（一時ファイルも削除済み）。
- **結果（直近14日）**:
  - 実際のログインのチケットは **`/web/_next/data/<buildId>/members.json?ticket=...`** 経路を通る（Next.js のデータ取得）。`/web/members?ticket=` 直打ちはごく少数（3件、長さ10/15・`stub-`付き）で、正規ログインではなく探索/手動アクセス。
  - `_next/data` 経路のチケット 500 件サンプルは、**全件が 40 桁・小文字16進数（0-9a-f）**。長さ・文字種とも一様。
- **結論**: 認証基盤の仕様（40 桁・半角英数字）は実データと一致。形式チェック `^[0-9A-Za-z]{40}$` は実チケット（40 桁hex＝部分集合）を弾かず、**本番ログインを壊さない**。不正値（短い/記号入り/`stub-`）は正しく弾かれる。これで①の形式チェック導入のリスクは解消。
- **補足**: チケットは `/web/members` と `/web/_next/data/.../members.json` の両方で `getServerSideProps` に渡るが、どちらも同じ `members/index.tsx` を通るため、同ファイルの修正で両経路をカバーできる。

## 2026-11-03 coopcdeweb へ申し送り送付、_next/data 経路の説明

- **決定（ユーザー）**: coopcdeweb への申し送りを進める。
- **送付**: coopcdeweb 直下に `INBOX_FROM_COOP.md`（未追跡・未コミット）を作成。内容は①（encodeURIComponent＋配列拒否＋形式チェック `^[0-9A-Za-z]{40}$`〈stgはstub許可〉＋memberCode `^\d{10}$`〈stgはstub桁許容〉＋テスト）、②（IpGuard localhost 限定、`::ffff:127.0.0.1` を含む、stg実機確認後、別コミット）、リリース(a)（1.8.2 を 1.8.1 と同時、1.4.2 hotfix なし）、③不要。coopinf への申し送りは無し。
- **補足説明（ユーザーへ）**: `/web/_next/data/<buildId>/members.json?ticket=` は Next.js（Page Router）のクライアントランタイムがブラウザ側で出すデータ取得リクエスト（サーバー内部通信ではない）。ALB・WAF を通る。フルロード `/web/members?ticket=` と同じ `getServerSideProps` を通るため、`members/index.tsx` の修正で両経路をカバーできる。WAF の GenericLFI はパス非依存でクエリを見るため両経路で効く。

## 2026-11-03 coopcdeweb から実装完了の申し送り（PR ＃132）、prd バージョンの訂正

- **受信（coopcdeweb-8b より SendMessage）**: 組合員画面の欠陥修正（1.8.2）の実装計画が確定し、実装・手元確認まで完了。**Draft PR #132**（https://github.com/alphacmc/coopcdeweb/pull/132）、ユーザーのマージ待ち。INBOX_FROM_COOP.md は取り込み済みで削除された。
- **重要な訂正（prd のバージョン）**: 申し送り・資料で「prd = 1.4.1」としていたが、**prd は 2026-10-26 から 1.7.0**（frontend・backend とも。ECS `coopcde-prd-task:16` の image タグ 1.7.0 で確認）。欠陥コード自体は 1.7.0 にも存在し、1.8.2 で直すことに変わりはない。
  - **波及**: 1.7.0 の frontend は Next 16.4.2。→ 資料 §4.2 の「Next.js 画像最適化 API の重大脆弱性が prd（1.4.1）に該当」「依存ライブラリ critical 5/high 31」は **prd では既に解消済み**。§1・§4 を訂正した。これらは MFA より先の対応項目ではなくなった。
  - 反省: prd の実バージョンを ECS タスク定義で確認せず、古い 1.4.1 を前提にしていた（横断確認の漏れ）。
- **実装内容（PR #132、1.8.2）**:
  - ① frontend: チケットは `^[0-9A-Za-z]{40}$` のみ通す（stg のみ実行時 APP_ENV で `^stub-\d{1,15}$` も許可）。未指定・配列・形式外は未認証扱いで backend を呼ばない。組合員コードは prd `^\d{10}$`・stg `^\d{1,15}$` で確認。ticket・memberCode とも encodeURIComponent。はじいたら warn（チケット値は記録しない）。**prd 直近30日のログイン 5,343 件はすべて組合員コード 10 桁**で、正規利用者は止まらないことを確認。
  - ② backend IpGuard: `127.0.0.1`/`::1`/`::ffff:127.0.0.1` 以外は 403、拒否時 warn。trust proxy 未設定で XFF 偽装不可。`/certif` にも適用（ユーザー承認済み）。**stg 実測で請求情報 API への request.ip は 661 回すべて `::ffff:127.0.0.1`**。prd・/certif は実測値なしだがタスク定義が stg と同形のため同値のはず。prd の ALB アクセスログ（10/19〜11/03）で外部からの `/api/certif`・`getBillInfoByMember` は 0 件。
  - 手元確認: node:24 で lint・build・テスト（backend 22・frontend 12）成功。Docker で同一ネットワーク名前空間で実機確認（パストラバーサル単純/二重・配列・`_next/data` 経由すべて未認証、prd モードで stub 不可、backend 直叩き＋XFF:127.0.0.1 でも 403）。
- **次の段取り（coopcdeweb）**: 1. ユーザーが PR #132 マージ → 2. stg に 1.8.2 反映 → 3. stg 確認 → 4. 結果を coop に連絡 → 5. 1.8.1 の prd リリースは 1.8.2 として出す（時期はお客様と調整中）。
- **ユーザー判断待ち（範囲外報告）**: サンプルページ `sample/members/[memberCode]` は URL の組合員コードで請求情報を表示する。prd は APP_ENV 判定と WAF で閲覧不可。**残すか削除するかはユーザー判断**。

## 2026-11-03 coopcdeweb 1.8.2 を stg にリリース、coop が stg で無害な結合/セキュリティ確認

- **事実（ユーザー）**: coopcdeweb 1.8.2 を stg にリリース。ECS `coopcde-stg-task:50`、frontend/backend とも image タグ 1.8.2、2 タスク稼働で確認。
- **coop の確認（結合試験担当。無害な GET のみ。存在しない/テスト用コード）**:
  | 入力 | 結果 | 判定 |
  |---|---|---|
  | `stub-1006526` | 307 → `/web/non-contractor` | 認証成功→請求取得へ進む（未契約データのため non-contractor）。**形式チェックは正規スタブを通す＝正規フロー非破壊** |
  | `stub-ng` | 307 → coopデリ | 未認証 |
  | `zzz`（形式外） | 307 → coopデリ | 未認証 |
  | `g`×40（40桁英字） | 307 → coopデリ | 形式は通るが上流認証失敗で未認証 |
  | パストラバーサル（単純） | 403 | WAF が入口で遮断 |
  | 配列 `ticket=a&ticket=b` | 307 → coopデリ | 未認証 |
- **結論**: 不正・悪意入力はすべて安全側（未認証/403）。正規スタブは認証通過で、形式チェック追加が正規ログインを止めていないことを確認。パストラバーサルは WAF が手前で 403 にするため「アプリ形式チェックで弾く」挙動は外部観測不可（coopcdeweb が WAF なし Docker で実証済み）。
- **coopcdeweb への申し送り（機能確認向け）**: `stub-1006526` は stg DB に契約データが無く non-contractor へ転送された。請求明細まで出す機能確認は、契約データのある test identity で coopcdeweb 側に実施してもらう。

## 2026-11-03 PR 整理: ＃21 マージ済み、以降の記録は PR ＃22 へ

- PR #21（MFA 見積もり＋点検＋修正方針）はユーザーがマージ済み。
- push 直後にマージ判明したため、未反映だった stg 確認の記録コミットを新ブランチ `feature/coop-sec-stg-verify-20261103` に移し、Draft PR #22（base main）を作成。旧ブランチ `feature/admin-mfa-estimate` は local/remote とも削除。
- 以降の coop 側の記録追記は PR #22 のブランチで行う。

## 2026-11-03 判断: サンプルページは stg のみ残す／stub 確認は実契約データで／ガードの警告ログを prd 想定で確認

- **決定（ユーザー）**:
  1. **サンプルページ `sample/members/[memberCode]` は stg のみで残す**（削除しない）。1.8.2 は APP_ENV 判定＋WAF で prd では閲覧不可なので、現状の実装どおり＝コード変更不要。coopcdeweb に「残す（stg 限定）」を連絡する。
  2. **stub-xxxxx の機能確認は、実契約のあるデータで行う**（coopcdeweb が契約データのある test identity で請求明細まで確認する）。
- **ガードの警告ログ確認（prd リリース前確認、ユーザー質問）**: 「ticket 形式チェック／IPフィルター(localhost) にかかった時、警告ログは出るか」。
  - **結論: prd でも WARN は出る**（コードで環境別のレベル設定を確認）。
    - backend（NestJS）`apps/backend/src/main.ts:13`: `logger = NODE_ENV!=='prd' ? [error,warn,log,debug,verbose] : [error,warn,log]` → prd は warn 有効・debug 無効。
    - frontend（winston）`apps/frontend/src/lib/logger.ts`: prd は `level:'info'`（warn は info より上位で出力、debug 抑制）。
  - **メッセージ（grep 用）**:
    - frontend 形式チェック `members/index.tsx:56` `[WARN] Invalid ticket format has been rejected.`（memberCode 不正は `:97` `[WARN] Invalid memberCode format has been returned from ticket certification.`）。チケット値は出さない。**stg の CloudWatch で実出力を確認済み**。
    - backend IpGuard `ip-guard.guard.ts:21` `[WARN] IP address:[<ip>] is not allowed to request to <target>`（許可時は `:18` DEBUG。許可IP=`127.0.0.1`/`::1`/`::ffff:127.0.0.1`）。
  - **実機の見え方**（CLAUDE.md「実際の閲覧環境での見え方」）: ロググループ `/ecs/logs/coopcde-{env}-ecs-loggroup`（接頭辞 `-fr`/`-bk`）。stg は DEBUG まで出る（チケット値・会員XMLも）。**prd は DEBUG 抑制で、チケット値・PII（associationMemberCode/XML）は 0 件**＝監査 M-7 は prd には該当しないことも確認。
  - **実観測できなかった点**: IpGuard の reject WARN は、外部から `/api` が WAF で遮断されるため prd/stg で発生させられない。ただしレベル設定上 prd でも出る構成で、coopcdeweb が WAFなし Docker で reject→WARN を実証済み。

## 2026-11-03 決定: 弾いた値もログに出す（サニタイズ＋長さ制限）、coopcdeweb の 1.8.2 stg 確認完了

- **決定（ユーザー）**: チケット形式チェック／組合員コード不正の WARN に、**弾いた値も出す**。形式は **サニタイズ（改行・制御文字除去）＋長さ制限（チケット先頭64文字・組合員コード先頭32文字）**。
  - 根拠: これらの WARN は形式チェックで弾かれた異常値のときだけ出る（正規の有効チケットはこの分岐に来ない）ので、監査 M-7 の「正規の認証情報・PII を残す」懸念には当たらない。値がある方が攻撃内容の把握と誤検知の切り分けに有用。生値のままはログインジェクション・ログ溢れの恐れがあるため、サニタイズ＋truncate を必須とする。
  - **実装は coopcdeweb**。`members/index.tsx` の2か所（`:56` チケット、`:97` 組合員コード）。**PR #132 は既にマージ済み**（下記）なので、本件は follow-up として coopcdeweb に依頼する。版・時期は coopcdeweb が判断。
- **受信（coopcdeweb-8b より）: 1.8.2 の stg 確認が完了、問題なし**。
  - PR #132 マージ済み（11/03 13:15 JST）。stg は 1.8.2（`coopcde-stg-task:50`、frontend/backend とも）。
  - 機能確認（契約データのある組合員コードをスタブで使用。stg DB を読み取り専用で検索し 10 桁・直近 202610 まで請求のあるものを選定）:
    - `stub-2410008437`（でんき・ガス両方）→ 200 表示、両方の契約データあり。
    - `stub-2424666711`（でんきのみ）→ 200 表示、でんき契約データあり。
    - `stub-1006526`（契約なし）→ `/web/non-contractor`（coop の結果と一致）。
    - 公開ドメインと ALB 直接で同結果。
  - 異常系: `stub-ng`→coopデリ（frontend 形式チェックで停止、backend 未呼出）。パストラバーサル→WAF 403。40桁偽チケット→本物の認証 API で失敗しコープデリ（backend は従来どおり ERROR AFE90002）。外部から `/api/certif`・`getBillInfoByMember` 直接→403（WAF）。
  - ログ（stg 直近20分）: IpGuard 許可は /certif 8・請求情報 API 6、送信元すべて `::ffff:127.0.0.1`、拒否 warn 0。frontend の `[WARN] Invalid ticket format has been rejected.` が 4 件。想定外エラーなし。
  - サンプルページ「stg のみで残す」了解。
- **prd リリース**: 1.8.1 は 1.8.2 として出す。時期はユーザーがお客様と調整中。

## 2026-11-03 段取り: 1.8.2 の prd リリースは今晩

- **確定（ユーザー）**: coopcdeweb **1.8.2 の prd リリースは今晩**（2026-11-03 夜）。内容は組合員画面のセキュリティ修正 ①（チケット形式チェック・encodeURIComponent・配列拒否・memberCode 検証）＋②（IpGuard の localhost 限定）。stg で確認済み（機能・異常系・ログとも問題なし）。1.8.1 は 1.8.2 として出す。
- **影響（ログ値追加 1.8.3 との前後）**: ログに弾いた値を出す改修は **1.8.3** の予定で、coopcdeweb は当初「prd リリース前に同梱」としていたが、**今晩リリースのため 1.8.3 は今晩には間に合わない見込み**。→ 今晩は 1.8.2（コアのセキュリティ修正）をそのまま出し、ログ値追加は **1.8.3 の follow-up（後日）** とする整理。1.8.2 自体は WARN は出る（値を出さないだけ）ので、監視・調査の最低限は今晩時点で確保されている。
- **ログ値の truncate 長（16 文字 vs 64 文字）の判断**: 1.8.3 に関わる項目のため、今晩のリリースはブロックしない。引き続きユーザー判断待ち。

## 2026-11-03 変更: ログ値追加も 1.8.2 に含める（今晩のリリースに同梱）

- **決定（ユーザー）**: 「ログ値追加も 1.8.2 に追加する」。→ 先の「1.8.3 で後日」から変更。**今晩の prd リリース（1.8.2）に、弾いた値のログ出力も含める**。
- **影響**: coopcdeweb は、ログ値追加を実装 → stg で再確認 → 今晩 1.8.2 として prd リリース、の流れになる。版の扱い（1.8.2 のまま再ビルドか付番か）は coopcdeweb の判断。
- **要確定（実装前・critical path）**: チケットの truncate 長。coop 推奨は 16 文字（有効チケット40桁を復元させないため）。組合員コードは 32 文字維持。整形（制御文字除去・JSON引用・len表示・配列処理）は coopcdeweb 案どおり。→ ユーザーに最終確認中。

## 2026-11-03 確定: ログ値の truncate はチケット64文字（coopcdeweb 原案）

- **決定（ユーザー）**: チケットの truncate 長は **64 文字**（coopcdeweb 原案）。組合員コードは 32 文字。整形（制御文字 C0/DEL/C1・U+2028/2029 除去、JSON.stringify 引用、元の長さ併記、配列は要素ごと・非文字列は型名）は coopcdeweb 案どおり。
- **残存リスク（ユーザー承知の上）**: 「正規40桁チケット＋末尾ゴミ」のような形式違いのとき、先頭64文字に正規チケット全40桁が残り得る（有効な認証情報の漏えい可能性）。coop は 16 文字を推奨したが、診断性を優先して 64 文字を採用。緩和要因: チケットは有効期限・単回使用、CloudWatch はアクセス制限、WARN は弾かれた異常値のときだけ出る。
- **段取り**: coopcdeweb が実装 → stg 再確認 → **今晩の 1.8.2 に同梱して prd リリース**。版の扱いは coopcdeweb 判断。

## 2026-11-03 訂正: ログ値 truncate 64 文字の「残存リスク」は実質なし（過剰表現だった）

- **指摘（ユーザー）**: 「先頭40桁が正しくても、41文字目が存在する時点で NG（弾かれる）ではないか」。
- **訂正**: 指摘が正しい。前セクションで「64 文字だと正規チケット全40桁が残り得る＝有効な認証情報の漏えい可能性」と書いたが、これは過剰表現だった。
  - このログは形式チェックに**失敗したときだけ**出る。正規の有効チケットは必ず40桁ちょうどで**チェックを通過する**ため、このログ分岐に来ない（＝ログに出ない）。
  - 他人の正規チケットがログに出るには、その人のリクエストが「40桁＋余分」で届いて弾かれる必要があるが、正規フローではそうならない。攻撃者が自分で「40桁＋ゴミ」を送っても、その40桁は攻撃者自身の値で新情報は漏れない。
  - → **他人の有効チケットがこのログ経由で漏れる現実的な経路は無い**。64 文字で問題なし。16 文字推奨の根拠（＝有効チケット復元の防止）も、そもそも有効チケットがここに来ないため不要だった。
- 整形・サニタイズ（制御文字除去＝ログインジェクション対策、長さ上限＝ログ溢れ対策）は引き続き有効な安全策として維持。

## 2026-11-03 coopcdeweb: 弾いた値の WARN 出力を実装（PR ＃133、版は 1.8.2 のまま）

- **受信（coopcdeweb-8b）**: ログ値追加を実装。ユーザー本人にも承認確認済み。**版は 1.8.2 のまま**（新番号にしない、ユーザー決定。ECR の 1.8.2 を上書き）。
- **実装（PR #133、Draft・CI 成功・マージ待ち）**: https://github.com/alphacmc/coopcdeweb/pull/133
  - 出力例: `Invalid ticket format has been rejected. [ticket : "..%2Fx" (len=6)]` / `Invalid memberCode format has been returned from ticket certification. [memberCode : "../admin" (len=8)]`
  - 整形: 制御文字（C0/DEL/C1）・U+2028/2029 除去 → チケット64文字・memberCode32文字で truncate、JSON.stringify で引用＋元の長さ併記、配列は先頭3要素＋count（ログ溢れ対策で追加）・非文字列は型名。
  - テスト 5 件追加（frontend 計17件）、lint・build とも node:24 で成功。
- **段取り**: 1. ユーザーが PR #133 マージ → 2. CodeBuild で 1.8.2 を作り直し（ECR 1.8.2 上書き）→ 3. stg ECS 更新 → 4. stg 確認 → 5. coop に連絡 → 6. 今晩 prd リリース。
- **留意（記録のみ）**: 同じタグ 1.8.2 を上書きするため、「stg で確認した 1.8.2」と「prd に出る 1.8.2」は中身が更新版になる。追跡性の観点では注意だが、ユーザー決定。stg 再確認で担保する。

## 2026-11-03 coop 独立確認: 作り直した 1.8.2 の stg でログ値出力が正しく動作（prd 前最終確認）

- **coopcdeweb より**: 作り直した 1.8.2 の stg 再確認完了・問題なし。ビルドと stg リリースはユーザー実施（ECS デプロイ完了 15:02 JST）。stg 稼働イメージ digest: frontend `sha256:e638…634f`、backend `sha256:8e62…306a`。prd リリース後、prd タスクがこの digest と一致するか照合予定。
- **coop 独立確認（結合試験担当、無害 GET のみ、2026-11-03）**:
  - stg 稼働タスク2つのイメージ digest が上記報告値と**一致**を確認。
  - WARN の値出力を実機 CloudWatch で確認（frontend ストリーム）:
    - `stub-ng` → `[ticket : "stub-ng" (len=7)]`
    - CRLF 注入 `abc\r\n[ERROR] fake` → `[ticket : "abc[ERROR] fake" (len=17)]`（**改行除去で1行維持＝ログインジェクション無効化**、len は元長保持）
    - 100文字 → 64文字に truncate、`(len=100)` 併記
    - 配列（coopcdeweb テスト）→ `["stub-1"(len=6), "stub-2"(len=6), "stub-3"(len=6)] (count=4)`（先頭3＋count）
  - いずれも未認証（307）で安全側。サニタイズ・truncate・配列処理とも設計どおり。
- **結論**: 今晩の prd リリース可。prd リリース後は coopcdeweb が prd タスクの digest 照合を実施予定。

## 2026-11-03 完了: 組合員画面セキュリティ修正（1.8.2）を prd リリース、coop 独立確認済み

- **prd リリース完了（coopcdeweb より＋coop 独立確認）**: ユーザーが実施。prd タスク定義 `coopcde-prd-task:17`、タスク起動 15:12 JST・デプロイ完了 15:15 JST。1.8.1 の単価修正・新単価も同梱。
- **イメージ照合**: prd 稼働2タスクの digest が stg と一致（frontend `sha256:e638…634f`、backend `sha256:8e62…306a`）。coop 側でも prd タスクの digest 一致を確認。ALB ターゲットも healthy。
- **coop 独立確認（prd、無害 GET）**: スタブ `stub-9999999999` → 307 コープデリ（prd では stub 無効＝未認証）。パストラバーサル → 403（WAF）。
- **coopcdeweb の prd ログ（起動〜15:17 JST）**: ERROR 0、IpGuard 拒否 0、正規ログイン 1。外部からの `/api/certif`・`getBillInfoByMember` 直叩きは 403（WAF）。スタブは未認証で WARN が1行（例 `[ticket : "stub-2410008437" (len=15)]`）。
- **タグ**: coopcdeweb が `1.8.2`（#133 マージ）を付与。付け漏れていた `1.8.1` も付与。
- **これで、組合員画面のパストラバーサル欠陥（他人の請求情報閲覧）とその多重防御（IpGuard localhost 限定）、および弾いた値の WARN ログ化が、prd で有効化された。** MFA（保留中）とは別件として先行対応が完了。

## 2026-11-03 MFA 見積もりの再開（prd=1.8.2 を反映、前提の制約を解消）

- **依頼（ユーザー）**: MFA 見積もりの再開。
- **最大の変化**: prd が 1.8.2 になったため、資料にあった「**1.8 系の prd リリースが先**」という前提（旧: prd=1.4.1/1.7.0 を想定）が**解消**。MFA は現行 prd（1.8.2、Next16/Nest11/Prisma7）の上に直接着手できる。
- **管理者側「同時対応」項目の現状（coopcdeweb origin/main = prd 1.8.2 で確認、2026-11-03）**: いずれも**未修正**（1.8.2 は組合員側の対応で、管理者側は対象外だった）。
  - change-pass-inlogin が `body.loginId` 使用（`admin.controller.ts:67`、H-3）。
  - 管理 API にロール判定なし（`@UseGuards(AuthGuard('jwt-admin'))` のみ、H-2）。
  - JWT `validate` が削除済み・権限を確認しない（`strategy/jwt.strategy.ts`、存在確認のみ）。有効期限 5h（`admin-auth.service.ts:46`。期限切れ自体は `ignoreExpiration:false` で拒否）。
- **資料の更新（`support/admin_mfa_estimate.md`）**: §1 リリースの土台を 1.8.2 に・前提解消を明記、§2 Cognito の「1.4.1 でも可」記述を一般化、§3 推奨から「1.8 系を先に」を削除し、同時対応3項目が prd で未修正である旨を明記。
- **推奨は変わらず**: 方式1（アプリ内 TOTP）＋同時対応で **8〜11 人日**。お客様確認事項（認証アプリ可否・管理者人数・紛失時の運用）は未回答のまま。
- **次の方向性は未確定**（ユーザーに確認中）: (a) お客様向けの見積もり文書に仕上げる、(b) お客様確認事項を先に確認、(c) 方式を決めて実装計画へ。

## 2026-11-05 管理画面 MFA: パスキーを「将来候補」からお客様の判断に委ねる選択肢へ

- **方針変更（ユーザー）**: パスキー（WebAuthn）は `support/admin_mfa_estimate.md` で「将来候補」としていたが、**お客様に判断していただくため、端末紛失時の復旧策を含めた工数を出す**。
- **算出した工数（資料に反映済み）**: 合計 **12〜16 人日**（本体 9〜12 ＋ 復旧策 3〜4）。同時対応（ロール判定・`change-pass-inlogin`・JWT 確認、+2〜3）は別枠。
  - 本体: DB（パスキー用の新テーブル、coopbatch マイグレーション）1〜1.5 ／ backend（2 段階ログイン・登録と認証の処理・RP ID と origin の環境別設定・パスキー管理 API）3〜4 ／ frontend（2 段階目・初回登録・パスキー管理画面）2〜2.5 ／ 端末・ブラウザ互換確認 1 ／ WAF 0.25 ／ 試験・リリース・手順書 2〜2.5。
  - 復旧策: ① 2 台目の登録を推奨（1 台だけなら警告）0.25 ／ ② リカバリーコード（使い捨て 10 個、ハッシュ保存）1〜1.5 ／ ③ 管理者によるリセット＋短期限の再登録リンク（別経路で渡す）1〜1.5 ／ 復旧の試験・手順書（全員が締め出されたときの DB 直接操作を含む）0.75〜1。②を省くと −1〜1.5。
  - お客様に確認すること: 管理者が使う端末、同期パスキー（個人の Apple ID・Google）を社内規程で認めるか、物理セキュリティキーを購入できるか、管理者の人数。
- **SES の登録範囲（質問への回答）**: 認証するのは送信元（ドメイン全体か、アドレス 1 件）で、宛先の管理者を一人ずつ登録するものではない。ドメイン認証はお客様 DNS に DKIM の CNAME 3 件（サブドメインに絞る方法もある）。サンドボックス解除は AWS アカウント単位（リージョンごと）で 1 回。サンドボックスのままだと宛先も認証済みに限られるが、管理者が全員認証済みドメインのアドレスなら解除申請は不要にできる可能性がある。coopinf に Route 53 のホストゾーンは無く、DNS はお客様の管理という前提。
- **反映（ユーザー了承）**: 上記を `support/admin_mfa_estimate.md` に反映した（方式表のパスキー行と SES の記述、「5. パスキーの内訳」節、お客様への確認事項）。
- **お客様向けスライドを作成（ユーザー依頼）**: https://claude.ai/artifact/Epfsd7Mt82qRrnU9JKynA4（全8枚、非公開。お客様に見せるには共有設定が必要）。方式・概要・概算工数・評価を表にまとめる。社内向けの脆弱性の詳細（監査の指摘番号・組合員画面の件）は載せず、同時対応は「権限まわりの強化」として表現する。

## 2026-11-05 管理画面 MFA: ②Cognito 前段案の位置づけと、認証を Cognito に一本化する案（⑥）の提起

- **②の確認**: ②は Cognito 自体が MFA（ユーザープールで TOTP 必須）で、その後ろに既存のパスワードログインが残る構成。資料・スライドの表記（「AWS Cognito 連携」「専用ログイン画面の後に既存のログイン」）ではパスワード認証を 2 回重ねただけに見えるとユーザーから指摘あり。表記の修正案は提示済みで、反映はユーザーの判断待ち。
- **方針の提起（ユーザー）**: 「本システムの認証を AWS Cognito に寄せるべきではないか」。
  - 提示した⑥案: 管理画面のログインを Cognito（managed login、日本語対応）に一本化する。アプリは Cognito のトークンを検証して `admin_user`（権限・有効期限）と対応付ける。アプリのパスワードログイン・パスワード変更は廃止する。MFA は TOTP・メール・パスキー（Essentials 以上）から設定で選べる。管理者数名なら無料枠（10,000 MAU）の範囲内。
  - 概算 9〜12 人日（粗い見積もり。CF 2〜3 ／ backend 2.5〜3.5 ／ frontend 1.5〜2 ／ 管理者移行と手順書 1 ／ 試験・リリース 2）。同時対応はロール判定と JWT まわりだけで +1.5〜2 程度。
  - 注意点: 既存のパスワードハッシュは移行できないので仮パスワードを再発行する。ユーザー管理画面から Cognito の API を呼ぶ改修が要る。stg と prd でプールを分ける。AWS への依存が強まる。
- **未決（ユーザー判断待ち）**: ⑥を資料とスライドに追加するか。②を残すか、外すか。推奨を①と⑥のどちらにするか。⑥を採用する場合は、coopinf・coopcdeweb・coopbatch の各セッションと内訳を詰める。

## 2026-11-05 管理画面 MFA: ⑥（Cognito 一本化）を追加し、②（Cognito 前段）を外す

- **決定（ユーザー）**:
  1. **Cognito 一本化案を資料とスライドに追加する（OK）。**
  2. **②「ALB 認証 + Cognito（前段だけに MFA、既存のパスワードログインを残す）」は外す。**
- **反映**: 方式の番号を振り直した（1 認証アプリ TOTP／2 メール／3 SMS／4 パスキー（自前実装）／5 Cognito 一本化）。
  - `support/admin_mfa_estimate.md`: 方式表から旧 2 を除き、除外の理由を注記した。旧 2 の内訳の節は削除した（見積もり 5〜7 人日は git 履歴に残る）。「5. 認証を Cognito に一本化する案の内訳」（9〜12 人日、同時対応 +1.5〜2）を追加し、推奨と確認事項も更新した。
  - スライド（https://claude.ai/artifact/Epfsd7Mt82qRrnU9JKynA4）: 比較表を差し替え、⑤の説明スライドを追加した（全 9 枚）。推奨スライドに「パスキーをご希望なら ⑤（10.5〜14 人日）」を追記した。確認事項に⑤（AWS への依存を許容するか）を加えた。
- **未決**: 推奨を①と⑤のどちらにするかは、お客様の回答（パスキーの希望、AWS 依存の許容）を見て決める。

## 2026-11-05 管理画面 MFA: 方式を「A. 現在のユーザー管理機能を使う」「B. 認証を Cognito に寄せる」の 2 つの方向に分けて示す

- **依頼（ユーザー）**: 現在のユーザー管理機能を使う案と、Cognito に寄せる案の分かれ目が分かるようにしてほしい。
- **反映**:
  - `support/admin_mfa_estimate.md`: 「2. 方式別の概算」の冒頭に A と B の比較表を加えた（ログイン画面、ID・パスワード、MFA、権限・有効期限、管理者の登録・削除、工数、移行時の利用者への影響、依存）。方式表には A（1〜4）と B（5）の区切り行を入れた。
  - スライド: 3 枚目に「2つの方向性」（A／B の 2 枚カード）を追加し、全 10 枚になった。比較表に「区分」列（A／B、B の行は色を変える）を加えた。各スライドの見出しを A-④・B-⑤・A-② のように区分付きにした。同時対応のスライドには「B では +1.5〜2」を注記した。

## 2026-11-06 WAF ブロック情報の確認と、日次ダイジェストの仕組み化（方式A・設計）

- **依頼（ユーザー）**: WAF のブロック情報を確認。情報漏洩が頻発する昨今、**毎朝・日次で確認したい**。
- **prd WAF ブロック確認結果（直近7日、2026-11-06）**: 総数の大半は無差別ボットの背景ノイズ（IpReputation 3604 / CommonRuleSet 1683 / KnownBadInputs 488 / Linux 150）で managed ルールが遮断。要点:
  - 実管理ログイン `/web/admin/login` への攻撃は国外(US)からの3件のみ、すべて **AdminGeoRestrict** で遮断。
  - レート制限（Login/AdminSensitive/ApiRateLimit）の発動は **0 件**（総当たりの痕跡なし）。
  - ApiAllowList 82 件はすべて無関係なボット探索で、**実エンドポイント（/api/certif・getBillInfoByMember・/api/admin）を狙ったものは0件**。
  - → MFA 資料には追記しない（ユーザー判断「確認だけで十分」）。
- **決定（ユーザー）**: 毎朝の WAF 確認を **方式A（AWSネイティブ日次通知）** で仕組み化する。パラメータ: **毎朝 7:00 JST**・**prd のみ**・通知先は**既存アラートと同じ宛先**（coopcdealert の SNS→メール）。
  - 不採用: クラウドの定期エージェント（/schedule）＝お客様 AWS の WAF ログにアクセスできず毎朝失敗するため不可。ローカル定期タスク＝SSO 期限切れで無人実行が不安定のため見送り。
- **設計（coop）**:
  ```
  EventBridge Scheduler（cron(0 7 * * ? *), Asia/Tokyo）
    → Lambda（CloudWatch Logs Insights で aws-waf-logs-coopcde-prd を過去24h集計）
    → SNS（既存トピック）→ 担当者へメール
  ```
  - 既存資産を流用: coopinf `cf/lambda-evb-cf.yaml` の EventBridge Scheduler（Asia/Tokyo 指定の実績、`coop-batch-send-alarm`）、coopcdealert の SNS→メール経路。
  - メール内容: (1) 24h ブロック総数＋ルール別内訳（上位）、(2) 要注意シグナル＝レート制限発動>0／`/web/admin/*` への AdminGeoRestrict（国別）／実エンドポイント（/api/certif・getBillInfoByMember・/api/admin/*・/web/admin/*）へのアクセス／`/web/members` の `..`(GenericLFI)／前日比急増。要注意が1件でもあれば件名・冒頭に ⚠ を付けて目立たせる。
  - 時刻・TZ は既存 Scheduler と同様に `ScheduleExpressionTimezone: Asia/Tokyo` を使う（UTC 換算は 22:00 UTC 前日だが、TZ 指定で `cron(0 7 * * ? *)` と書ける）。
- **実装は coopinf**（CF: Scheduler＋Lambda＋IAM、SNS は既存流用）。coopinf セッション未起動のため `INBOX_FROM_COOP.md` で申し送る。結合確認（通知が届くか・要注意シグナルの検知）は coop が担当。

## 2026-11-06 coopinf 進捗: ALB 監視③（SensitivePathBlock, Count）＋prd 5xx アラーム適用、WAF 日次ダイジェストは後続

- **受信（coopinf-68）**: Draft PR alphacmc/coopinf#55 で stg・prd へ適用（stg 11:59 JST、prd 12:04 JST。prd 変更セットはユーザー実行）。記録は coopinf `conversations/2026-11-06.md`・`cf/waf-settings.md`。
- **③ WAF ルール `coopcde-<env>-SensitivePathBlock`（Priority 8、prd・stg、いまは Count）**:
  - (a) アプリ入口（`^/web(/|$)`・`^/api/`・`^/$`・favicon・apple-touch-icon・robots.txt）以外のパスを遮断対象。
  - (b) 先頭ドットの区切り（`/.env`・`/.git/` 等）と機微な拡張子（env/bak/zip/sql/pem/php/yml 等）は `/web`・`/api` 配下でも遮断対象。
  - 照合前に URL_DECODE → NORMALIZE_PATH → LOWERCASE。Count/Block はパラメータ `SensitivePathBlockAction` で切替。
- **①② prd のみの ALB 5xx アラーム**: 5 分で 5 件以上 → prd エラー通知 SNS（`coopcde-send-error-alart-topic-prd`）。`coopcde-prd-alb-Target5XX`・`coopcde-prd-alb-ELB5XX`。stg は停止中 503 の誤報回避のため作らない。
- **確認結果**: Target5XX は OK でメトリクス取得、ELB5XX は 5xx 0 件で INSUFFICIENT_DATA（異常ではない）。正規表現はサンプル URI で検証（正規11許可／スキャン11遮断）。Next16/Nest11 の内部 URL（`/web/_next/static・image・data`）にドット始まり区切りなし。未確認: ③に実通信が当たったか（ログ未到着）、stg テスト送信（手元から ALB に届かず）。③の当たり方は 11/9 前後まで WAF ログで観察。
- **注意（設計影響）**: `/.well-known/` も遮断対象（現在未使用、使うなら例外追加）。③を Block にすると 404 相当のスキャンも遮断数に乗り、`waf-ALL` アラーム（IpReputation 除く遮断が 5 分 500 件以上）の発報が増える可能性。
- **WAF 日次ダイジェスト（coop 依頼分）**: ブランチ `feature/waf-daily-digest`・Draft PR #54 で後続実装。**要注意シグナルに③の遮断件数も含める**（coopinf 提案、妥当として coop も合意）。prd 投入後に coopinf から連絡 → **手動実行で通知1回を出し、coop が結合確認**する段取り。
- **段取り**: 1. 11/9 前後まで③の当たり方を観察（日本からの正規利用が当たっていないか）→ 2. ユーザーの go で stg→prd の順に③を Block 化 → 3. 日次ダイジェスト実装 → 4. prd 投入後に結合確認。
