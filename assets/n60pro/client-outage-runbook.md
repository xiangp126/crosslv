# N60 Pro 客户端集体断网 — 排查记录与取证 runbook

> 设备：`n60pro-main`（磊科 Netcore N60 Pro，ImmortalWrt 24.10.5，MediaTek Filogic / mt76）
> 角色：主路由 `192.168.10.1`，**双重 NAT** 挂在上游 `192.168.1.1` 后面（WAN = dhcp，拿到 `192.168.1.2`）
> SSH：`ssh -l root -p 8822 192.168.10.1`

---

## 一、故障现象

- 客户端**突然集体失去互联网连接**，路由器本身看着没事。
- 已发生两次：**2026-06-14** 和 **2026-06-16**。
- **重启路由器 10.1 后立即恢复。**
- 关键线索：第二次断网时，**先尝试在主路由上 disable passwall，仍然上不了网；只有重启才恢复。**

---

## 二、排查结论（2026-06-17 已用现场快照实测确认）

> 早期曾推测"硬件流量卸载卡死 / passwall DNS 链卡死"。**这些已被实测推翻**，保留于文末"附：被排除的假设"以备参考。

### 决定性证据

2026-06-17 第三次断网时，**重启前先跑了 `capture-now`**，netmon 抓到了故障现场快照，时间线一目了然：

- WAN 口 **eth1 的 `rx_bytes` 从 00:43:01 起整整 31 分钟完全冻结**（一个字节没收到），而 `tx_bytes` 仍在缓慢增长（路由器在不停发 ARP 重试）。
- 对网关的 ARP：`192.168.1.1 dev eth1 INCOMPLETE`（发 ARP 无应答）。
- **没有 carrier-down 事件、内核零报错、`ifstatus wan` 仍显示 up** —— 链路"看着还在"，但接收通道已死 = **单向链路 / RX 同步丢失**。
- 只有重启（重新初始化 PHY）能恢复。

### 根因：WAN 物理链路（L1/L2）RX 死锁

故障发生在主路由 **WAN 口（eth1，2.5G Maxlinear GPY211C PHY ↔ 上游 192.168.1.1）的物理接收通路**。这解释了所有困惑：

- **为什么 disable passwall 没用** —— passwall 在 L4/DNS 层，根本够不到 eth1 收不收以太网帧、ARP 回不回。
- **为什么之前查不出** —— 故障时刻内核不报错、接口仍是 up，没有主动日志。
- **为什么必须重启** —— PHY/MAC 进入 RX 挂死，软件层看不到也清不掉。

### 物理诱因（两个叠加，都不是软件）

WAN 链路长期 marginal：一个 2.5G 口反复在 **100M↔1G↔2.5G** 之间协商（开机常落在 100M）。

1. **USB3 电磁干扰（EMI）**：用户曾因 wrt32x 外接 USB hub 反复导致 100M，换成更好的 hub 后消失 —— USB3 SuperSpeed 噪声谱（2.4–2.5GHz）辐射耦合进旁边的 WAN 网线。
2. **接头/线缆接触不良**：2026-06-17 **重新拔插 WAN 网线，速率当场从 100M 跳到 1G**（内核日志：Link Down → Link Up-1Gbps，`carrier_changes` 1→3）。链路建立后 RX/TX 错误计数为 0，说明问题在"协商/建链的余量"，不是持续噪声。

两者都在消耗同一份"链路余量"，叠加后把链路从"偶尔降速"逼成"彻底 RX 死锁"。

### 已排除（均有证据）

- **passwall / 流量卸载 / DNS**：够不到 L1/L2，disable 无效已证伪。
- **发热**：传感器 47–53°C（节流阈值 100°C+），无 throttle 记录；且故障发生在半夜。
- **主路由 SoC/内存/固件**：无崩溃、无硬件报错、无看门狗复位。
- **软件**：拔插网线即改变协商速率 = 纯硬件 PHY 行为，软件不可能随"动接头"而变。
- conntrack 打满（峰值 1965/30720）、内存耗尽（240MB 空闲）、定时重启（crontab 空）。

