# mlxconfig 怎么和 firmware 通信——完整、修正版

下面我用一条命令 `sudo mlxconfig -d /dev/mst/mt4131_pciconf0 set NUM_OF_PF=4` 当线索，从硬件到代码逐层讲清楚。

---

## 总览：一次配置修改要经过的七层

```
mlxconfig 进程（用户态）
  ↓ ioctl()
mst 内核模块
  ↓ pci_read/write_config_dword()  ← 注意：是 PCI 配置空间，不是 BAR0
PCIe Root Complex
  ↓ PCIe Configuration TLP
CX8 的 vendor-specific PCI capability（CR-space 后门）
  ↓ 内部总线
CX8 的 Command Interface（CR-space 里的一段共享内存 + doorbell）
  ↓ 触发
firmware 主循环 → ACCESS_REGISTER handler → MNVDA → SPI 控制器 → QSPI Flash
```

每一层都做一件具体的事，下面拆开看。

---

## 第一层：PCIe 给 CX8 两套"门"

CX8 上电、BIOS 枚举之后，会得到两类对外可访问的地址空间：

**(1) Memory-Mapped I/O（BAR0、BAR2、BAR4）**
BIOS 给设备分配若干段物理内存地址。`lspci -vvs <bdf>` 里 "Region 0" 那一行就是 BAR0，CX 系列 BAR0 一般是 **16MB 量级**，不是几十 MB。这段地址内部映射到设备的 **CR-space**（Configuration Register Space）——所有命令队列、doorbell、状态寄存器都在 CR-space 里。

**(2) PCI Configuration Space**
每个 PCIe 设备都有一段独立的 4KB 配置空间（标准头 + capability 链）。NVIDIA/Mellanox 在 capability 链里塞了一个 **vendor-specific capability**（典型在 config offset 0x58 一带），实现了"通过 config space 远程访问 CR-space"的后门：

- 往后门里一个 dword（地址寄存器）写 CR-space 偏移
- 再读/写另一个 dword（数据寄存器），就完成对应 CR-space 地址的读/写

**两条路通向同一个目的地（CR-space）**，差别在传输：

| 路径 | 走的 PCIe 包类型 | 速度 | 适用场景 |
|---|---|---|---|
| BAR0 mmap | Memory TLP | ns 级 | mlx5_core 驱动数据面 |
| Configuration space 后门 | Configuration TLP | μs 级 | bring-up / 无驱动 / 半死状态下的诊断 |

---

## 第二层：mst 的两种设备节点对应这两条路

`mst start` 之后你会看到两个节点，**它们不是一个东西**：

```
/dev/mst/mt4131_pci_cr0     ← BAR0 mmap，走 Memory TLP，快
/dev/mst/mt4131_pciconf0    ← config space 后门，走 Configuration TLP，慢但稳
```

你一直在用的是 `pciconf0`——这是 mlxconfig/flint 的**默认选择**，因为它不依赖 mlx5_core 驱动是否健康，连 firmware 半挂的卡都能救。

`mst` 内核模块本身**只干一件事**：把"对 CR-space 偏移 X 的读/写"暴露成 ioctl。它内部对两种节点的实现差异：

```c
// pci_cr0 路径
void __iomem *bar0 = pci_ioremap_bar(pdev, 0);
writel(value, bar0 + cr_offset);

// pciconf0 路径
pci_write_config_dword(pdev, vsec_addr_off, cr_offset);
pci_write_config_dword(pdev, vsec_data_off, value);
```

mst **完全不懂** firmware 协议、不懂 NVCONFIG、不懂 TLV——它只是一个授权代理（root 才能 open），把 CR-space 的原始读/写权限交给用户态。

---

## 第三层：CR-space 里有什么——Command Interface

CR-space 是一段固定布局的寄存器空间，开头几 KB 是 **Initialization Segment**，里面有几个关键字段：

```
Init Segment（CR-space offset 0 起）
├── fw_rev / cmd_interface_rev / 设备能力位
├── cmdq_phy_addr_h / cmdq_phy_addr_l  ← Command Queue 物理基地址
├── command_doorbell_vector            ← 哪些 entry 有新命令
└── ...
```

