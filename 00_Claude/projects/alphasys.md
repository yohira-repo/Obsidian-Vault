# alphasys 作業ログ

## 2026-09-30 メニューレイアウト統一の方針承認

`feature/menu-unification-prototype`（PR #163）で試作した `/sales/customer` を実機確認。

- 確認結果: 動作ボタンの右寄せ配置、左のBusinessNav（業務メニュー）の階層化（営業メールの2階層常時展開）ともに問題なし
- **承認**: この案（M-1〜M-5: `src/config/menu.ts` にメニュー定義集約、`BusinessNav`/`PageHeader` への分離）の方針で、残り52画面へ展開を進める
- 補足: ユーザーより「他にも階層化すべきところがある」との指摘あり。対象画面は未特定。次回、対象一覧の洗い出しが必要

## 2026-09-30 残り52画面の棚卸しと方針決定

Exploreエージェントで残り52画面（`/sales/customer`系3件を除く全`page.tsx`）を棚卸し。結果を踏まえてユーザーが以下を決定。

1. **`/member/employees` のリンク切れ**（menu.tsの「社員情報」項目とルートが指す先が実体なし）: 今回は対応せず、**別の残タスクとして整理する**（やらないことの決定ではなく、優先度を下げて後回しにする決定）
2. **`src/app/customer/page.tsx`**（初期デモ用のハードコードされた取引先一覧、`/sales/customer`と主題重複）: **削除を承認、実施済み**（PR #163、コミット46784e7）
3. **Sidebar実装パターンの例外3画面**（`manager/dc`, `manager/employee-info`一覧, `member/skills`一覧。専用Sidebarを持たず操作ボタンがテーブル行/Content直書き）: **例外扱いにせず、他の一覧画面と同様にBusinessNav/PageHeaderへ統一する方針を承認**
4. **`member/skills/infoset`（追加スキル項目マスタ）を「技術経歴管理」の子メニューとして2階層化する案**: **承認**

次のアクション: 上記の方針に沿って、残り52画面への展開作業を進める（`/member/employees`のリンク切れ対応は別タスクとして後日着手）。

## 2026-09-30 展開作業中に判明した仕様の決定（division着手時）

`/sales/customer`以外の画面へ展開する過程で、既存画面の見出し実装にばらつきがあることが判明し、以下を決定。

1. **`PageHeader`のtitleをstring→ReactNodeに変更**し、各画面で共通の`<Title>`コンポーネント（緑の左ボーダーの`<h1>`）を渡す方式に統一（承認: PageHeader素のh2ではなく、既存の`<Title>`を維持する案を採用）
2. **`LaborCostTitle`/`LaborCostSettingTitle`のような画面固有の見出しコンポーネント**（青下線・中央寄せ）も**共通`<Title>`に統一**する方針を承認（見た目が変わることを許容）

進捗: `division`業務エリア（7画面: 部門一覧/追加/編集、人件費原価一覧/設定、部門メンバー一覧、社員所属先一覧）の展開完了。残りは manager(8)/member(10)/sales(19程度)。

## 2026-09-30 manager業務エリア完了・新たなリンク切れ発見

manager業務エリア（8画面）の展開完了。あわせて発見事項:

- `/manager/employee-info/skills`（社員一覧の「業務経歴書一覧」ボタンのリンク先）も実体の無いルート。`/member/employees`と同じ**リンク切れ**。既存動作を変えない方針のためボタンはそのまま維持し、`/member/employees`と合わせて後日まとめて整理する対象とする
- `manager/page.tsx`・`member/page.tsx`（各業務トップ）は、SidebarがBusinessNavと完全に重複する内容だったため、BusinessNavのみのシンプルな構成に変更（ユーザー承認済みの「例外扱いせず統一」方針の範囲内と判断し、個別確認はせず実施）

## 2026-09-30 member業務エリア完了・役割表示の差異

member業務エリア（10画面）の展開完了。あわせてmenu.tsに承認済みの2階層化（技術経歴管理→情報設定）を反映。

- 発見事項: 「情報設定」（`/member/skills/infoset`）はADMIN専用機能で、旧SidebarはUSERには表示していなかった。新しいBusinessNavはロールに応じた出し分け機能を持たないため、USERにもメニュー項目自体は見えてしまう（クリックするとページ側の`confirmAdmin()`で権限エラーになるため、アクセス制御自体は保たれている）。表示範囲が広がる差異として記録。対応要否は未確認
- 進捗: division(7)・manager(8)・member(10)完了。残りはsales(約19画面)

## 2026-09-30 sales/page.tsxのデモコード削除承認

`src/app/sales/page.tsx`（売上仕入管理の業務トップ）が`src/app/customer/page.tsx`と同種の、ハードコードされたダミー請求データを表示するだけの初期デモ画面と判明。

- **承認**: 削除してBusinessNavのみのシンプルな業務トップ構成にする（実施済み、コミット9e05098）
- 進捗: sales/bill（請求管理、3画面）も展開完了。残りはsales/project(4)・sales/contract(6)・sales/customer/add・edit(2、M-5試作時は一覧のみ対応だったため残っていた)・sales/member(2)

## 2026-09-30 全52画面のメニューレイアウト統一 完了

sales/bill(3)・sales/project(4)・sales/contract(6)・sales/customer/add,edit(2)・sales/member(2)の展開も完了し、`/sales/customer`以外の**全52画面**でBusinessNav+PageHeaderへの統一が完了した(PR #163)。jest 16スイート/126テスト、vitestの非DB依存テストとも既存の合格状態を維持（DB依存のpage.vitest.tsx系はローカルに.env.test/実DBが無いための元々の失敗で、今回の変更とは無関係）。

追加で見つかったリンク切れ（`/member/employees`、`/manager/employee-info/skills`と合わせて後日まとめて整理する対象）:
- `/sales/customer/edit/[customerNo]`の「プロジェクト一覧」→`/sales/project/{customerNo}`、「請求一覧」→`/sales/bill/{customerNo}` はいずれも実体の無いルート（正しくは`/sales/project/edit/[projectId]`等）。既存動作維持のためボタンはそのまま残置

次のアクション（未着手・別タスク）:
1. リンク切れ3件（member/employees、manager/employee-info/skills、sales/customer/edit内の2リンク）の整理
2. 今回の展開の実機確認（特にAWS/Google連携など認証が必要な画面は本セッションでは表示確認していない）

## 2026-09-30 メニューレイアウト統一（PR ＃163）stagingマージ完了

ユーザーが実機確認の上、`staging`ブランチへマージ済み。全52画面の展開作業はここで完了。
