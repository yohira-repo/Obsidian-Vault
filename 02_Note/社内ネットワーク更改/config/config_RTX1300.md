# YAMAHA RTX1300 コンフィグ

- 設計根拠：[[社内LANネットワーク設定]]（3. IPアドレス設計）
- 関連：[[config_XG-200KI]] / [[config_XS508TM]] / [[切替・障害切り分け手順]]
- 移植元：[[現行config棚卸し]]（RTX1200 / PPPoE からの引き継ぎ判定）

> **前提**：XG-200KI（HGW）配下 ／ IPv6は **RA方式** ／ 社内は **IPv4のみ** ／ VLAN ID は **10・20・30**

---

## 0. プレースホルダ一覧（投入前に確定させる値）

| プレースホルダ                         | 内容                                                                                                           | 入手先                      |
| ------------------------------- | ------------------------------------------------------------------------------------------------------------ | ------------------------ |
| `<LOGIN_PASS>` / `<ADMIN_PASS>` | ログイン／管理者パスワード                                                                                                | 社内                       |
| `<GLOBAL_IP>`                   | 固定グローバルIPv4（＝「お客さまネットワークアドレス(IPv4)」）。NAT外側は `map-e` で自動適用。値は §8フィルタ・§10/11 IPsec local address で使用 | **OCN固定IP設定情報** |
| `<AR_URL>`                      | アドレス解決システム FQDN URL（Lua `SERVER_URL`）                                                                        | **OCN固定IP設定情報** |
| `<AR_ID>` / `<AR_PASS>`         | アドレス解決システム 認証用共通ID／パスワード（Lua `USERNAME`／`PASSWORD`）                                                          | **OCN固定IP設定情報** |
| `<AR_HOST>`                     | アドレス解決用ホスト名（Lua `HOSTNAME`）                                                                                  | **OCN固定IP設定情報** |
| `<BR_IPV6>`                     | BR IPv6アドレス（map-eのBorder Relay。確認用。明示指定要否は公式固定IP例で確認）                                                       | **OCN固定IP設定情報** |
| ~~`<IF_ID>` / `<TUNNEL_DST>`~~  | ~~旧ipip方式の値~~ **map-e方式では不要（通知もされない）**                                                                     | —                        |
| `<DNS1>` `<DNS2>`               | **確定**：OCN指定DNS（東日本）優先＋パブリックDNSをフォールバック → 6章参照（`210.145.254.170` / `125.170.93.234` / `8.8.8.8` / `1.1.1.1`） | OCN_settei_Ver1.7        |
| `<MAC_xx>`                      | DHCP予約対象PCのMACアドレス                                                                                           | 実機確認                     |
| `<L2TP_PSK>`                    | L2TP/IPsec 事前共有鍵                                                                                             | 社内                       |
| `<VPN_USER_x>` / `<VPN_PASS_x>` | VPNユーザー名・パスワード                                                                                               | 社内                       |
| `<AWS_*>`                       | AWS VGW の対向IP・PSK・BGP情報                                                                                      | **今回のスコープ外**（→ 11章。事後対応） |

---

## 1. 基本設定

> **最初に管理者モードへ。** 通常モード（プロンプト `>`）では設定コマンドを受け付けません（`login password`→「Invalid command name」、`administrator password`→「Administrator use only」）。まず `administrator` を実行し、`Password:` に現在の管理者パスワード（**工場出荷時は空＝Enterのみ**）を入力。プロンプトが `#` に変わったら以降の設定コマンドを投入します。

```
administrator          # → Password: 現在の管理者PW（工場出荷時は空＝Enterのみ）。以降 # プロンプト
console character ascii
console lines infinity
timezone +09:00
```

> **RTX1300はユーザー名方式（従来の無名 `login password` は非対応）。** 初期ユーザーは `admin`／初期PW `admin` で、初回ログイン時に変更必須。ログインは以後この `admin` ユーザー（変更後PW＝`<LOGIN_PASS>` 相当）を使用します。
> - 追加の一般ユーザーを作る場合（対話入力）：
>   ```
>   login user <ユーザー名>
>     New_Password: <LOGIN_PASS>
>     New_Password: <LOGIN_PASS>   （再入力）
>   user attribute <ユーザー名> administrator=2   # 管理権限も与える場合
>   ```
> - 昇格（管理者）パスワードは対話入力：
>   ```
>   administrator password
>     Old_Password:                （現在の管理者PW。初期は空＝Enter）
>     New_Password: <ADMIN_PASS>
>     New_Password: <ADMIN_PASS>   （再入力）
>   ```
> ※ パスワードは同じ行に書けない（`login password <PW>` はRTX1300で「コマンド名を確認してください」）。画面にPWは表示されません。事前ハッシュがあれば `login user <名> encrypted <hash>` 等の1行指定も可。

---

## 2. フレキシブルLAN/WANポート

```
# 工場出荷時の割り当て（LAN1=物理1-8 / LAN2=物理9 / LAN3=物理10）をそのまま使用するため
# lan flexible-port コマンドの投入は不要。
# 変更する場合は save + restart が必要（切替当日の変更は避けること）
```

---

## 3. インターフェース

### 3-1. LAN1：保守セグメント

```
ip lan1 address 192.168.200.1/24
```

### 3-2. LAN2：WAN（XG-200KI LAN4 と接続）

```
# ★ HGW(XG-200KI)配下のため RA方式でIPv6取得。dhcp-prefix@(PD) にすると IPv4 が通らない
# ★ map-e方式：IF_ID等の直書きはしない（WAN側IPv6はRAで取得し、アドレス解決Luaで登録）
ipv6 lan2 address ra-prefix@lan2::1/64
ipv6 lan2 dhcp service client ir=on
```

> **最重要**：`ra-prefix@lan2` を `dhcp-prefix@lan2` にしないこと。HGW配下ではDHCPv6-PDでプレフィックスを取得できず、MAPルール／トンネルが成立せず **「IPv6は通るがIPv4が全く通らない」** 状態になります（→ [[切替・障害切り分け手順]] 5-1）。
>
> **OCN公式の裏付け（2026-09-09 突き合わせ）**：`OCNIPoE_v1.1.pdf` に「（フレッツ光クロス対応レンタルルータ）配下にIPoE対応ルーターを接続するとIPv6配布方式が**RA方式に変換される**」と明記。※同資料は当時の機種名として **XG-100NE** を名指ししているが、**当社のレンタルルータは後継の XG-200KI（同一の光クロスHGW系列）**であり、HGW配下という構造は同一のため **RA方式が同様に適用**される。RA方式は本設計の独自判断ではなく **OCN公式準拠**です（→ [[OCN_DOC突き合わせ結果]] #1）。

