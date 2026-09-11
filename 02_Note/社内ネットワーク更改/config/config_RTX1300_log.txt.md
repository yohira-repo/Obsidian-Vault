①  事前投入ブロック

```
 console character ascii
> console lines infinity
> login password alphacmc
Error: Invalid command name
> login password 'alphacmc'
Error: Invalid command name
>
> administrator password Alphacmc1$
Error: Administrator use only

#
# console character ascii
# console lines infinity
# login password Alphacmc1$
Error: Invalid command name
# login password 'Alphacmc1$'
Error: Invalid command name
# administrator password Alphacmc1$
Error: Insufficient or too many parameters
+# login password
エラー: コマンド名を確認してください
# login
エラー: コマンド名を確認してください
#
#
#
#
# administrator password
Old_Password:
New_Password:
New_Password(Confirm):
Password Strength : Strong
#

#
# timezone +09:00
#
# ip lan1 address 192.168.200.1/24
# vlan lan3/1 802.1q vid=10
# vlan lan3/2 802.1q vid=20
# vlan lan3/3 802.1q vid=30
# ip lan3/1 address 192.168.128.1/24
# ip lan3/2 address 192.168.64.1/24
# ip lan3/3 address 192.168.192.1/24
#

# dns server 210.145.254.170 125.170.93.234 8.8.8.8 1.1.1.1
# dns service recursive
# dhcp service server
# dhcp server rfc2131 compliant except remain-silent
# dhcp scope 10 192.168.128.100-192.168.128.199/24 gateway 192.168.128.1 expire
 12
# dhcp scope option 10 dns=210.145.254.170,125.170.93.234,8.8.8.8,1.1.1.1
# dhcp scope 20 192.168.64.100-192.168.64.199/24 gateway 192.168.64.1 expire 12
# dhcp scope option 20 dns=210.145.254.170,125.170.93.234,8.8.8.8,1.1.1.1
# dhcp scope 30 192.168.192.100-192.168.192.199/24 gateway 192.168.192.1 expire
 4
# dhcp scope option 30 dns=210.145.254.170,125.170.93.234,8.8.8.8,1.1.1.1
# dhcp scope 40 192.168.200.100-192.168.200.199/24 gateway 192.168.200.1 expire
 12

---
C:\Users\alphauser>ping 192.168.200.1

192.168.200.1 に ping を送信しています 32 バイトのデータ:
192.168.200.1 からの応答: バイト数 =32 時間 =25ms TTL=255
192.168.200.1 からの応答: バイト数 =32 時間 <1ms TTL=255
192.168.200.1 からの応答: バイト数 =32 時間 <1ms TTL=255
192.168.200.1 からの応答: バイト数 =32 時間 <1ms TTL=255

192.168.200.1 の ping 統計:
    パケット数: 送信 = 4、受信 = 4、損失 = 0 (0% の損失)、
ラウンド トリップの概算時間 (ミリ秒):
    最小 = 0ms、最大 = 25ms、平均 = 6ms
----


# ip filter 2000 reject * 192.168.128.0/24 * * *
# ip filter 2001 reject * 192.168.192.0/24 * * *
# ip filter 2002 reject * 192.168.200.0/24 * * *
# ip filter 2003 reject * 192.168.201.0/24 * * *
# ip filter 2004 reject * 10.0.3.0/24 * * *
# ip filter 2009 pass   * * * * *
# ip filter 2010 reject * 192.168.200.0/24 * * *
# ip filter 2011 reject * 192.168.201.0/24 * * *
# ip filter 2019 pass   * * * * *
# ip filter 2020 reject * 192.168.0.0/16 * * *
# ip filter 2021 reject * 10.0.0.0/8 * * *
# ip filter 2022 reject * 172.16.0.0/12 * * *
# ip filter 2029 pass   * * * * *
# ip filter 2039 pass   * * * * *
# ip filter 2100 reject 192.168.128.20   192.168.64.0/24 * * *
# ip filter 2101 pass   192.168.128.0/24 192.168.64.0/24 * * *
# ip filter 2102 pass   192.168.200.0/24 192.168.64.0/24 * * *
# ip filter 2103 pass   192.168.201.32/28 192.168.64.0/24 tcp * 3389
# ip filter 2104 pass   192.168.201.32/28 192.168.64.0/24 tcp * 22
# ip filter dynamic 3000 192.168.128.0/24  192.168.64.0/24 tcp
# ip filter dynamic 3001 192.168.128.0/24  192.168.64.0/24 udp
# ip filter dynamic 3010 192.168.200.0/24  192.168.64.0/24 tcp
# ip filter dynamic 3011 192.168.200.0/24  192.168.64.0/24 udp
# ip filter dynamic 3020 192.168.201.32/28 192.168.64.0/24 tcp
# ip lan3/1 secure filter in  2010 2011 2019
# ip lan3/2 secure filter in  2000 2001 2002 2003 2004 2009
# ip lan3/2 secure filter out 2100 2101 2102 2103 2104 dynamic 3000 3001 3010 3
011 3020
# ip lan3/3 secure filter in  2020 2021 2022 2029
# ip lan1   secure filter in  2039
#

---
# ip filter 2000 reject * 192.168.128.0/24 * * *
# ip filter 2001 reject * 192.168.192.0/24 * * *
# ip filter 2002 reject * 192.168.200.0/24 * * *
# ip filter 2003 reject * 192.168.201.0/24 * * *
# ip filter 2004 reject * 10.0.3.0/24 * * *
# ip filter 2009 pass   * * * * *
# ip filter 2010 reject * 192.168.200.0/24 * * *
# ip filter 2011 reject * 192.168.201.0/24 * * *
# ip filter 2019 pass   * * * * *
# ip filter 2020 reject * 192.168.0.0/16 * * *
# ip filter 2021 reject * 10.0.0.0/8 * * *
# ip filter 2022 reject * 172.16.0.0/12 * * *
# ip filter 2029 pass   * * * * *
# ip filter 2039 pass   * * * * *
# ip filter 2100 reject 192.168.128.20   192.168.64.0/24 * * *
# ip filter 2101 pass   192.168.128.0/24 192.168.64.0/24 * * *
# ip filter 2102 pass   192.168.200.0/24 192.168.64.0/24 * * *
# ip filter 2103 pass   192.168.201.32/28 192.168.64.0/24 tcp * 3389
# ip filter 2104 pass   192.168.201.32/28 192.168.64.0/24 tcp * 22
# ip filter dynamic 3000 192.168.128.0/24  192.168.64.0/24 tcp
# ip filter dynamic 3001 192.168.128.0/24  192.168.64.0/24 udp
# ip filter dynamic 3010 192.168.200.0/24  192.168.64.0/24 tcp
# ip filter dynamic 3011 192.168.200.0/24  192.168.64.0/24 udp
# ip filter dynamic 3020 192.168.201.32/28 192.168.64.0/24 tcp
# ip lan3/1 secure filter in  2010 2011 2019
# ip lan3/2 secure filter in  2000 2001 2002 2003 2004 2009
# ip lan3/2 secure filter out 2100 2101 2102 2103 2104 dynamic 3000 3001 3010 3
011 3020
# ip lan3/3 secure filter in  2020 2021 2022 2029
# ip lan1   secure filter in  2039
# ip filter 200003 reject 192.168.0.0/16 * * * *
# ip filter 200020 reject * * udp,tcp 135 *
# ip filter 200021 reject * * udp,tcp * 135
# ip filter 200022 reject * * udp,tcp netbios_ns-netbios_ssn *
# ip filter 200023 reject * * udp,tcp * netbios_ns-netbios_ssn
# ip filter 200024 reject * * udp,tcp 445 *
# ip filter 200025 reject * * udp,tcp * 445
# ip filter 200026 restrict * * tcpfin * www,21,nntp
# ip filter 200027 restrict * * tcprst * www,21,nntp
# ip filter 200030 pass * 192.168.0.0/16 icmp * *
# ip filter 200032 pass * 192.168.0.0/16 tcp * ident
# ip filter 200099 pass * * * * *
# ip filter 200100 reject * * * * *
# ip filter dynamic 200080 * * ftp
# ip filter dynamic 200081 * * domain
# ip filter dynamic 200082 * * www
# ip filter dynamic 200083 * * smtp
# ip filter dynamic 200084 * * pop3
# ip filter dynamic 200085 * * ssh
# ip filter dynamic 200098 * * tcp
# ip filter dynamic 200099 * * udp
# save
セーブ中... CONFIG0 終了
#
```