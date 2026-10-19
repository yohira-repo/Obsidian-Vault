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