### 3-3. LAN3：コアスイッチ幹線（タグVLAN）

```
vlan lan3/1 802.1q vid=10
vlan lan3/2 802.1q vid=20
vlan lan3/3 802.1q vid=30

ip lan3/1 address 192.168.128.1/24
ip lan3/2 address 192.168.64.1/24
ip lan3/3 address 192.168.192.1/24
```

---

## 4. map-eトンネル（OCN固定IP1／アドレス解決システム）

> **方式**：OCN光「フレッツ」IPoE クロス 固定IP1 は **map-e**。固定IPv4はOCNの**アドレス解決システム**へ、**YAMAHA公式LuaスクリプトでルータのIPv6を登録**して適用する（開通情報の URL/ID/PW/ホスト名 をLuaに設定）。手動ipip（対向・IF_ID直書き）は使わない。
> 出典：rtpro OCNバーチャルコネクト対応機能（map-e／固定IP・アドレス通知Lua）／Luaスクリプト機能。
>
> [!important] 確定方法＝**Web GUI かんたん設定ウィザード**で生成するのが確実（下記CLIは参考／バックアップ）
> WAN/OCN固定IP1（map-e・アドレス解決Lua・IPv6方式）は細部が機種ファーム/トポロジ依存で、公開情報だけでは断定しきれない（RA/PDの記述揺れあり）。**RTX1300のWeb GUIウィザード（OCNバーチャルコネクト／固定IP1）に開通情報を入力して自動生成**させ、それを正とする。
> - **要OCN確認（最重要）**：本構成は **ONU→XG-200KI(HGW)→RTX1300** の**HGW配下**。HGWがPDを取得しRTXへRA広告＝**RTXはRA方式**（OCNIPoE_v1.1でも配下ルータ構成=可）。ただしYAMAHAの光クロスウィザードは「ひかり電話あり→PD」等**RTX直結前提の表現**があり紛らわしい。「光クロス＋XG-200KI配下＋RTX1300＋OCN固定IP1でRTXはRAか／ウィザードのどの選択肢か」を **OCN設定サポート 0120-047-644（ガイダンス【4】）／tech-support@ntt.com** に確認する。
> - ウィザード生成後、§8の `ip tunnel secure filter` 適用と固定IPv4値（§8/§10）をCLIで整合させる。

```
tunnel select 1
 tunnel encapsulation map-e
 tunnel map-e type ocn
 ip tunnel mtu 1460
 ip tunnel tcp mss limit auto
 ip tunnel nat descriptor 1
 tunnel enable 1

ip route default gateway tunnel 1
```

### 4-1. アドレス解決システムへの登録（OCN公式Lua）

**`ocn_address_notification.lua` は YAMAHA rtpro 公式のものをそのまま配置**し、冒頭変数に開通情報を設定する（**自作しない・本ファイルに全文は載せない＝改変防止**）。

```
schedule at 1 startup * lua emfs:/ocn_address_notification.lua
```

Lua冒頭変数と開通情報の対応：

| Lua変数 | 開通情報の項目 | 設定値 |
|---|---|---|
| `SERVER_URL` | アドレス解決システム FQDN URL | `<AR_URL>` |
| `USERNAME` | 認証用共通ID | `<AR_ID>` |
| `PASSWORD` | 認証用共通パスワード | `<AR_PASS>` |
| `HOSTNAME` | アドレス解決用ホスト名 | `<AR_HOST>` |
| `IPv6_IF` | WAN側インターフェース | `"LAN2"` |

> **要検証（実機投入時に公式固定IP例と突き合わせて確定）**：
> 1. **BR IPv6アドレス（`<BR_IPV6>`）** の明示指定要否（`tunnel map-e type ocn` はOCNのBRを内蔵想定。固定IPで別指定が要る場合あり）。
> 2. **HGW配下（RA方式）でのmap-e成立**と `ipv6 lan2` の正確な行（`ra-prefix@` か `address dhcp`）。OCN固定IPの公式例に合わせる。
> 3. Luaスクリプト本体はrtpro公式版を使用（4変数のみ設定）。

---

## 5. NAT（固定グローバルIPでのNAPT）

```
nat descriptor type 1 masquerade
nat descriptor address outer 1 map-e          # 固定IPv4は map-e で自動適用（= <GLOBAL_IP> と一致）
nat descriptor address inner 1 auto
```

> **固定IPv4（`<GLOBAL_IP>`）の“値”は §8（VPN終端フィルタ）・§10/11（IPsec local address）で使用**します（NAT外側自体は `map-e` で自動）。

> **Web公開（現行の `192.168.128.128` への www/https）は今回移植しません。** サーバ群はAWSへ移行済みで、公開環境は新構成に合わせて別途検討する方針です。必要になった時点で以下を追加します。
> ```
> nat descriptor masquerade static 1 301 <公開サーバIP> tcp www
> nat descriptor masquerade static 1 302 <公開サーバIP> tcp https
> ```

---

## 6. DNS

```
# ★ 自動設定の "dhcp lan2" は使わない（HGWをDNSサーバとして参照し名前解決に失敗する既知事象の回避）
# DNSは OCN指定（東日本）を優先し、パブリックDNSをフォールバックに併記（社内はIPv4のみ運用）
#   OCN指定：210.145.254.170 / 125.170.93.234（OCN_settei_Ver1.7）
#   フォールバック：8.8.8.8 / 1.1.1.1
dns server 210.145.254.170 125.170.93.234 8.8.8.8 1.1.1.1
dns service recursive
```

---

## 7. DHCP

```
dhcp service server
dhcp server rfc2131 compliant except remain-silent

# VLAN 10（営業・総務管理）
dhcp scope 10 192.168.128.100-192.168.128.199/24 gateway 192.168.128.1 expire 12
dhcp scope option 10 dns=210.145.254.170,125.170.93.234,8.8.8.8,1.1.1.1

# VLAN 20（社内開発・試験）
dhcp scope 20 192.168.64.100-192.168.64.199/24 gateway 192.168.64.1 expire 12
dhcp scope option 20 dns=210.145.254.170,125.170.93.234,8.8.8.8,1.1.1.1

# VLAN 30（ゲスト）
dhcp scope 30 192.168.192.100-192.168.192.199/24 gateway 192.168.192.1 expire 4
dhcp scope option 30 dns=210.145.254.170,125.170.93.234,8.8.8.8,1.1.1.1

# 保守セグメント
dhcp scope 40 192.168.200.100-192.168.200.199/24 gateway 192.168.200.1 expire 12
```

