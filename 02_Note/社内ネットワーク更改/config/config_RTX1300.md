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
| `<AWS_*>` | AWS VGW の対向IP・PSK・BGP情報 | **AWSコンソールの設定ファイル**（新CGW作成後に再取得） |
| `<WEB_SRV>` | Web公開サーバのIP（移設後） | 社内決定。案：`192.168.128.10` |

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

# --- Web公開（現行の 301/302 を移植） ---
nat descriptor masquerade static 1 301 <WEB_SRV> tcp www
nat descriptor masquerade static 1 302 <WEB_SRV> tcp https
```

> **現行の `192.168.128.128` から移設が必要です。** 新設計では `.128` はDHCP予約範囲（`.100`〜`.149`）に当たるため、固定IP範囲 `.2`〜`.99` 内へ移してください。サーバIPの変更は社内DNS・証明書・監視設定に影響する場合があります（→ [[現行config棚卸し]] 3章）。

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

# --- Web公開（宛先を移設後のIPへ変更） ---
ip filter 200087 pass * <WEB_SRV> tcpflag=0x0002/0x0017 * www
ip filter 200088 pass * <WEB_SRV> tcpflag=0x0002/0x0017 * https

ip filter 200099 pass * * * * *
ip filter 200100 reject * * * * *

# --- 動的フィルタ ---
ip filter dynamic 200    * <WEB_SRV> www
ip filter dynamic 200080 * * ftp
ip filter dynamic 200081 * * domain
ip filter dynamic 200082 * * www
ip filter dynamic 200083 * * smtp
ip filter dynamic 200084 * * pop3
ip filter dynamic 200085 * * ssh
ip filter dynamic 200086 * <WEB_SRV> https
ip filter dynamic 200098 * * tcp
ip filter dynamic 200099 * * udp
```

### 適用

```
tunnel select 1
 ip tunnel secure filter in  200003 200020 200021 200022 200023 200024 200025 200030 200032 200080 200081 200082 200083 200087 200088 200100 dynamic 200 200086
 ip tunnel secure filter out 200020 200021 200022 200023 200024 200025 200026 200027 200099 dynamic 200080 200081 200082 200083 200084 200085 200086 200098 200099
```

> **現行から除外した項目**：SIP公開用の `200084`／`200085`／`200086`（静的、`192.168.50.150` 宛）は、IP電話コントローラの使用終了に伴い**移植しません**。
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

### 9-2. フィルタ定義（雛形）

```
# --- 静的フィルタ ---
ip filter 2010 reject 192.168.128.20 192.168.64.0/24 * * *      # 複合機→VLAN20（最優先で拒否）
ip filter 2020 reject * 192.168.128.0/24 * * *                  # →VLAN10 拒否
ip filter 2021 reject * 192.168.64.0/24 * * *                   # →VLAN20 拒否
ip filter 2022 reject * 192.168.192.0/24 * * *                  # →VLAN30 拒否
ip filter 2023 reject * 192.168.200.0/24 * * *                  # →保守 拒否
ip filter 2024 reject * 10.0.3.0/24 * * *                       # →AWS 拒否
ip filter 2030 reject * 192.168.0.0/16 * * *                    # →プライベート全体 拒否
ip filter 2031 reject * 10.0.0.0/8 * * *
ip filter 2032 reject * 172.16.0.0/12 * * *
ip filter 2099 pass * * * * *                                   # 上記以外は許可（インターネット向け）

# --- 動的フィルタ（VLAN10 → VLAN20 の片方向許可） ---
ip filter dynamic 3010 192.168.128.0/24 192.168.64.0/24 tcp
ip filter dynamic 3011 192.168.128.0/24 192.168.64.0/24 udp
ip filter dynamic 3012 192.168.128.0/24 192.168.64.0/24 icmp

# --- 動的フィルタ（保守 → VLAN10・20） ---
ip filter dynamic 3020 192.168.200.0/24 192.168.128.0/24 tcp
ip filter dynamic 3021 192.168.200.0/24 192.168.128.0/24 udp
ip filter dynamic 3022 192.168.200.0/24 192.168.128.0/24 icmp
ip filter dynamic 3030 192.168.200.0/24 192.168.64.0/24 tcp
ip filter dynamic 3031 192.168.200.0/24 192.168.64.0/24 udp
ip filter dynamic 3032 192.168.200.0/24 192.168.64.0/24 icmp
```

### 9-3. インターフェースへの適用（雛形）

```
ip lan3/1 secure filter in  2023 2099                    # VLAN10：保守宛のみ拒否
ip lan3/2 secure filter in  2020 2022 2023 2024 2099     # VLAN20：VLAN10/30/保守/AWS宛を拒否
ip lan3/3 secure filter in  2030 2031 2032 2099          # VLAN30：プライベート宛を全拒否
ip lan3/2 secure filter out 2010 dynamic 3010 3011 3012 3030 3031 3032
```

