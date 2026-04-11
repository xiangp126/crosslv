# 磊科 N60 Pro 刷入 ImmortalWrt 完整教程

> 本教程使用 ImmortalWrt 官方提供的 U-Boot（BL31-UBOOT.FIP）。该 U-Boot **没有 Web 刷机界面**，需要通过 TFTP 方式刷入固件。刷机过程建议使用 **Windows** 电脑（Linux / Mac 的 TFTP 工具实测可能失败）。

---

## 刷机原理

在开始之前，先了解一下整个刷机流程的逻辑，知道每一步在做什么、为什么要这样做。

### 分区结构

N60 Pro 的闪存分为以下分区：

```
mtd0: 整个 ROM（完整镜像，包含下面所有分区）
mtd1: BL2         ← 最底层引导程序，上电第一个运行
mtd2: u-boot-env  ← U-Boot 的环境变量/配置
mtd3: Factory     ← 无线射频校准数据 + MAC 地址（每台机器唯一）
mtd4: FIP         ← U-Boot 引导程序（刷机写入新 U-Boot 的位置）
mtd5: ubi         ← 系统固件（原厂系统 / ImmortalWrt 装在这里）
```

各分区相互独立，启动顺序为 **BL2（mtd1）→ U-Boot（mtd4）→ 系统固件（mtd5）**。只要 mtd1 和 mtd4 是完好的，U-Boot 就能正常启动。即使 mtd5 被擦除或刷坏，U-Boot 会检测到系统无法启动并进入恢复模式，让你重新刷入固件。因此刷完第三方 U-Boot 后，日常折腾固件基本不怕变砖。

mtd0 不是一个独立分区，而是整块闪存芯片的完整映射（mtd0 = mtd1 + mtd2 + mtd3 + mtd4 + mtd5）。整个刷机过程只修改了 mtd4 和 mtd5，但由于它们是 mtd0 的一部分，mtd0 的内容也会随之改变。所以 mtd0 的备份必须在刷机之前完成。

### 关于 Factory 分区（mtd3）

mtd3 存储的是出厂时用专业射频仪器逐台测量写入的硬件校准数据，包括每颗射频芯片在各频段、各功率档位下的误差补偿值，以及 MAC 地址等。这些数据跟系统无关——无论原厂固件还是 ImmortalWrt，启动时都会读取 mtd3 来驱动 WiFi 硬件。丢失后 WiFi 信号会严重异常，且无法从其他途径恢复，务必备份。

### 为什么要先刷一个精简 Linux（KERNEL/recovery）？

U-Boot 只是一个引导程序，能力非常有限。它能做的事只有：通过 TFTP 把文件拉到内存里，然后引导启动它。它不具备将完整系统固件写入闪存 ubi 分区的能力——这涉及 UBI 卷管理、文件系统格式化、数据校验等复杂操作，需要一个运行中的 Linux 系统来完成。

所以刷机是一个三步接力：

1. **U-Boot** 通过 TFTP 将 KERNEL（recovery 镜像）拉到内存并引导启动
2. **KERNEL（recovery）** 是一个精简但完整的 Linux 系统，直接运行在内存中（initramfs），不依赖闪存上的任何数据。它启动后提供 LuCI Web 界面和完整的 mtd/ubi 写入工具
3. 通过 recovery 的 Web 界面上传 **SYSUPGRADE** 固件，由它负责将完整系统正确写入闪存

> 社区大佬制作的 U-Boot（如恩山论坛版）之所以能跳过 KERNEL 这一步，是因为他们在 U-Boot 里额外集成了 Web 界面和直接写入 ubi 分区的功能，相当于把 recovery 的部分能力塞进了 U-Boot 里，所以可以一步到位。

### 什么是 U-Boot？

U-Boot 全称 **Das U-Boot**（Universal Boot Loader，通用引导加载程序），是嵌入式设备上广泛使用的开源引导程序。路由器上电后，它负责初始化硬件、加载操作系统内核并启动。文件名中的 BL31 指 ARM Trusted Firmware 的第三阶段引导，FIP 是 Firmware Image Package（固件镜像包）的缩写。

---

## 准备工作

### 需要的文件

从 ImmortalWrt 固件选择器下载（搜索 Netcore N60 Pro）：
https://firmware-selector.immortalwrt.org/

需要下载以下 **3 个文件**：

| 按钮名称 | 用途 |
|----------|------|
| **BL31-UBOOT.FIP** | 第三方 U-Boot 引导程序，刷入 mtd4（FIP）分区 |
| **KERNEL** | recovery 镜像（initramfs），通过 TFTP 传入内存启动 |
| **SYSUPGRADE** | ImmortalWrt 完整系统固件，通过 recovery 的 Web 界面刷入 mtd5 |