### DHCP予約（RDP／SSH接続先PC）

`.100`〜`.149` から割り当てます。**VPNで接続する対象PCのみ**でよく、全PC分は不要です。

```
dhcp scope bind 10 192.168.128.101 <MAC_01>
dhcp scope bind 10 192.168.128.102 <MAC_02>
dhcp scope bind 20 192.168.64.101  <MAC_11>
dhcp scope bind 20 192.168.64.102  <MAC_12>
```

---

## 8. WAN側セキュリティフィルタ（現行configから移植）

現行RTX1200の `pp secure filter`（200000番台）を、**トンネルインターフェースへ移植**します。実績のあるフィルタセットのため、番号体系はそのまま踏襲します。

```
# --- プライベートアドレス偽装の遮断 ---
ip filter 200003 reject 192.168.0.0/16 * * * *

# --- Windows系ポートの遮断 ---
ip filter 200020 reject * * udp,tcp 135 *
ip filter 200021 reject * * udp,tcp * 135
ip filter 200022 reject * * udp,tcp netbios_ns-netbios_ssn *
ip filter 200023 reject * * udp,tcp * netbios_ns-netbios_ssn
ip filter 200024 reject * * udp,tcp 445 *
ip filter 200025 reject * * udp,tcp * 445
ip filter 200026 restrict * * tcpfin * www,21,nntp
ip filter 200027 restrict * * tcprst * www,21,nntp

# --- 内向き許可（最低限） ---
ip filter 200030 pass * 192.168.0.0/16 icmp * *
ip filter 200032 pass * 192.168.0.0/16 tcp * ident

# --- VPN終端（自機宛）【優先度低】VPNは後回し。切替当日は投入不要、VPN着手時に追加 ---
ip filter 200080 pass * <GLOBAL_IP> esp * *
ip filter 200081 pass * <GLOBAL_IP> udp * 500
ip filter 200082 pass * <GLOBAL_IP> udp * 4500
ip filter 200083 pass * <GLOBAL_IP> udp * 1701

# --- Web公開（今回は投入しない。必要時に有効化） ---
# ip filter 200087 pass * <公開サーバIP> tcpflag=0x0002/0x0017 * www
# ip filter 200088 pass * <公開サーバIP> tcpflag=0x0002/0x0017 * https

ip filter 200099 pass * * * * *
ip filter 200100 reject * * * * *

# --- 動的フィルタ ---
ip filter dynamic 200080 * * ftp
ip filter dynamic 200081 * * domain
ip filter dynamic 200082 * * www
ip filter dynamic 200083 * * smtp
ip filter dynamic 200084 * * pop3
ip filter dynamic 200085 * * ssh
ip filter dynamic 200098 * * tcp
ip filter dynamic 200099 * * udp
```

### 適用

```
tunnel select 1
 ip tunnel secure filter in  200003 200020 200021 200022 200023 200024 200025 200030 200032 200080 200081 200082 200083 200100
 ip tunnel secure filter out 200020 200021 200022 200023 200024 200025 200026 200027 200099 dynamic 200080 200081 200082 200083 200084 200085 200098 200099
```

> **現行から除外した項目**
> - SIP公開用の静的フィルタ `200084`／`200085`／`200086`（`192.168.50.150` 宛）— IP電話コントローラの使用終了に伴い移植しません
> - Web公開用の `200087`／`200088`、動的フィルタ `200`／`200086` — 公開環境を新構成で別途検討するため今回は投入しません
> **要検証**：現行は `ipsec ike local address 192.168.128.1` ＋ NAT静的で自機宛IPsecを通していました。新構成は固定グローバルIPを直接保持するため、上記のとおり `<GLOBAL_IP>` 宛としています。**フィルタとNATの評価順序の関係で調整が必要な場合があります。**

---

## 9. フィルタ（VLAN間アクセス制御）

### 9-1. 実現したいポリシー

| 通信方向 | 可否 |
|---|:--:|
| VLAN 10 → VLAN 20 | 許可（**セッション開始方向のみ**） |
| VLAN 20 → VLAN 10 | 拒否（例外なし） |
| 複合機 `192.168.128.20` → VLAN 20 | **拒否**（VLAN10→VLAN20許可の例外） |
| VLAN 30 → VLAN 10・20・保守・AWS | 拒否 |
| VLAN 30 → インターネット | 許可 |
| **VLAN 20 ↔ AWS `10.0.0.0/16`（10.0.3.x/10.0.4.x）** | 許可 |
| **VLAN 10 ↔ AWS `10.0.0.0/16`** | 許可（**2026-09-14変更**：VLAN10も接続対象に拡張） |
| VLAN 30 → AWS | 拒否（既存 2021 の 10.0.0.0/8 拒否で担保） |
| 保守 `192.168.200.0/24` → VLAN 10・20 | 許可（逆方向は拒否） |
| リモートVPN `192.168.201.0/24` → VLAN 10 | TCP 3389／22 のみ許可（**2026-09-14変更**：外部VPNはVLAN10のみ） |
| リモートVPN → VLAN 20/30 | 拒否（**2026-09-14変更**：開発のVLAN20リモートは廃止。開発のAWSは拠点間VGWで担保） |

> [!note] 【2026-09-14 AWS接続（VLAN20＋VLAN10）に伴うフィルタ更新＝下記9-3/9-4に反映済み】
> - **`ip filter 2004`（VLAN20→AWS 拒否）を削除**（lan3/2 in 適用列からも除外）→ VLAN20→AWS 許可。
> - **AWS→VLAN20 戻り許可**：`ip filter 2105 pass 10.0.0.0/16 192.168.64.0/24 * * *` を lan3/2 out に追加。
> - **VLAN10 は変更不要**：発信は既存 `2019 pass *` で許可、戻りは lan3/1 に out フィルタが無く自動許可（VLAN10→AWS拒否フィルタは入れない）。
> - **BGP広報**は §11 で 64系＋128系の2本（VLAN20・VLAN10）。
> - リモートVPN（L2TP）の VLAN20到達（`2103`/`2104`/dynamic`3020`）は §10方針どおり VPN実装時に廃止（本AWS対応とは独立・優先度低）。

確定版を作るうえで押さえるべき仕様は3点です。