> ⚠️ **この 9-2／9-3 は雛形です。実装前に検証環境での動作確認が必要です。**
> 「片方向許可」は **静的フィルタだけでは戻りパケットが落ちて通信不能**になります。ヤマハの動的フィルタは適用方向（`in`／`out`）と評価順序の解釈を誤りやすいため、以下を必ず実機で確認してください。
> - VLAN10 → VLAN20 の通信が**双方向で成立**するか（戻りパケットが落ちていないか）
> - VLAN20 → VLAN10 が**新規セッションとして拒否**されるか
> - 複合機 `192.168.128.20` → VLAN20 が拒否されるか（静的拒否が動的許可より**前**に評価されているか）
> - VLAN10・20からインターネットへの通信が阻害されていないか

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

# 現行は5本のトンネルに6ユーザーを登録しており、6人目が同時接続できない状態でした。
# 新構成では tunnel 1000〜1005（6本）以上を用意します。
ipsec transport 1000 1 udp 1701
# tunnel 1001〜1005 も同様に定義（ipsec tunnel 番号・transport 番号を重複させないこと）

# --- PPP（anonymous） ---
pp select anonymous
 pp bind tunnel1000-tunnel1004
 pp auth request mschap-v2
 pp auth username yohira       <PASS_yohira>       <IP>
 pp auth username t-yamashita  <PASS_t-yamashita>  <IP>
 pp auth username takebuchi    <PASS_takebuchi>    <IP>
 pp auth username t.kido       <PASS_t.kido>       <IP>
 pp auth username mogik        <PASS_mogik>        <IP>
 pp auth username iizukak      <PASS_iizukak>      <IP>
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

### ユーザーごとの払出IP（要記入）

| ユーザー名 | 区分 | 払出IP |
|---|---|---|
| yohira | **要記入**（業務／開発） | |
| t-yamashita | **要記入** | |
| takebuchi | **要記入** | |
| t.kido | **要記入** | |
| mogik | **要記入** | |
| iizukak | **要記入** | |

- 業務ユーザー：`192.168.201.17`〜`.30`（VLAN 10へ RDP/SSH）
- 開発ユーザー：`192.168.201.33`〜`.46`（VLAN 20へ RDP/SSH）

> **`ip pp remote address pool` は設定しません。** 現行は `ip pp remote address pool dhcp` でLAN内のDHCPプール（`.10`〜`.60`）から払い出し、`ip lan1 proxyarp on` を併用していましたが、**新構成では専用セグメントの固定払出に変更**するため、プールとproxyarpはいずれも不要です。
> プールを併用し、固定指定したIPがプール範囲と重複すると、プール側から別アドレスが払い出されフィルタが意図通りに効かなくなります。
> **事前共有鍵は移行を機に更新することを推奨**します（現行は全トンネル共通の値が平文でconfigに残っています）。

---

## 11. AWS拠点間VPN（VGW）

> **⚠️ グローバルIPが変わるため、AWS側の作り直しが必要です。**
> 現行のCustomer Gatewayは `153.156.71.228`（PPPoE時代のIP）で登録されています。光クロス+固定IP1で**IPが変わる**ため、**新CGWの作成とVPN接続の張り直し**が必要です。これは切替当日ではなく**事前に着手**してください。
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

| # | 内容 | 確認 |
|---:|---|---|
| 1 | 基本設定（1章） | コンソール接続 |
| 2 | インターフェース（3章） | `show status lan2` でリンクアップ |
| 3 | IPv6（3-2） | `show ipv6 address` でグローバルIPv6 |
| 4 | トンネル・NAT・経路（4〜5章） | `ping 8.8.8.8` |
| 5 | DNS（6章） | 名前解決 |
| 6 | VLAN・DHCP（3-3、7章） | 各VLANでIP取得 |
| 7 | フィルタ（8章） | VLAN間の可否を確認 |
| 8 | L2TP/IPsec（9章） | 外部から接続テスト |
| 9 | AWS VPN（10章） | `show ipsec sa` |

```
save
```

> **各段階を投入するたびに確認**してください。まとめて投入すると障害切り分けが困難になります（→ [[切替・障害切り分け手順]] 4章）。

---

## 13. 未確定・要検証事項

| 項目 | 状態 |
|---|---|
| OCN開通情報（`<IF_ID>` `<TUNNEL_DST>` `<GLOBAL_IP>`） | **未入手** |
| ファームウェアRev（Rev.23.00.17以降） | **未確認** |
| DHCP予約対象PCのMACアドレス | **未収集** |
| VLAN間フィルタ（8章）の動作 | **要検証**（動的フィルタの方向・評価順） |
| AWS VPN設定 | **新CGW作成→設定ファイル再取得が必要**（事前作業） |
| Web公開サーバの移設先IP | 未決定（案：`192.168.128.10`） |
| `.61`〜`.254` の固定IP機器の棚卸し | **未実施**（新設計では `.2`〜`.99` へ移設が必要） |
| VPNユーザー6名の業務／開発区分 | **未記入** |
| MAP-E／IPIP上でのIKE・ESP通過性 | OCNへ要確認 |
| L2TP/IPsec 同時接続数の上限 | 機種仕様を要確認 |