### 需要的工具

- 一根网线（进入 U-Boot 后 WiFi 不可用，必须有线连接）
- SSH 工具：推荐 **MobaXterm**（支持 SSH 终端 + 文件上传）
- TFTP 服务器：**tftpd64**（Windows），下载地址 https://github.com/PJO2/tftpd64/releases/
---

## 第一步：开启 SSH

登录磊科官方后台（默认地址 `192.168.0.1`），在「应用 → 远程访问」中确认 SSH 已开启。

---

## 第二步：备份原厂所有分区（非常重要！）

用 MobaXterm 通过 SSH 连接路由器（这一步可以用 WiFi）：

- 用户名：`useradmin`（不是 root）
- 密码：后台管理密码

连接后先查看分区表确认：

```bash
cat /proc/mtd
```

由于路由器 /tmp 空间有限，需要分两批备份。

### 第一批：备份 mtd1 ~ mtd5

```bash
dd if=/dev/mtd1 of=/tmp/mtd1
dd if=/dev/mtd2 of=/tmp/mtd2
dd if=/dev/mtd3 of=/tmp/mtd3
dd if=/dev/mtd4 of=/tmp/mtd4
dd if=/dev/mtd5 of=/tmp/mtd5
```

> mtd5 文件较大，备份时间会长一些，耐心等待。

备份完成后，将 /tmp 下的文件下载到电脑。MobaXterm 可以用左侧文件管理器拖拽，也可以在电脑终端用以下命令：

```bash
ssh useradmin@192.168.0.1 cat /tmp/mtd1 > mtd1
ssh useradmin@192.168.0.1 cat /tmp/mtd2 > mtd2
ssh useradmin@192.168.0.1 cat /tmp/mtd3 > mtd3
ssh useradmin@192.168.0.1 cat /tmp/mtd4 > mtd4
ssh useradmin@192.168.0.1 cat /tmp/mtd5 > mtd5
```

下载后验证 md5，确保文件完整无损：

```bash
# 路由器上执行
md5sum /tmp/mtd*

# 电脑上对比（Windows 可用 certutil -hashfile 文件名 MD5）
```

确认 md5 一致后，删除路由器上的备份文件腾出空间：

```bash
rm /tmp/mtd*
```

### 第二批：备份 mtd0（整个 ROM 完整镜像）

```bash
dd if=/dev/mtd0 of=/tmp/mtd0
```

同样下载到电脑并验证 md5：

```bash
ssh useradmin@192.168.0.1 cat /tmp/mtd0 > mtd0
```

> ⚠️ /tmp 是内存目录，路由器断电就会丢失！备份后务必立即下载到电脑。
>
> ⚠️ 建议云盘 + 本地双备份。

---

## 第三步：上传并刷入 U-Boot（BL31-UBOOT.FIP）

将下载好的 BL31-UBOOT.FIP 文件上传到路由器 `/tmp` 目录。

> 如果 scp 报错，可以用以下方式上传：
> ```bash
> cat immortalwrt-24.10.5-mediatek-filogic-netcore_n60-pro-bl31-uboot.fip | ssh useradmin@192.168.0.1 "cat - > /tmp/uboot.fip"
> ```

上传后验证 sha256，与官网页面显示的值对比：

```bash
sha256sum /tmp/uboot.fip
```

确认一致后，执行刷入：

```bash
mtd write /tmp/uboot.fip FIP
```

看到以下输出说明写入成功：

```
Unlocking FIP ...
Writing from /tmp/uboot.fip to FIP ...
```

> ⚠️ 写入过程中千万不要断电！

---

## 第四步：擦除原厂系统并重启

刷完 U-Boot 后，擦除 ubi 分区（原厂系统），让路由器重启后进入 TFTP 恢复模式：

```bash
mtd erase ubi
reboot
```

路由器会自动重启。由于 mtd5 已被擦除，U-Boot 启动后找不到可用系统，会自动进入 TFTP 恢复模式，不断向网络中 IP 为 `192.168.1.254` 的设备请求 recovery 镜像。

---

## 第五步：通过 TFTP 刷入 recovery 镜像（KERNEL）

**⚡ 从这一步开始必须使用 Windows 电脑 + 网线连接路由器！**

### 5.1 设置电脑网络

将电脑的有线网卡 IP 手动设置为：