| # | 仕様 | 出典の要点 |
|---:|---|---|
| 1 | 動的フィルタは**最初から存在せず、トリガとなるコネクションを検出した時に生成**される。**最初のパケットには静的フィルタが適用**される | → **転送方向の静的フィルタに `pass` が必要**。ここで `reject` されるとセッションが生成されない |
| 2 | 動的フィルタを `secure filter out` に指定すると、**そのセッションの戻りパケットは `in` 側の静的 `reject` に関わらず通過**する | → 公式例では `in` 側を `reject * *` にしても戻り通信が成立している |
| 3 | 動的フィルタのプロトコルに **ICMP は指定できない**（tcp / udp / ftp / domain / www 等のニーモニック） | → **VLAN間の ping は別途対応が必要**（→ 9-5） |

**構成の型**：制御は「**宛先側インターフェースの `in` で相手発の通信を拒否し、`out` に静的 `pass` ＋ `dynamic` を置く**」。これはヤマハ公式設定例「ローカルルーターで複数のLANを接続（片方向の通信）」と同じ構造です。

```
        VLAN10 (lan3/1)                      VLAN20 (lan3/2)
             │                                     │
   ①発信 ────┼──── in: pass ────▶ ルーティング ────┼──── out: 静的pass + dynamic ────▶ 宛先
             │                                     │      （ここでセッション生成）
   ④到達 ◀───┼──── out: フィルタなし ◀── ルーティング ◀──┼──── in: 動的フィルタが戻りを許可
             │                                     │      （静的は reject でよい）
                                                   │
   ✗ 逆方向 ─────────────────────────────────────  ┼──── in: reject（VLAN20発は拒否）
```

> **`lan3/1`（VLAN10）と `lan3/3`（VLAN30）には `secure filter out` を設定しません。** `out` に静的 `reject` を置くと、インターネットやVLAN20からの**戻りパケットまで落ちる**ためです。制御は各インターフェースの `in` と、`lan3/2` の `out` に集約します。

### 9-3. フィルタ定義（確定版）

```
# ============================================================
#  静的フィルタ：各VLAN発の通信制御（secure filter in 用）
# ============================================================
# --- VLAN20（開発）発 ---
ip filter 2000 reject * 192.168.128.0/24 * * *        # → VLAN10 拒否
ip filter 2001 reject * 192.168.192.0/24 * * *        # → VLAN30 拒否
ip filter 2002 reject * 192.168.200.0/24 * * *        # → 保守 拒否
ip filter 2003 reject * 192.168.201.0/24 * * *        # → VPN払出 拒否
# ip filter 2004（→AWS拒否）は 2026-09-14 廃止：VLAN20↔AWS 許可のため
ip filter 2009 pass   * * * * *                       # 以外（インターネット・AWS 10.0.0.0/16）許可

# --- VLAN10（営業・総務）発 ---
ip filter 2010 reject * 192.168.200.0/24 * * *        # → 保守 拒否
ip filter 2011 reject * 192.168.201.0/24 * * *        # → VPN払出 拒否
ip filter 2019 pass   * * * * *                       # 以外 許可（VLAN20・インターネット・AWS 10.0.0.0/16）

# --- VLAN30（ゲスト）発：プライベート宛は全拒否 ---
ip filter 2020 reject * 192.168.0.0/16 * * *
ip filter 2021 reject * 10.0.0.0/8 * * *
ip filter 2022 reject * 172.16.0.0/12 * * *
ip filter 2029 pass   * * * * *                       # インターネットのみ許可

# --- 保守セグメント発：制限なし ---
ip filter 2039 pass   * * * * *

# ============================================================
#  静的フィルタ：VLAN20 への転送許可（lan3/2 の secure filter out 用）
#  ★ 順序が重要：拒否を許可より前に置く
# ============================================================
ip filter 2100 reject 192.168.128.20   192.168.64.0/24 * * *          # 複合機 → VLAN20 拒否（例外）
ip filter 2101 pass   192.168.128.0/24 192.168.64.0/24 * * *          # VLAN10 → VLAN20 許可
ip filter 2102 pass   192.168.200.0/24 192.168.64.0/24 * * *          # 保守 → VLAN20 許可
ip filter 2103 pass   192.168.201.32/28 192.168.64.0/24 tcp * 3389    # VPN開発 → RDP
ip filter 2104 pass   192.168.201.32/28 192.168.64.0/24 tcp * 22      # VPN開発 → SSH
ip filter 2105 pass   10.0.0.0/16       192.168.64.0/24 * * *         # AWS(10.0.3.x/4.x) → VLAN20 戻り許可（2026-09-14追加）

# ★★★ 必須：RTX自身（lan3/2のIP）からVLAN20への送信を許可 ★★★
#  これが無いと DHCPのOFFER応答・ICMP応答が暗黙拒否で落ち、
#  VLAN20の端末にIPが配布されない（2026-09-14に実際に発生）
ip filter 2099 pass   192.168.64.1 * * * *

# ============================================================
#  動的フィルタ：戻り通信を許可（トリガ＝VLAN20方向への発信）
#  ※ ICMPは指定できないため tcp / udp のみ
# ============================================================
ip filter dynamic 3000 192.168.128.0/24  192.168.64.0/24 tcp
ip filter dynamic 3001 192.168.128.0/24  192.168.64.0/24 udp
ip filter dynamic 3010 192.168.200.0/24  192.168.64.0/24 tcp
ip filter dynamic 3011 192.168.200.0/24  192.168.64.0/24 udp
ip filter dynamic 3020 192.168.201.32/28 192.168.64.0/24 tcp

# ★★★ 必須：VLAN20発の通信（インターネット等）の戻りを許可 ★★★
#  lan3/2 の "in" 側に適用する。これが無いとVLAN20はインターネットの
#  応答パケットを受け取れず、Webが一切表示されない
ip filter dynamic 3030 192.168.64.0/24 * tcp
ip filter dynamic 3031 192.168.64.0/24 * udp
```

### 9-4. インターフェースへの適用（確定版）

```
ip lan3/1 secure filter in  2010 2011 2019
ip lan3/2 secure filter in  2000 2001 2002 2003 2009 dynamic 3030 3031
ip lan3/2 secure filter out 2099 2100 2101 2102 2103 2104 2105 dynamic 3000 3001 3010 3011 3020
ip lan3/3 secure filter in  2020 2021 2022 2029
ip lan1   secure filter in  2039
```

> `lan3/1`・`lan3/3`・`lan1` に `secure filter out` は設定しません（→ 9-2 の注記）。