注意：**Command Queue 的位置不是硬编码 offset**，要从 Init Segment 里读出来。Init Segment 自己的地址才是固定的（CR-space 起始）。

Command Queue 是一个由 host 在 DMA 内存里分配的环形数组（典型 32 项），每一项是一个 64 字节的 **Command Queue Entry (CQE)**：

```c
struct cmdq_entry {
    u32  input_length;
    u64  input_mailbox_ptr;     // 输入参数所在的 DMA 内存地址
    u32  command_input[4];      // 短命令直接 inline
    u32  command_output[4];     // 短输出 inline
    u64  output_mailbox_ptr;
    u32  output_length;
    u8   token;
    u8   signature;
    u8   status;                // firmware 写：0 = 成功
    u8   ownership;             // 0 = HW 处理中，1 = SW 可读
};
```

OpCode 写在 `command_input[0]` 的高 16 位里。CX 系列里 mlxconfig 用到的就是：

| OpCode | 名称 | 作用 |
|---|---|---|
| `0x805` | **ACCESS_REGISTER** | 读/写一个内部寄存器，包括 NVCONFIG 用的 MNVDA |
| `0x100` | QUERY_HCA_CAP | 查能力（mlxconfig 启动时会调） |

具体 opcode 值要以你这版 firmware 的 PRM 为准——不同代际可能微调。

---

## 第四层：mlxconfig 进程在用户态做的事

```bash
sudo mlxconfig -d /dev/mst/mt4131_pciconf0 set NUM_OF_PF=4
```

按回车后 mlxconfig 内部顺序执行：

**1) 打开 mst 节点**
```c
int fd = open("/dev/mst/mt4131_pciconf0", O_RDWR);
```

**2) 本地查字段表**
mlxconfig 二进制里编译进了一张 NVCONFIG 字段数据库，告诉它：
```
NUM_OF_PF
  ├─ 所在 TLV type: 0x80（NV_HOST_CHAINING_CAP 类一族里的某条）
  ├─ data 区偏移：某个 dword 的 bit X..Y
  └─ 合法范围：8-bit unsigned
```
这一步**纯本地**，不和卡通信。

**3) 通过 ACCESS_REGISTER + MNVDA 读出当前整条 TLV**
mlxconfig 通过 mst 把一个 CQE 写进 Command Queue（实际上是先把 CQE 内容 DMA 给卡，再写 doorbell）：
```c
opcode      = 0x805 (ACCESS_REGISTER)
register_id = MNVDA   // Mellanox NV Data Access register
method      = 0 (READ)
tlv_type    = 0x80
```
然后按 doorbell，轮询 ownership bit 翻回到 1，从 output mailbox 取回当前 TLV 的完整内容。

**4) 在本地修改字段**
把刚读回来的 TLV data 里 NUM_OF_PF 对应那几个 bit 改成 4，其它 bit **原样保留**——这就是为什么必须先读：避免把同一条 TLV 里别的字段抹成 0。

**5) 显示 Apply 提示**
```
Apply new Configuration? (y/n) [n] :
```
**重要更正**：此时**还没写**任何东西到卡上。

**6) 按 y 之后，才发 ACCESS_REGISTER (WRITE)**
```c
opcode      = 0x805
register_id = MNVDA
method      = 1 (WRITE)
tlv_type    = 0x80
data        = 改过的 TLV
```
按 n 直接退出，flash 完全没动——你前面 probe NUM_OF_PF 上限的脚本就是这样，每次都回 `n`，所以那张卡的 NVCONFIG 还是原样。

---

## 第五层：firmware 收到 ACCESS_REGISTER(MNVDA, WRITE) 之后

CX8 内部有若干嵌入式 CPU 核跑 firmware（具体型号 NVIDIA 一般不公开，泛称 "embedded firmware processor" 就行，别套 "IR Processor" 这种非官方名字）。firmware 主循环大致是：

```c
for (;;) {
    if (cmdq_doorbell_rang()) {
        cqe = read_cmdq_entry();
        switch (opcode_of(cqe)) {
            case 0x805: handle_access_register(cqe); break;
            case 0x500: handle_create_qp(cqe); break;
            // ... 几百个其它 opcode
        }
        write_status_and_ownership(cqe);
    }
}
```

