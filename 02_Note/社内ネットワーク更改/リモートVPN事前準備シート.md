# リモートVPN 事前準備シート

作成：2026-09-15 ／ [[リモートVPN投入手順]] 1章「事前準備」の記入用ワークシート。
段階3（実機投入）の前に、このシートを埋めてから作業に入る。

> [!warning] 取り扱い
> **PSK・パスワードの実値はこのファイル（Vault）に書かない。** 実機へ手入力し、値は社内のパスワード管理（金庫/シークレット管理ツール）で管理する。本シートは「発行済みか」のチェックと、機器/PC情報の記録用。

---

## 1. 秘密情報の発行チェック（実値は別管理）

| # | 項目 | 用途 | 文字数/方針 | 発行済 | 保管先 |
|---:|---|---|---|:--:|---|
| 1 | **L2TP事前共有鍵（PSK）** | 全トンネル共通の事前共有鍵 | 24文字以上・記号なし英数（`ipsec ike pre-shared-key … text` 用） | ☐ | |
| 2 | `yohira` パスワード | L2TP認証（MS-CHAPv2） | 20文字以上・ユーザー毎に別値 | ☐ | |
| 3 | `t.kido` パスワード | 同上 | 同上 | ☐ | |
| 4 | `mogik` パスワード | 同上 | 同上 | ☐ | |
| 5 | `iizuka` パスワード | 同上 | 同上 | ☐ | |

> **記号の注意**：YAMAHAの `text` 指定では空白や一部記号がパース事故を招くため、**英数中心（Base64から `+ / =` を除いた文字）**が無難。

### 生成方法（PowerShell・値は保存しない）
```powershell
# 1件生成（24文字・英数のみ）。実行のたびに別値が出る
$b = New-Object 'System.Byte[]' 18
(New-Object System.Security.Cryptography.RNGCryptoServiceProvider).GetBytes($b)
(([Convert]::ToBase64String($b)) -replace '[+/=]','').Substring(0,24)
```
```bash
# Git Bash / Linux の場合
LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 24; echo
```
- PSK1件＋パスワード4件＝**計5件**を生成し、それぞれ保管先（パスワード管理）へ登録。
- 生成した端末の履歴・クリップボードに残さない（実機入力後にクリア）。

---

## 2. 接続先PC（RDP/SSH対象）情報 ― MAC収集とDHCP予約

VPNで自席PCへRDP/SSHする**対象PCのみ**。MACを集め、`.100`〜`.149`（VLAN10=`192.168.128.100`〜`149`）で予約する。

| 利用者    | 接続先PCホスト名 | OS  | MACアドレス | 予約IP(VLAN10)      | RDP/SSH | 記入済 |
| ------ | --------- | --- | ------- | ----------------- | :-----: | :-: |
| yohira |           |     |         | `192.168.128.___` | RDP/SSH |  ☐  |
| t.kido |           |     |         | `192.168.128.___` | RDP/SSH |  ☐  |
| mogik  |           |     |         | `192.168.128.___` | RDP/SSH |  ☐  |
| iizuka |           |     |         | `192.168.128.___` | RDP/SSH |  ☐  |

### MACアドレスの調べ方
```powershell
# Windows（物理NIC）
Get-NetAdapter -Physical | Select-Object Name,MacAddress,Status
```
```bash
# Linux
ip link | grep -A1 -E '^[0-9]+: e' | grep link/ether
```

### DHCP予約の投入コマンド（記入後に実機へ・[[config_RTX1300]] §7 と整合）
```
# 書式：dhcp scope bind <スコープ番号> <IPアドレス> <MAC>
# 例（VLAN10スコープが scope 10 の場合。実スコープ番号は§7で確認）
dhcp scope bind 10 192.168.128.100 xx:xx:xx:xx:xx:xx   # yohira PC
dhcp scope bind 10 192.168.128.101 xx:xx:xx:xx:xx:xx   # t.kido PC
dhcp scope bind 10 192.168.128.102 xx:xx:xx:xx:xx:xx   # mogik PC
dhcp scope bind 10 192.168.128.103 xx:xx:xx:xx:xx:xx   # iizuka PC
```
> ランダムMAC（プライベートアドレス）だと予約が効かないため、**対象PCの当該NICは「ランダムなハードウェアアドレス」をOFF**にしておく（有線推奨）。

---

## 3. 接続先PC ファイアウォール設定チェック

VPN払出 `192.168.201.0/24` からの着信を各対象PCで許可する。

### Windows（RDP受信）
- [ ] リモートデスクトップ有効（システム > リモートデスクトップ）
- [ ] 受信規則「リモート デスクトップ (TCP 受信)」の**スコープに `192.168.201.0/24` を追加**（既定の「ローカルサブネットのみ」だと不可）
```powershell
# 確認
Get-NetFirewallRule -DisplayGroup 'リモート デスクトップ' | Get-NetFirewallAddressFilter
# 追加（例）：既存許可に 192.168.201.0/24 を足す運用は環境に合わせて調整
```

### Linux（SSH受信）
- [ ] `sshd` 稼働
- [ ] firewalld/ufw で `192.168.201.0/24` からの22番を許可
```bash
# firewalld 例
sudo firewall-cmd --permanent --add-rich-rule='rule family=ipv4 source address=192.168.201.0/24 port port=22 protocol=tcp accept'
sudo firewall-cmd --reload
```

---

## 4. 投入前バックアップ

- [ ] `show config` を退避（TFTP or コンソールログ保存）
- [ ] 退避先・日時を記録：__________________________

---

## 5. 準備完了判定（すべて☑で段階3へ）

- [ ] 1章：PSK＋パスワード4件を発行・保管
- [ ] 2章：対象PC4台のMAC収集・予約IP確定
- [ ] 3章：対象PCのFW許可（Windows/Linux）
- [ ] 4章：投入前バックアップ取得
- [ ] 端末側：ランダムMAC無効化（対象NIC）

→ 完了後、[[リモートVPN投入手順]] 2章の**ステップA**から実機投入。

---

### 関連
- 投入手順：[[リモートVPN投入手順]]
- 設計本体：[[config_RTX1300]] §10（VPN）・§7（DHCP）
- 全体サマリ：[[00_サマリ]] 7章・9章B