> [!warning] ★ `secure filter out` を置く唯一のインターフェース＝`lan3/2` の落とし穴（2026-09-14に発生）
> `out` フィルタは **ルーター自身が送信するパケットにも適用**されます。当初の設定は `2100`〜`2104`（＝他セグメント発 → VLAN20）しか `pass` しておらず、次の3つがすべて暗黙拒否で落ちていました。
>
> | 落ちていたもの | 送信元 | 症状 |
> |---|---|---|
> | **DHCPのOFFER応答** | `192.168.64.1`（RTX自身） | **VLAN20の端末にIPが配布されない** |
> | **ICMPのecho応答** | 同上 | VLAN20から `ping 192.168.64.1` が失敗 |
> | **インターネットからの戻り** | グローバルIP | 手動IP設定してもWebが見られない |
>
> **`2099`（RTX自身→VLAN20の許可）と、`in` 側の `dynamic 3030 3031`（VLAN20発の戻り許可）が必須**です。
>
> **切り分けのコツ**：`show arp` にVLAN20端末が `LAN3/2` として載っているのに ping/DHCP だけ通らない場合は、**ARPはIPフィルタの対象外**なので「L2は正常、IPフィルタが原因」と断定できます。

### 9-5. VLAN間の ping について

**動的フィルタはICMPを扱えないため、上記の設定ではVLAN10からVLAN20への ping は通りません**（TCP/UDPは通ります）。対応は2案あります。

| 案 | 設定 | 評価 |
|---|---|---|
| **A：pingを使わない**（推奨） | 追加設定なし | 分離が最も厳密。疎通確認は **TCPで実施**（例：VLAN10のPCからVLAN20のPCの3389/22へ接続、`Test-NetConnection -Port 3389`） |
| B：ICMPを双方向許可 | `ip filter 2105 pass 192.168.128.0/24 192.168.64.0/24 icmp * *` を `lan3/2 out` の先頭付近へ、`ip filter 1999 pass 192.168.64.0/24 192.168.128.0/24 icmp * *` を `lan3/2 in` の先頭へ追加 | pingで確認できて運用は楽だが、**VLAN20からVLAN10へのping（＝ホスト存在調査）が可能になる**ため分離が緩む |

> 本設計は **案A** を採用します。[[切替・障害切り分け手順]] の疎通確認もTCPベースで記載しています。

### 9-6. 投入後に確認すること

| # | 確認内容 | 期待結果 |
|---:|---|---|
| 1 | VLAN10のPCから VLAN20のPCの TCP 3389/22 へ接続 | **成功**（戻り通信が成立している） |
| 2 | VLAN20のPCから VLAN10のPCの任意ポートへ接続 | **失敗**（新規セッション拒否） |
| 3 | 複合機 `192.168.128.20` から VLAN20 へ接続 | **失敗**（静的拒否が動的許可より前に評価されている） |
| 4 | VLAN10・VLAN20 からインターネットへ接続 | **成功**（`out` フィルタ未設定の影響が無いこと） |
| 5 | VLAN30から VLAN10・20 へ接続 | **失敗** |
| 6 | 保守セグメントから VLAN10・20 へ接続 | **成功** |
| 7 | `show ip connection summary` | VLAN10→VLAN20 のセッションが登録されている |

> 1がNGの場合は、`lan3/2 secure filter out` の静的 `pass`（2101）が動的フィルタより**前**にあるかを確認してください。静的に `pass` されないと動的フィルタのセッションが生成されません。

---

## 10. リモートアクセスVPN（L2TP/IPsec）

> **優先度低（VPNは後回し）。** 切替当日は投入せず、インターネット/VLAN成立後の別作業とする（→ [[conversations]] 2026-09-10「VPNは後回し」）。
>
> **【2026-09-14 方針変更】外部からのリモートVPNの到達先は VLAN10 のみ。** 全ユーザーの払出は VLAN10（RDP3389/SSH22）到達に統一。**開発ユーザー→VLAN20 のリモート経路は廃止**（下記本文の `192.168.201.32/28`→VLAN20、`4020`/`4021`、`yohiradev`/`t.kidodev` のVLAN20到達は実装時に削除）。開発のAWS利用は §11 拠点間VGW（VLAN20専用）で担保。

```
# --- IPsec 基本 ---
ipsec auto refresh on
ipsec transport 1 1 udp 1701

tunnel select 1000
 tunnel encapsulation l2tp
 ipsec tunnel 1
  ipsec sa policy 1 1 esp aes-cbc sha-hmac
  ipsec ike keepalive use 1 off
  ipsec ike local address 1 <GLOBAL_IP>
  ipsec ike pre-shared-key 1 text <L2TP_PSK>
  ipsec ike remote address 1 any
 l2tp tunnel disconnect time off
 l2tp keepalive use on 10 3
 l2tp syslog on
 ip tunnel tcp mss limit auto
 tunnel enable 1000

# 現行と同様に5本（tunnel 1000〜1004）を用意する。
# リモートアクセスVPN自体が代替手段のため、同時接続は4名程度を想定（6名登録／5本で運用可）。
ipsec transport 1000 1 udp 1701
# tunnel 1001〜1004 も同様に定義（ipsec tunnel 番号・transport 番号を重複させないこと）

# --- PPP（anonymous） ---
pp select anonymous
 pp bind tunnel1000-tunnel1004
 pp auth request mschap-v2
 # --- 業務ユーザー（VLAN10へRDP/SSH） ---
 pp auth username yohira     <PASS_yohira>     192.168.201.17
 pp auth username t.kido     <PASS_t.kido>     192.168.201.18
 pp auth username mogik      <PASS_mogik>      192.168.201.19
 pp auth username iizuka     <PASS_iizuka>     192.168.201.20
 # --- 開発ユーザー（VLAN20へRDP/SSH） ---
 pp auth username yohiradev  <PASS_yohiradev>  192.168.201.33
 pp auth username t.kidodev  <PASS_t.kidodev>  192.168.201.34
 ppp ipcp ipaddress on
 ppp ipcp msext on
 ppp ccp type none
 ip pp secure filter in 4010 4011 4020 4021 4099
 pp enable anonymous

# --- VPN用フィルタ ---
ip filter 4010 pass 192.168.201.16/28 192.168.128.0/24 tcp * 3389   # 業務→VLAN10 RDP
ip filter 4011 pass 192.168.201.16/28 192.168.128.0/24 tcp * 22     # 業務→VLAN10 SSH
ip filter 4020 pass 192.168.201.32/28 192.168.64.0/24  tcp * 3389   # 開発→VLAN20 RDP
ip filter 4021 pass 192.168.201.32/28 192.168.64.0/24  tcp * 22     # 開発→VLAN20 SSH
ip filter 4099 reject * * * * *                                     # それ以外は拒否
```

### ユーザーごとの払出IP（確定）