> 注：192.168.1.1 在 80/443 无 Web 界面，WAN 段仅它与主路由两台设备 —— 更可能是运营商光猫/网关，而非用户的 Linksys。

### 相关现状（排查时记录）

- passwall：`enabled=1`，sing-box 核心，单 VLESS 节点，`balancing_enable=0`，全局 DNS 劫持链 `dnsmasq → chinadns-ng(15354) → 直连 192.168.1.1 / 可信 dns2socks(15353) → sing-box socks(1070) → tcp://1.1.1.2:53`。
- passwall 自动 reload 来源：`monitor.sh`（子进程死了才重启，每 58s 查一次）+ `/etc/hotplug.d/iface/98-passwall`（WAN 每次 ifup 都 `passwall restart`）。reload 期间会短暂清空并重建 nft + DNS，造成客户端瞬断。
- 卸载配置：`firewall.@defaults[0].flow_offloading=1`、`flow_offloading_hw=1`，nft 有活跃 `flowtable inet fw4 ft { flags offload }`，`network.globals.packet_steering=1`。

---

## 三、已部署的取证看门狗（netmon）

用户选择：**只装监控抓现行，先不改转发配置。**

落在路由器 **`/root/netmon/`**（overlay 分区，**重启不丢**），procd 服务 `/etc/init.d/netmon`（**已开机自启**）。

| 文件 | 作用 |
|---|---|
| `monitor.sh` | 守护进程。每 30s 探测网关 / 两个公网 IP / passwall DNS；心跳写入 RAM 环 `/tmp/netmon/heartbeat.ring`（低闪存磨损）；状态 OK↔BAD 翻转时自动 dump 全量快照；每 30 分钟把心跳环刷一份到磁盘 `heartbeat.log`。 |
| `snapshot.sh <reason>` | 全量取证：探测矩阵、心跳时间线、DNS 链分层测试、路由/WAN、conntrack、**WAN 链路速率/协商次数**、eth1+br-lan 收发字节、nft flowtable、passwall 进程、dmesg 尾部。落到 `/root/netmon/snapshots/`，保留最近 25 份。 |
| `capture-now` | 手动取证按钮，直接调 `snapshot.sh manual`。 |
| `/etc/init.d/netmon` | procd 服务，开机自启 + 进程崩溃自动重启。 |

心跳每行含 `sp=`（WAN 协商速率）、`cc=`（carrier_changes）、`rx=/tx=`（WAN 收发字节）。
自动快照触发：状态 OK↔BAD 翻转、**WAN 速率变化（100M↔1G↔2.5G）**、手动 `capture-now`。
关键判据：断网时 **`rx` 冻结不涨而 `tx` 仍涨 + 网关 ARP `INCOMPLETE`** = WAN 链路 RX 死锁。

---

## 四、下次断网时怎么做（最重要）

**客户端一断网、在重启路由器之前**，SSH 进去跑这一条：

```sh
/root/netmon/capture-now
```

它会立刻把现场 dump 到 `/root/netmon/snapshots/`。**然后照常重启恢复网络即可。**

### 事后读快照判读

读最新的 `/root/netmon/snapshots/snap-*.txt` 与心跳时间线：

- **eth1 `rx` 冻结、`tx` 仍涨、网关 ARP `INCOMPLETE`、`sp=` 此前掉到 100M 或在抖** → **确诊 WAN 链路 RX 死锁**（物理层）→ 对策见第六节（换线/远离 USB3/锁速率），不是软件问题。
- 只有 `DNS ... FAIL`、`internet` 仍 ok → passwall DNS 链问题（次要可能）。
- 网关、公网全 `FAIL` 但 `rx` 仍在涨 → 上游 `192.168.1.1`（光猫）侧问题。

---

## 五、一键 teardown（环境彻底变好后，清掉本次所有改动）

本次调查在路由器 10.1 上部署的**全部东西**：