- IP 地址：`192.168.1.254`
- 子网掩码：`255.255.255.0`
- 网关：`192.168.1.1`

### 5.2 重命名 KERNEL 文件

路由器 U-Boot 请求的文件名是固定的，需要将下载的 KERNEL 文件重命名为：

```
immortalwrt-mediatek-filogic-netcore_n60-pro-initramfs-recovery.itb
```

> 你也可以先不改名，启动 tftpd64 后在日志中看到路由器实际请求的文件名，再据此重命名。

### 5.3 启动 tftpd64

1. 打开 **tftpd64**
2. 将 **Current Directory** 设置为上面重命名后的 KERNEL 文件所在的目录
3. 确认 **Server interfaces** 选择的是你网线连接的网卡（IP 为 `192.168.1.254`）

### 5.4 路由器自动拉取文件

路由器重启后会每隔约 1 秒向 `192.168.1.254` 发起 TFTP 请求。在 tftpd64 的 **Log Viewer** 中你会看到类似这样的日志：

**文件名不匹配或找不到时（失败）：**
```
Connection received from 192.168.1.1 on port 3874
Read request for file <immortalwrt-mediatek-filogic-netcore_n60-pro-initramfs-recovery.itb>
File <immortalwrt-mediatek-filogic-netcore_n60-pro-initramfs-recovery.itb> : error 2 in system call CreateFile 系统找不到指定的文件。
```

**文件名匹配且传输成功时：**
```
OACK: <timeout=5,blksize=1468,>
<immortalwrt-mediatek-filogic-netcore_n60-pro-initramfs-recovery.itb>: sent 9554 blks, 14024704 bytes in 2 s. 0 blk resent
```

看到 `sent ... bytes` 就说明传输成功了。如果一直报错，请检查：
- 文件名是否与日志中请求的完全一致
- tftpd64 的 Current Directory 是否指向文件所在目录
- Server interfaces 是否选对了网卡

传输完成后，路由器会自动启动 recovery 系统，等待 1~2 分钟即可。

---

## 第六步：通过 Web 界面刷入完整系统（SYSUPGRADE）

recovery 系统启动后，浏览器访问 **`192.168.1.1`**，进入 ImmortalWrt 的 LuCI 管理界面。

在「系统 → 备份/升级 → 刷写新的固件」中上传 **SYSUPGRADE** 文件，点击刷写，等待完成。

> ⚠️ 刷写过程中不要断电、不要拔网线。

---

## 第七步：进入 ImmortalWrt 系统

刷写完成后路由器自动重启，浏览器访问：

- 地址：**`192.168.1.1`**（ImmortalWrt 默认网关地址，区别于磊科原厂的 `192.168.0.1`）
- 用户名：**`root`**
- 密码：**默认无密码**

能进入 LuCI 后台就大功告成了！刷机完成后记得把电脑网卡改回 DHCP 自动获取。

---

## 附一：恢复官方固件

进入 ImmortalWrt 后，通过 SSH 连接路由器（`192.168.1.1`，用户名 `root`），将之前备份的 mtd5 上传到 `/tmp`，执行：

```bash
mtd write /tmp/mtd5 ubi
reboot
```

重启后即可恢复原厂系统，访问 `192.168.0.1` 进入官方后台。

也可以重新进入 U-Boot 的 TFTP 模式（断电 → 按住 reset → 通电 → 等 8 秒松开），用 tftpd64 传入原厂备份来恢复。

---

## 附二：两种 U-Boot 的区别

| | ImmortalWrt 官方 U-Boot（本教程） | 恩山社区大佬制作的 U-Boot |
|---|---|---|
| 来源 | 固件选择器下载的 BL31-UBOOT.FIP | 恩山论坛（如 1715173329 大佬版） |
| 刷固件方式 | **TFTP**（路由器主动拉取文件） | **Web 界面**直接上传 |
| 是否需要 tftpd64 | 是（仅 Windows 可用） | 不需要 |
| 是否需要先刷 KERNEL | 是（U-Boot 自身无法写入 ubi 分区，需要先启动一个临时 Linux 系统来完成写入） | 不需要（U-Boot 内集成了写入 ubi 的能力） |
| 是否自带 DHCP | 否（需手动设置电脑 IP 为 `192.168.1.254`） | 是（电脑自动获取 IP） |
| 操作难度 | 较高 | 较低 |
| 适合人群 | 想用纯官方固件链的用户 | 追求方便快捷的用户 |

两种 U-Boot 都写入 mtd4（FIP）分区，后续使用和效果没有区别，只是刷机过程的便捷程度不同。