| ユーザー名 | 利用者 | 区分 | 払出IP | 到達範囲 |
|---|---|---|---|---|
| `yohira` | yohira | 業務 | `192.168.201.17` | VLAN 10（TCP 3389／22） |
| `t.kido` | t.kido | 業務 | `192.168.201.18` | VLAN 10（TCP 3389／22） |
| `mogik` | mogik | 業務 | `192.168.201.19` | VLAN 10（TCP 3389／22） |
| `iizuka` | iizuka | 業務 | `192.168.201.20` | VLAN 10（TCP 3389／22） |
| `yohiradev` | yohira | 開発 | `192.168.201.33` | VLAN 20（TCP 3389／22） |
| `t.kidodev` | t.kido | 開発 | `192.168.201.34` | VLAN 20（TCP 3389／22） |

- 業務レンジ：`192.168.201.16/28`（`.17`〜`.30`、14ユーザーまで）
- 開発レンジ：`192.168.201.32/28`（`.33`〜`.46`、14ユーザーまで）
- **利用者4名／アカウント6個**。業務と開発の両方へアクセスする2名（yohira・t.kido）は、**用途別に別アカウントで接続**します。

> **1アカウントで業務・開発の両方に到達させることも技術的に可能です**（到達範囲はフィルタで決まるため）。その場合は「兼務レンジ」を追加し、VLAN 10・VLAN 20 の双方を許可するフィルタを定義します。本設計では**セッション単位の権限を最小に保つため、用途別のアカウント分離を採用**しています。

#### 兼務レンジを使う場合（参考・今回は未使用）

```
# 兼務レンジ 192.168.201.48/28（.49〜.62）
ip filter 4030 pass 192.168.201.48/28 192.168.128.0/24 tcp * 3389
ip filter 4031 pass 192.168.201.48/28 192.168.128.0/24 tcp * 22
ip filter 4032 pass 192.168.201.48/28 192.168.64.0/24  tcp * 3389
ip filter 4033 pass 192.168.201.48/28 192.168.64.0/24  tcp * 22
# lan3/2 secure filter out へ 192.168.201.48/28 → VLAN20 の pass と dynamic も追加が必要
```

> **現行configからのユーザー変更**：`t-yamashita`・`takebuchi` は新リストに無いため**登録しません**。`iizukak` は `iizuka` へ改称。新規に `yohiradev`・`t.kidodev` を追加します。

> **`ip pp remote address pool` は設定しません。** 現行は `ip pp remote address pool dhcp` でLAN内のDHCPプール（`.10`〜`.60`）から払い出し、`ip lan1 proxyarp on` を併用していましたが、**新構成では専用セグメントの固定払出に変更**するため、プールとproxyarpはいずれも不要です。
> プールを併用し、固定指定したIPがプール範囲と重複すると、プール側から別アドレスが払い出されフィルタが意図通りに効かなくなります。
> **事前共有鍵は移行を機に更新することを推奨**します（現行は全トンネル共通の値が平文でconfigに残っています）。

---

## 11. AWS拠点間VPN（VGW）

> **【2026-09-14 優先度変更】AWS拠点間VPN(VGW)は「優先」で実装**（従来の優先度低/事後対応から格上げ）。
> **接続範囲＝VLAN20＋VLAN10 の両方**（2026-09-14ユーザー決定）：VLAN20(192.168.64.0/24)・VLAN10(192.168.128.0/24) ↔ AWS VPC(**10.0.3.0/24 と 10.0.4.0/24**)を双方向で接続。BGP広報は **64系＋128系の2本**。VLAN30↔AWSは拒否。
> ※RTXが**イニシエータ（発信側）**でAWS VGWへ張るため、map-e固定IP上でも **NAT-T(UDP4500)** で成立見込み（インバウンド待受が要る L2TP リモートVPN より条件は緩い）。
>
> **接続情報（2026-09-14 AWSコンソールで作成・DL済 → `config/aws_vpn_yamaha_config.txt`。PSKは平文のため git非追跡）**
>
> | 項目 | 値 |
> |---|---|
> | VPN接続ID / VGW / CGW | `vpn-02dfe4cb7fb8d8155` / `vgw-4e66d04f` / `cgw-0c4eb6ae228af69d1` |
> | 自外側IP（固定・map-e） | `124.100.212.73` |
> | BGP 自AS / 対向AS | `65000` / `10124` |
> | Tunnel1 対向外側 / 内側 | `52.196.54.142` / `169.254.23.54/30 ↔ 169.254.23.53` |
> | Tunnel2 対向外側 / 内側 | `54.65.4.212` / `169.254.222.134/30 ↔ 169.254.222.133` |
> | AWS側VPC CIDR | `10.0.3.0/24` / `10.0.4.0/24`（VGWのRoute PropagationがONであること＝要確認） |

> **DL版（Yamaha）そのままは投入不可。以下4点を適応**（→ [[conversations]] 2026-09-14）：
> 1. **番号の範囲修正**：RTX1300 は tunnel番号 2001 が範囲外（最大2000）。**トンネルI/F=2・3**（tunnel1=map-e使用中）、**SAポリシー=201/202**、**IKE gateway=1/2**（＝AWS生成の実績値）。
> 2. **NAT-T明示ON**：`ipsec ike nat-traversal 1/2 on` を追加（固定IP1でも map-e はポート制限NAPTのため）。
> 3. **BGP広報**：DL版の `0.0.0.0/0` は不採用。**`192.168.64.0/24`＋`192.168.128.0/24`** を広報。
> 4. **`bgp import` は `static`**（`connected` は非対応キーワード）。YAMAHAでは接続経路＝**implicit経路**で、公式ガイド「implicit経路は `bgp import` でプロトコルに `static` を指定することで導入できる」に準拠 → `bgp import 10124 static filter 1 2` で lan3/2・lan3/1 の直結網を広報（静的経路の追加不要）。