| 改动 | 路径 |
|---|---|
| netmon 看门狗脚本 | `/root/netmon/`（monitor.sh / snapshot.sh / capture-now / snapshots/ / heartbeat.log） |
| netmon 服务（开机自启） | `/etc/init.d/netmon` |
| netmon 运行态（RAM） | `/tmp/netmon/` |
| WAN 锁 1000M（持久化） | `/etc/hotplug.d/net/20-wan-lock-1000` |
| WAN 锁 1000M（当前生效的 advertise） | ethtool 运行态，重启自动清除 |

**一键清除**（脚本已部署在路由器上，会自删）：

```sh
ssh -l root -p 8822 192.168.10.1 /root/teardown-netmon.sh
```

它会：移除 WAN 锁的 hotplug、停用并删除 netmon 服务与全部文件。删完后会提示：当前生效的"1000M-only"会在**下次重启自动恢复默认**；若想立刻恢复全速自协商（约 10 秒 WAN 闪断）再手动跑 `ethtool -s eth1 autoneg on advertise 0x02f`。

**手动等价命令**（万一脚本已被删/不在）：

```sh
# 1) 去掉 WAN 1000M 锁
rm -f /etc/hotplug.d/net/20-wan-lock-1000
ethtool -s eth1 autoneg on advertise 0x02f   # 立刻恢复 10/100/1000 自协商；或重启恢复默认(含2.5G)
# 2) 去掉 netmon 看门狗
/etc/init.d/netmon disable; /etc/init.d/netmon stop
rm -f /etc/init.d/netmon
rm -rf /root/netmon /tmp/netmon
```

> 只想去掉其中一项也可以：上面第 1 段只关 WAN 锁，第 2 段只关 netmon。

---

## 六、对策（根因为物理层，按性价比排序）

1. **换 WAN 网线**：用屏蔽 Cat6（STP/FTP），两端用力插紧。同时治"接触不良"和"EMI"（屏蔽线抗 USB3 干扰）。最便宜、命中率最高。
2. **让 WAN 网线远离 USB3 设备/hub**（wrt32x、wrt1200ac 的 USB 外设）——用户已验证过的 EMI 因素。
3. **WAN 锁定到 1000M —— 已于 2026-06-17 应用。**
   重要：ethtool 显示上游 192.168.1.1 **只广播到 1000baseT/Full（不支持 2.5G）**，故链路本就上不了 2.5G；锁 1000M 的真正作用是**去掉 10/100M 低速回退**，让链路要么稳在 1G、要么直接 down（被 netmon 抓到），不再"偷偷降 100M 苟着"。
   做法（不能用 netifd 的 `option speed`，那会 `autoneg off` 强制、千兆下协商不上；必须 autoneg 开 + 限制 advertise）：
   - 立即生效：`ethtool -s eth1 autoneg on advertise 0x020`（`0x020`=仅 1000baseT/Full）。会触发重新协商，**约 10 秒 WAN 闪断**后回到 1G。
   - 持久化（已装）：`/etc/hotplug.d/net/20-wan-lock-1000`，在 eth1 每次 up 时套用上面的 ethtool。
   - 撤销：`rm -f /etc/hotplug.d/net/20-wan-lock-1000 && ethtool -s eth1 autoneg on advertise 0x02f`（恢复 10/100/1000；连 2.5G 用 `0x1802f` 或重启）。
4. 可选：netmon 加 WAN 自愈（检测 RX 死锁自动 `ip link set eth1 down/up`），把手动重启变成自动恢复（用户暂未采用）。
5. 长期：配远程 syslog（`log_ip` 指向常开 NAS/PC）或加大 `log_size`，根治"重启即丢日志"。

---

## 附：被排除的假设（保留以备参考）

早期在拿到现场快照前，曾按"重启能修、disable 修不了"推测过以下方向，**均已被 2026-06-17 的实测推翻**：

- **MediaTek 硬件流量卸载（`flow_offloading_hw=1` + WED）卡死转发通路**：Filogic 著名顽疾、症状高度吻合，一度列为头号。但实测断网时连路由器自身对网关的 ARP 都失败、eth1 RX 完全冻结，属 L1/L2 链路层，而非 FORWARD 卸载通路。
- **passwall DNS 链卡死 / 单节点代理死亡**：passwall 在 L4/DNS 层，disable 无效已直接证伪。
