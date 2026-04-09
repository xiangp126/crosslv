# 磊科 N60 Pro 刷入 ImmortalWrt 完整教程

> 本教程使用 ImmortalWrt 官方提供的 U-Boot（BL31-UBOOT.FIP）。该 U-Boot **没有 Web 刷机界面**，需要通过 TFTP 方式刷入固件。刷机过程建议使用 **Windows** 电脑（Linux / Mac 的 TFTP 工具实测可能失败）。

---

## 准备工作

### 需要的文件

从 ImmortalWrt 固件选择器下载（搜索 Netcore N60 Pro）：
https://firmware-selector.immortalwrt.org/

需要下载以下 **3 个文件**：

| 按钮名称 | 用途 |
|----------|------|
| **BL31-UBOOT.FIP** | 第三方 U-Boot 引导程序，刷入 FIP 分区 |
| **KERNEL** | recovery 镜像（initramfs），通过 TFTP 刷入 |
| **SYSUPGRADE** | ImmortalWrt 完整系统固件，最后通过 Web 界面刷入 |

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

连接后先查看分区表：

```bash
cat /proc/mtd
```

输出如下：

```
dev:    size   erasesize  name
mtd0: 08000000 00020000 "spi0.1"     ← 整个 ROM（完整镜像）
mtd1: 00100000 00020000 "BL2"        ← 最底层引导程序
mtd2: 00080000 00020000 "u-boot-env" ← U-Boot 环境变量
mtd3: 00200000 00020000 "Factory"    ← 无线校准数据 + MAC 地址（每台唯一，必备！）
mtd4: 00200000 00020000 "FIP"        ← 原厂 U-Boot（刷机会被覆盖，必备！）
mtd5: 07280000 00020000 "ubi"        ← 原厂系统固件（恢复用，必备！）
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

下载后验证 md5，确保文件完整：

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

刷完 U-Boot 后，擦除 ubi 分区（原厂系统），让路由器重启后进入 TFTP 拉取模式：

```bash
mtd erase ubi
reboot
```

路由器会自动重启。由于系统已被擦除，U-Boot 启动后找不到可用系统，会自动进入 TFTP 恢复模式，不断向网络请求 recovery 镜像。

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
3. 确认 **Server interfaces** 选择的是你网线连接的网卡（IP 为 192.168.1.254）

### 5.4 路由器自动拉取文件

路由器重启后会每隔约 1 秒向 `192.168.1.254` 发起 TFTP 请求。在 tftpd64 的 **Log Viewer** 中你会看到类似这样的日志：

```
Connection received from 192.168.1.1 on port 3874
Read request for file <immortalwrt-mediatek-filogic-netcore_n60-pro-initramfs-recovery.itb>
```

如果文件名匹配且路径正确，传输会自动开始，日志显示：

```
OACK: <timeout=5,blksize=1468,>
<immortalwrt-mediatek-filogic-netcore_n60-pro-initramfs-recovery.itb>: sent 9554 blks, 14024704 bytes in 2 s.
```

看到 `sent ... bytes` 就说明传输成功了。如果一直报 `error 2 in system call CreateFile 系统找不到指定的文件`，请检查：
- 文件名是否与日志中请求的完全一致
- tftpd64 的 Current Directory 是否指向文件所在目录
- Server interfaces 是否选对了网卡

传输完成后，路由器会自动刷入并启动 recovery 系统，等待 1~2 分钟即可。

---

## 第六步：通过 Web 界面刷入完整系统（SYSUPGRADE）

recovery 系统启动后，浏览器访问 **`192.168.1.1`**，进入 ImmortalWrt 的 LuCI 管理界面。

在「系统 → 备份/升级 → 刷写新的固件」中上传 **SYSUPGRADE** 文件，点击刷写，等待完成。

> 刷写过程中不要断电、不要拔网线。

---

## 第七步：进入 ImmortalWrt 系统

刷写完成后路由器自动重启，浏览器访问：

- 地址：**`192.168.1.1`**（ImmortalWrt 默认网关地址）
- 用户名：**`root`**
- 密码：**默认无密码**

能进入 LuCI 后台就大功告成了！

> 注意：ImmortalWrt 默认 IP 是 `192.168.1.1`，与磊科官方固件的 `192.168.0.1` 不同。刷机完成后记得把电脑网卡改回 DHCP 自动获取。

---

## 附一：恢复官方固件

进入 ImmortalWrt 后，通过 SSH 连接路由器（192.168.1.1，用户名 root），将之前备份的 `mtd5`（ubi 分区）上传到 `/tmp`，执行：

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
| 刷固件方式 | **TFTP**（路由器主动拉取文件） | **Web 界面**上传 |
| 是否需要 tftpd64 | 是（仅支持 Windows） | 不需要 |
| 是否自带 DHCP | 否（需手动设置电脑 IP 为 192.168.1.254） | 是（电脑自动获取 IP） |
| 操作难度 | 较高 | 较低 |
| 适合人群 | 想用纯官方固件链的用户 | 追求方便快捷的用户 |

如果觉得 TFTP 方式太麻烦，可以选择社区大佬制作的 U-Boot，刷入后按住 reset 通电即可进入 Web 刷机界面，直接上传固件，流程简单很多。两种 U-Boot 都写入 mtd4（FIP）分区，后续使用和效果没有区别。