```
ipsec use on
ipsec auto refresh on

# --- トンネル1（AWS 52.196.54.142）／ tunnel I/F=2, SAポリシー=201, IKE gateway=1 ---
tunnel select 2
 tunnel encapsulation ipsec
 ipsec tunnel 201
  ipsec sa policy 201 1 esp aes-cbc sha-hmac
  ipsec ike version 1 2
  ipsec ike duration isakmp-sa 1 28800
  ipsec ike duration ipsec-sa 1 3600
  ipsec ike encryption 1 aes-cbc
  ipsec ike group 1 modp1024
  ipsec ike hash 1 sha
  ipsec ike pfs 1 on
  ipsec ike message-id-control 1 on
  ipsec ike child-exchange type 1 2
  ipsec ike keepalive use 1 on rfc4306 10 3
  ipsec ike nat-traversal 1 on                    # ★map-e配下のため追加
  ipsec ike local address 1 192.168.128.1         # ★map-e：固定IPは非保有→LAN IPを指定（NATで124.100.212.73へ変換）
  ipsec ike local name 1 124.100.212.73 ipv4-addr # IKE識別子は固定グローバルIP
  ipsec ike remote address 1 52.196.54.142
  ipsec ike remote name 1 52.196.54.142 ipv4-addr
  ipsec ike pre-shared-key 1 text <PSK_T1>        # ★実機で手入力（ファイルに残さない）
  ipsec ike negotiation receive 1 off
 ipsec tunnel outer df-bit clear
 ip tunnel address 169.254.23.54/30
 ip tunnel remote address 169.254.23.53
 ip tunnel tcp mss limit auto
 tunnel enable 2

# --- トンネル2（AWS 54.65.4.212 / 冗長）／ tunnel I/F=3, SAポリシー=202, IKE gateway=2 ---
tunnel select 3
 tunnel encapsulation ipsec
 ipsec tunnel 202
  ipsec sa policy 202 2 esp aes-cbc sha-hmac
  ipsec ike version 2 2
  ipsec ike duration isakmp-sa 2 28800
  ipsec ike duration ipsec-sa 2 3600
  ipsec ike encryption 2 aes-cbc
  ipsec ike group 2 modp1024
  ipsec ike hash 2 sha
  ipsec ike pfs 2 on
  ipsec ike message-id-control 2 on
  ipsec ike child-exchange type 2 2
  ipsec ike keepalive use 2 on rfc4306 10 3
  ipsec ike nat-traversal 2 on                    # ★
  ipsec ike local address 2 192.168.128.1         # ★map-e：固定IPは非保有→LAN IPを指定（NATで124.100.212.73へ変換）
  ipsec ike local name 2 124.100.212.73 ipv4-addr # IKE識別子は固定グローバルIP
  ipsec ike remote address 2 54.65.4.212
  ipsec ike remote name 2 54.65.4.212 ipv4-addr
  ipsec ike pre-shared-key 2 text <PSK_T2>
  ipsec ike negotiation receive 2 off
 ipsec tunnel outer df-bit clear
 ip tunnel address 169.254.222.134/30
 ip tunnel remote address 169.254.222.133
 ip tunnel tcp mss limit auto
 tunnel enable 3

# --- BGP（VLAN20＋VLAN10 を広報）---
bgp use on
bgp autonomous-system 65000
bgp neighbor 1 10124 169.254.23.53   hold-time=30 local-address=169.254.23.54
bgp neighbor 2 10124 169.254.222.133 hold-time=30 local-address=169.254.222.134
bgp import filter 1 equal 192.168.64.0/24     # VLAN20（開発）
bgp import filter 2 equal 192.168.128.0/24    # VLAN10（営業・総務）
bgp import 10124 static filter 1 2            # implicit(直結)経路を static 指定で広報
bgp configure refresh
```

> **DL版とのマッピング（`config/aws_vpn_yamaha_config.txt`）**：DL版の `tunnel select 1/2` → `2/3`（tunnel1=map-e回避）、`ipsec tunnel 201/202`・`ipsec sa policy 201 1`/`202 2`・IKE gateway `1`/`2` はDL値のまま（実績値・範囲内）、`ipsec ike version 1/2 2`（=IKEv2）維持、PSK 2本 → `<PSK_T1>/<PSK_T2>`（実機投入）、`bgp neighbor 1/2 10124 ...` そのまま、`bgp import filter 1 equal 0.0.0.0/0`＋`bgp import 10124 static filter 1` → 上記の 64系＋128系＋`static filter 1 2` に置換。
>
> **【教訓】RTX1300のトンネル番号は最大2000（2001以降は「パラメータが範囲を越えています」）。`bgp import` の protocol に `connected` は無い（static/rip/ospf/bgp/aggregate のみ）。直結網は implicit 経路として `static` 指定で広報する。**（2026-09-14 実機投入エラーで確認）
>
> **【教訓・最重要】map-e配下のIPsecは `ipsec ike local address` に固定グローバルIPを書いてはいけない**（当機はそのIPをインターフェースに保有せず、IKEを発信できず `show ipsec sa` が `send:0` になる）。**LAN側の保有IP（例 192.168.128.1）を指定**し、map-eのNATで固定IPへ変換＋NAT-Tで抜ける。IKE識別子は `ipsec ike local name <id> 124.100.212.73 ipv4-addr` で担保。出典：YAMAHA公式「Amazon VPCとVPN(IPsec)接続するルーターの設定(OCNバーチャルコネクトを利用)」= `ipsec ike local address 1 192.168.100.1`（LAN IP指定）。（2026-09-14 send:0 の切り分けで確認）
>
> **【呼び水】BGPは local-address（トンネル内側IP）がupしないと Idle のまま接続試行しない（`Local host: unspecified`）。トンネル未確立→IKE未起動→…のデッドロックは、AWS VPC宛の一時静的経路（`ip route 10.0.3.0/24 gateway tunnel 2` 等）＋LAN端末からの ping で通信を流し、RTXにIKEを起動させて解く。両系Established後に一時静的経路は削除しBGPへ委ねる。**
>
> **AWS(10.0.3.0/24・10.0.4.0/24)の経路はBGPで受信**するため、当社側に受信フィルタは不要（`show ip route` に自動掲載）。§9のAWS向けフィルタは `10.0.0.0/16` で3系・4系＋将来分を一括カバー。
>
> **要検証（実機投入時）**：
> - `show ipsec sa` / `show status tunnel 2` / `show status tunnel 3`（ISAKMP/IPsec SA確立）、`show ip bgp neighbor`（Established）、`show ip route`（10.0.3.0/24・10.0.4.0/24 学習）
> - map-e MTU1460＋IPsecのフラグメント（不通・大サイズ落ちがあれば `ip tunnel mtu` を明示調整。まず `ip tunnel tcp mss limit auto` で様子見）
> - §8（tunnel1=map-e）の `out` dynamic udp(200099) で NAT-T戻り(UDP4500)が通ること（アウトバウンド発のため追加静的許可は不要見込み）

### 11-1. 別アカウント/別VGWへVPNを追加する時の再利用チェックリスト

本§11は**テンプレートとして再利用可**。ただし「PSKだけ変わる」ではない点に注意。

