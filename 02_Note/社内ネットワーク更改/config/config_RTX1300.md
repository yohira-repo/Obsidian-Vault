# YAMAHA RTX1300 コンフィグ

- 設計根拠：[[社内LANネットワーク設定]]（3. IPアドレス設計）
- 関連：[[config_XG-100NE]] / [[config_XS508TM]] / [[切替・障害切り分け手順]]
- 移植元：[[現行config棚卸し]]（RTX1200 / PPPoE からの引き継ぎ判定）

> **前提**：XG-100NE（HGW）配下 ／ IPv6は **RA方式** ／ 社内は **IPv4のみ** ／ VLAN ID は **10・20・30**

---

## 0. プレースホルダ一覧（投入前に確定させる値）

| プレースホルダ | 内容 | 入手先 |
|---|---|---|
| `<LOGIN_PASS>` / `<ADMIN_PASS>` | ログイン／管理者パスワード | 社内 |
| `<IF_ID>` | インターフェースID | **OCN開通通知** |
| `<TUNNEL_DST>` | Tunnel Destination（対向IPv6） | **OCN開通通知** |
| `<GLOBAL_IP>` | 固定グローバルIPv4アドレス | **OCN開通通知** |
| `<DNS1>` `<DNS2>` | パブリックDNS（例 `8.8.8.8` / `1.1.1.1`） | 社内決定 |
| `<MAC_xx>` | DHCP予約対象PCのMACアドレス | 実機確認 |
| `<L2TP_PSK>` | L2TP/IPsec 事前共有鍵 | 社内 |
| `<VPN_USER_x>` / `<VPN_PASS_x>` | VPNユーザー名・パスワード | 社内 |
| `<AWS_*>` | AWS VGW の対向IP・PSK・BGP情報 | **今回のスコープ外**（→ 11章。事後対応） |

---

## 1. 基本設定

```
console character ascii
console lines infinity
login password <LOGIN_PASS>
administrator password <ADMIN_PASS>
timezone +09:00
```

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

### 3-2. LAN2：WAN（XG-100NE LAN4 と接続）

```
# ★ RA方式（HGW配下のため）。dhcp-prefix@ にすると IPv4 が通らなくなる
ipv6 lan2 address ra-prefix@lan2::<IF_ID>/64
```

> **最重要**：`ra-prefix@lan2` を `dhcp-prefix@lan2` にしないこと。HGW配下ではDHCPv6-PDでプレフィックスを取得できず、MAPルール／トンネルが成立せず **「IPv6は通るがIPv4が全く通らない」** 状態になります（→ [[切替・障害切り分け手順]] 5-1）。

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

## 4. IPIPトンネル（OCNバーチャルコネクト 固定IP1）

```
tunnel select 1
 tunnel encapsulation ipip
 tunnel endpoint address <TUNNEL_DST>
 ip tunnel mtu 1460
 ip tunnel tcp mss limit auto
 ip tunnel nat descriptor 1
 tunnel enable 1

ip route default gateway tunnel 1
```

> `tunnel endpoint address` は「対向アドレスのみ」の指定です。自側を明示する場合は `tunnel endpoint address <自側IPv6> <TUNNEL_DST>` の順になります。**OCN開通通知の記載を優先**してください。

---

## 5. NAT（固定グローバルIPでのNAPT）

```
nat descriptor type 1 masquerade
nat descriptor address outer 1 <GLOBAL_IP>
nat descriptor address inner 1 auto
```

> **Web公開（現行の `192.168.128.128` への www/https）は今回移植しません。** サーバ群はAWSへ移行済みで、公開環境は新構成に合わせて別途検討する方針です。必要になった時点で以下を追加します。
> ```
> nat descriptor masquerade static 1 301 <公開サーバIP> tcp www
> nat descriptor masquerade static 1 302 <公開サーバIP> tcp https
> ```

---

## 6. DNS

```
# ★ 自動設定の "dhcp lan2" は使わない（HGWをDNSサーバとして参照し名前解決に失敗する既知事象の回避）
dns server <DNS1> <DNS2>
dns service recursive
```

---

## 7. DHCP

```
dhcp service server
dhcp server rfc2131 compliant except remain-silent

# VLAN 10（営業・総務管理）
dhcp scope 10 192.168.128.100-192.168.128.199/24 gateway 192.168.128.1 expire 12
dhcp scope option 10 dns=<DNS1>,<DNS2>

# VLAN 20（社内開発・試験）
dhcp scope 20 192.168.64.100-192.168.64.199/24 gateway 192.168.64.1 expire 12
dhcp scope option 20 dns=<DNS1>,<DNS2>

# VLAN 30（ゲスト）
dhcp scope 30 192.168.192.100-192.168.192.199/24 gateway 192.168.192.1 expire 4
dhcp scope option 30 dns=<DNS1>,<DNS2>

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

# --- VPN終端（自機宛） ---
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
| VLAN 10 → AWS `10.0.3.0/24` | 許可 |
| VLAN 20・30 → AWS | 拒否 |
| 保守 `192.168.200.0/24` → VLAN 10・20 | 許可（逆方向は拒否） |
| VPN業務 `192.168.201.16/28` → VLAN 10 | TCP 3389／22 のみ許可 |
| VPN開発 `192.168.201.32/28` → VLAN 20 | TCP 3389／22 のみ許可 |

### 9-2. 動作原理（ヤマハ公式仕様の確認結果）

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
ip filter 2004 reject * 10.0.3.0/24 * * *             # → AWS 拒否
ip filter 2009 pass   * * * * *                       # 以外（インターネット）許可

# --- VLAN10（営業・総務）発 ---
ip filter 2010 reject * 192.168.200.0/24 * * *        # → 保守 拒否
ip filter 2011 reject * 192.168.201.0/24 * * *        # → VPN払出 拒否
ip filter 2019 pass   * * * * *                       # 以外 許可（VLAN20・インターネット・AWS）

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

# ============================================================
#  動的フィルタ：戻り通信を許可（トリガ＝VLAN20方向への発信）
#  ※ ICMPは指定できないため tcp / udp のみ
# ============================================================
ip filter dynamic 3000 192.168.128.0/24  192.168.64.0/24 tcp
ip filter dynamic 3001 192.168.128.0/24  192.168.64.0/24 udp
ip filter dynamic 3010 192.168.200.0/24  192.168.64.0/24 tcp
ip filter dynamic 3011 192.168.200.0/24  192.168.64.0/24 udp
ip filter dynamic 3020 192.168.201.32/28 192.168.64.0/24 tcp
```