`handle_access_register(MNVDA, WRITE)` 的工作（伪代码）：

```
1. 鉴权：调用者必须是 host PF 且具备 admin 权限
       （VF / VM 里发同样的命令会被拒）
2. 验证 TLV 头部 CRC、type 合法性、长度合法性
3. 验证字段值在允许范围内
       （比如 NUM_OF_PF 是 8-bit 字段，传 256 直接拒——
        这就是你之前看到的 "value 256 is not valid, as its size is 8 bits"）
4. 在两块 NV_DATA 分区里找当前 active 的那一块
5. 查找现有同 type TLV：
     - 没有 → 在分区末尾追加一条新 TLV，valid=1
     - 有   → 追加新版（valid=1），把旧版那条的 valid 翻成 0
6. 调用 SPI 控制器把改动持久化到 QSPI Flash
7. 写 status=0、ownership=1，结束
```

第 5 步是 **log-structured 更新**：从不就地覆写，只追加新版 + 让旧版失效。好处是断电安全（任何时刻 flash 上要么是旧版有效、要么是新版有效，不会两边都坏），坏处是 NV_DATA 会逐渐变满，需要 firmware 周期性 compaction。

---

## 第六层：为什么只有 firmware 能写 Flash

CX8 上的 QSPI Flash 控制器**只接受**来自内部 firmware 处理器的 SPI 命令。host CPU 没有任何路径能直接发 SPI 命令——这是 ASIC 层面的硬隔离。

所以 host 想改 flash 上任何东西，唯一路径是：

```
host → PCIe → CR-space Command Queue → firmware → SPI controller → Flash
```

firmware 在每一步都可以拒绝，且整个 firmware 镜像本身在 flash 上是签名保护的，Secure Boot 校验失败就不会加载。这就是为什么"`mlxconfig` 能改配置"和"`mlxconfig` 不能改 firmware 代码"两件事能并存：

- 改配置：firmware 主动开放的、受白名单约束的 NVCONFIG 数据区
- 改 firmware 代码：必须走 `flint burn`，且镜像必须是 NVIDIA 私钥签名过的，否则 firmware 自己拒绝写

---

## 第七层：每一层的安全边界

| 边界 | 保护机制 |
|---|---|
| Linux 用户态 → /dev/mst | 字符设备 mode 0600 + root only |
| /dev/mst → CR-space | mst 模块只允许特定 ioctl 命令 |
| host → firmware | firmware 校验调用者必须是 host PF；VF/VM 无权改 NVCONFIG |
| firmware → flash | firmware 校验 TLV 格式、字段范围、签名（若涉及 firmware 区） |
| 卡上电 | Secure Boot 校验 firmware 镜像签名 |

---

## 关于你前面的 NUM_OF_PF probe

把这套机制套回去就清楚了：

- 你 `set NUM_OF_PF=256` —— mlxconfig 本地字段表查到这是 8-bit 字段，**根本没发 ACCESS_REGISTER**，直接本地报错 "value 256 is not valid, as its size is 8 bits"。
- 你 `set NUM_OF_PF=96/128/192` —— mlxconfig 本地校验通过，**也没发 ACCESS_REGISTER WRITE**，只是展示了"如果你按 y 会变成这样"的预览。你回了 `n`，于是退出，flash 文风不动。

所以这块卡的真实"firmware 能不能接受 NUM_OF_PF=192"还**没有被验证**——本地表只校验了 8-bit 宽度上限 255，至于 firmware 自己内部对这个字段还有没有更严的限制（比如 PCIe physical function 数量受芯片 SR-IOV capability 限制），要真按 y 提交之后看 firmware 返回 status 才知道。

如果你想知道**实际 firmware 接受的上限**，就得真做一次写：选一个值（比如 192），按 y，看 firmware 是接受还是返回错误。这是不可逆的修改（会改 flash），建议先 `mlxconfig backup` 把当前 NVCONFIG 存到文件，万一接受了不喜欢可以 `mlxconfig -f <file> restore` 回滚。