**🔴 毎回変わる（新アカウントで作成し、Yamaha設定DLから取得）**
- PSK ×2
- AWS側 外側IP（`ipsec ike remote address`）×2
- 内側トンネルIP（`ip tunnel address`/`remote address` の 169.254.x.x/30）×2
- BGP neighbor（内側VGW IP）×2
- **Amazon側ASN**（今回10124。VGWごとに異なる場合あり＝要確認）

**🟡 RTX側で「新しい重複しない番号」に採番**（既存：tunnel2/3・ipsec/SA201/202・IKE gateway1/2・bgp neighbor1/2 と衝突不可）
- 次組の例：tunnelI/F **4・5**／ipsec・SAポリシー **203・204**／IKE gateway **3・4**／bgp neighbor **3・4**

**🟢 変えない（＝map-e対応テンプレの肝）**
- `ipsec ike local address <id> 192.168.128.1`（★固定IPは書かない）
- `ipsec ike local name <id> 124.100.212.73 ipv4-addr`（自CGW識別子）
- `ipsec ike nat-traversal <id> on`
- 自ASN `65000`／IKE暗号（aes-cbc・sha・modp1024＝AWS既定）

**AWSコンソール側（新アカウント）**
- Customer Gateway を **当社IP `124.100.212.73`／ASN `65000`** で作成
- Site-to-Site VPN（動的BGP）作成 → **Yamaha/IKEv2 で設定DL**（上記🔴を採取）
- VPCルートテーブルの **ルート伝播ON**（当社網の戻り経路）＋ SG/NACL で送信元 `192.168.64.0/24`・`192.168.128.0/24` を許可

**投入手順（今回と同じ4適応）**：①番号を🟡へ改番／②`nat-traversal on`／③`local address=192.168.128.1`＋`local name=固定IP`／④`bgp import <ASN> static filter …`（implicitはstatic）。起動は「一時静的経路（`ip route <新VPC> gateway tunnel N`）＋LAN端末からping」で呼び水 → 両系Established後に一時静的経路を削除。

---

## 12. 投入順序と保存

|   # | 内容                | 確認                             |
| --: | ----------------- | ------------------------------ |
|   1 | 基本設定（1章）          | コンソール接続                        |
|   2 | インターフェース（3章）      | `show status lan2` でリンクアップ     |
|   3 | IPv6（3-2）         | `show ipv6 address` でグローバルIPv6 |
|   4 | トンネル・NAT・経路（4〜5章） | `ping 8.8.8.8`                 |
|   5 | DNS（6章）           | 名前解決                           |
|   6 | VLAN・DHCP（3-3、7章） | 各VLANでIP取得                     |
|   7 | フィルタ（8章）          | VLAN間の可否を確認                    |
|   8 | L2TP/IPsec（9章）    | 外部から接続テスト                      |
|   9 | ~~AWS VPN~~       | **今回は対象外（事後対応）**               |

```
save
```

> **各段階を投入するたびに確認**してください。まとめて投入すると障害切り分けが困難になります（→ [[切替・障害切り分け手順]] 4章）。

### 12-1. 確認コマンド一覧（★実機で検証済み・誤記に注意）

RTX1300に**存在しないコマンド**を手順書に書いていたため調査が遅れました。正しいものは次のとおりです。

| 目的 | ✗ 誤（存在しない） | ✅ 正しいコマンド |
|---|---|---|
| DHCPのリース状況 | ~~`show dhcp status`~~ | **`show status dhcp`** |
| インターフェースのIP | ~~`show ip interface`~~ | **`show ip route`**（`implicit` 経路の有無で判断）／**`show status lan3`** |
| VLANサブIFの状態 | ~~`show status lan3/1`~~ | **`show ip route`** で `192.168.128.0/24 ... LAN3/1 implicit` を確認 |
| 動作中のconfig番号 | — | **`show environment`**（`実行中設定ファイル: config0` の行） |
| ARPの解決状況 | — | **`show arp`**（インターフェース名が `LAN3/1` 等で表示され、どのVLANで解決したかが分かる） |
| 設定の部分確認 | — | **`show config \| grep lan3`**（`\|` の前後にスペースが必要。`show config grep dhcp` はエラー） |

> **`show status lan3` の読み方**：`未サポートパケットの受信` が受信全体の大半を占める場合、**タグ付きフレームを解釈できずに破棄している**か、**VLAN定義の無いVIDのフレームが流入している**ことを示します。2026-09-14の障害では、VLAN10内の3台（スイッチ・AP・PC）が応答の返らないARPを再送し続けていた分が、この値として現れていました。

---

## 13. 未確定・要検証事項

| 項目                                              | 状態                                                                      |
| ----------------------------------------------- | ----------------------------------------------------------------------- |
| OCN開通情報（`<IF_ID>` `<TUNNEL_DST>` `<GLOBAL_IP>`） | **未入手**                                                                 |
| ファームウェアRev（Rev.23.00.17以降）                      | **確認済**（Rev.23.00.17 / 2025-10-03ビルド、2026-08-25 `show environment` で確認） |
| DHCP予約対象PCのMACアドレス                              | **未収集**                                                                 |
| VLAN間フィルタ（9章）                                   | **確定**（ヤマハ公式仕様・設定例に準拠）。投入後に 9-6 の7項目を確認                                 |
| AWS VPN設定                                       | **今回スコープ外**（事後対応。代替ルートあり）                                               |
| Web公開環境                                         | **今回スコープ外**（新構成に合わせて別途検討）                                               |
| 固定IP機器の割当                                       | サーバ群はAWS移行済みで少数。`.2`〜`.99` 内へ割当                                         |
| VPNユーザーの業務／開発区分                                 | **確定**（4名／6アカウント。→ 10章）                                                 |
| MAP-E／IPIP上でのIKE・ESP通過性                         | OCNへ要確認                                                                 |
| L2TP/IPsec 同時接続数の上限                             | 機種仕様を要確認                                                                |
| フレッツID×ルール情報の紐付け                              | **注意**：IPoEはフレッツID（CAF/COP）とルーター内ルール情報の組合せで通信。自営端末（RTX1300）を別回線へ流用（ルール情報未変更）すると IPv4 over IPv6 が不通になる。**切替当日は当該回線の開通情報（`<IF_ID>`/`<TUNNEL_DST>`/`<GLOBAL_IP>`）を投入**。検証で別回線に接続したRTX1300を持ち込む場合は初期化／ルール情報削除が必要（OCN Checklist ◆IPoE通信ご利用時の注意事項 → [[OCN_DOC突き合わせ結果]] #6） |
