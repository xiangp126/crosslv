# netmon + WAN-lock 部署脚本（n60pro-main / 192.168.10.1）

本目录是部署在主路由 10.1（ImmortalWrt）上、用于排查并缓解 WAN 断网的全部脚本的**仓库镜像**。
背景、根因、判读方法见上级目录的 [`client-outage-runbook.md`](../client-outage-runbook.md)。
脚本中**不含任何凭据/密钥**（已扫描确认）。

## 文件 → 路由器上的部署位置

| 仓库文件 | 部署到路由器 | 作用 |
|---|---|---|
| `monitor.sh` | `/root/netmon/monitor.sh` | 看门狗主循环：每 30s 探测，记心跳，断网/速率变化自动抓快照 |
| `snapshot.sh` | `/root/netmon/snapshot.sh` | 全量取证（探测矩阵、心跳、DNS 链、路由、conntrack、WAN 链路速率、收发字节、dmesg…） |
| `capture-now` | `/root/netmon/capture-now` | 手动取证按钮 |
| `netmon.init` | `/etc/init.d/netmon` | procd 服务，开机自启 + 崩溃自启 |
| `wan-lock.sh` | `/root/wan-lock.sh` | 把 WAN 锁到 1000baseT/Full；25s 内到不了 1G 则自动回退，绝不卡死 WAN |
| `99-wan-lock-1000.iface-hotplug` | `/etc/hotplug.d/iface/99-wan-lock-1000` | wan ifup（含开机）时调用 `wan-lock.sh`（flag 防循环） |
| `teardown-netmon.sh` | `/root/teardown-netmon.sh` | 一键清除以上所有（自删） |

## 重新部署（环境重装后）

```sh
# netmon
scp -P 8822 monitor.sh snapshot.sh capture-now root@192.168.10.1:/root/netmon/
scp -P 8822 netmon.init root@192.168.10.1:/etc/init.d/netmon
ssh -p 8822 root@192.168.10.1 'chmod +x /root/netmon/*.sh /root/netmon/capture-now /etc/init.d/netmon; /etc/init.d/netmon enable; /etc/init.d/netmon start'
# WAN lock
scp -P 8822 wan-lock.sh root@192.168.10.1:/root/wan-lock.sh
scp -P 8822 99-wan-lock-1000.iface-hotplug root@192.168.10.1:/etc/hotplug.d/iface/99-wan-lock-1000
ssh -p 8822 root@192.168.10.1 'chmod +x /root/wan-lock.sh /etc/hotplug.d/iface/99-wan-lock-1000; /root/wan-lock.sh'
# teardown helper
scp -P 8822 teardown-netmon.sh root@192.168.10.1:/root/teardown-netmon.sh
ssh -p 8822 root@192.168.10.1 'chmod +x /root/teardown-netmon.sh'
```

## 一键清除

```sh
ssh -p 8822 root@192.168.10.1 /root/teardown-netmon.sh
```