### 9-4. インターフェースへの適用（確定版）

```
ip lan3/1 secure filter in  2010 2011 2019
ip lan3/2 secure filter in  2000 2001 2002 2003 2004 2009
ip lan3/2 secure filter out 2100 2101 2102 2103 2104 dynamic 3000 3001 3010 3011 3020
ip lan3/3 secure filter in  2020 2021 2022 2029
ip lan1   secure filter in  2039
```

> `lan3/1`・`lan3/3`・`lan1` に `secure filter out` は設定しません（→ 9-2 の注記）。

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

> **⚠️ 本章は今回の切替スコープ外です（事後対応）。**
> AWSへのルートには代替手段があるため、回線切替後に順次対応する方針です。**切替当日はAWS VPNを設定しません。**
>
> グローバルIPが `153.156.71.228`（PPPoE時代のIP）から変わるため、**新Customer Gatewayの作成とVPN接続の張り直し**が必要になります。
>
> | 項目 | 扱い |
> |---|---|
> | BGP 自AS `65000`／対向AS `10124` | **引き継げる**（同じVGWを再利用する場合） |
> | 広報経路 `192.168.128.0/24` | **引き継げる**（VLAN 10のセグメントは変更なし） |
> | トンネル外側IP・内側IP・事前共有鍵 | **再取得が必要**（新CGW作成時にAWSが発行） |

AWSコンソールでSite-to-Site VPN接続を作成し、**「設定ファイルのダウンロード」でベンダー＝Yamaha を選択**すると、そのまま投入できるコンフィグが得られます。以下は現行構成を踏まえた構造です。

```
# --- トンネル1 ---
tunnel select 2001
 tunnel encapsulation ipsec
 ipsec tunnel 2001
  ipsec sa policy 2001 2001 esp aes-cbc sha-hmac
  ipsec ike version 2001 2
  ipsec ike local address 2001 <GLOBAL_IP>
  ipsec ike remote address 2001 <AWS_TUNNEL1_OUTSIDE_IP>
  ipsec ike pre-shared-key 2001 text <AWS_TUNNEL1_PSK>
 ip tunnel address <AWS_TUNNEL1_INSIDE_CGW_IP>
 ip tunnel remote address <AWS_TUNNEL1_INSIDE_VGW_IP>
 ip tunnel tcp mss limit auto
 tunnel enable 2001

# --- トンネル2（冗長） ---
tunnel select 2002
 （トンネル1と同様に <AWS_TUNNEL2_*> を設定）

# --- BGP ---
# --- BGP（現行値を踏襲） ---
bgp use on
bgp autonomous-system 65000
bgp neighbor 1 10124 <AWS_TUNNEL1_INSIDE_VGW_IP> hold-time=30 local-address=<AWS_TUNNEL1_INSIDE_CGW_IP>
bgp neighbor 2 10124 <AWS_TUNNEL2_INSIDE_VGW_IP> hold-time=30 local-address=<AWS_TUNNEL2_INSIDE_CGW_IP>
bgp import filter 1 equal 192.168.128.0/24
bgp import 10124 static filter 1
bgp configure refresh
```

> **AWSコンソールからダウンロードした設定を正としてください。**
> 現行は `ipsec ike local address 192.168.128.1` ＋ NAT静的（esp/500/4500）で自機宛IPsecを通していましたが、**新構成では固定グローバルIPを直接保持するため、`ipsec ike local address` に `<GLOBAL_IP>` を指定し、NAT静的は不要**になります。

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

---

## 13. 未確定・要検証事項

| 項目 | 状態 |
|---|---|
| OCN開通情報（`<IF_ID>` `<TUNNEL_DST>` `<GLOBAL_IP>`） | **未入手** |
| ファームウェアRev（Rev.23.00.17以降） | **確認済**（Rev.23.00.17 / 2025-10-03ビルド、2026-08-25 `show environment` で確認） |
| DHCP予約対象PCのMACアドレス | **未収集** |
| VLAN間フィルタ（9章） | **確定**（ヤマハ公式仕様・設定例に準拠）。投入後に 9-6 の7項目を確認 |
| AWS VPN設定 | **今回スコープ外**（事後対応。代替ルートあり） |
| Web公開環境 | **今回スコープ外**（新構成に合わせて別途検討） |
| 固定IP機器の割当 | サーバ群はAWS移行済みで少数。`.2`〜`.99` 内へ割当 |
| VPNユーザーの業務／開発区分 | **確定**（4名／6アカウント。→ 10章） |
| MAP-E／IPIP上でのIKE・ESP通過性 | OCNへ要確認 |
| L2TP/IPsec 同時接続数の上限 | 機種仕様を要確認 |
