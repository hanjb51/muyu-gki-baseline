# DroidSpaces 6.1.138 参考内核逆向分析与 muyu 评估

审计对象：用户指定 ZIP，以及 Xiaomi Pad 7 Pro / muyu 的既有 OS3.0.307 原厂取证和 Google GKI 基线。审计日期：2026-11-16（北京时间）。

**结论：可以借鉴其必要功能配置和 SYSVIPC 使用 kABI 保留空间的设计，但不能将该 ZIP、完整配置或整套工作流直接移植到 muyu。** 它保留了 muyu 已知的四个 CRC 冲突，也没有恢复原厂模块签名信任，更没有补齐两项 OEM MM 功能。Phase 5 的原厂兼容性阻塞没有解除，本轮不建议进入完整功能内核编译或刷写。

本报告的“已证实”限于静态提取、密码学测试或固定源码直接支持的事实；“间接证据/推测”不等于设备实测；“尚未验证”明确保留缺口。

## 1. 输入、哈希与成功案例可信度

【已证实】文件在用户给出的精确路径存在，未猜测其他位置：

```text
C:\Users\15121\Downloads\AnyKernel3_Resukisu_gki_6.1.138_coolapk@爱你么么哒qcjl哟.zip
```

| 对象 | 大小 | SHA256 |
|---|---:|---|
| ZIP | 18,039,097 字节 | `73a034d6c57f6faea694c045ef9576f0fd1b73e1bd53676f9e7d573dcd11dbcd` |
| ZIP 内 `Image` | 36,878,848 字节 | `9943c5a1a7cba7e9e6a8243831e986f4003856902371a5d94c146d19601f563c` |
| 提取的 `.config` | 206,734 字节，7,611 行 | `f4f39b362b7fa47e99a02db1b4df1d69be0bb58ad2987bdbcc8ed798bbe1aabb` |

命令/方法：Python `zipfile.ZipFile`、`hashlib.sha256` 逐项读取；找到 `IKCFG_ST` / `IKCFG_ED` 后用标准库 `gzip.decompress` 提取配置。清单及每个文件哈希见 [zip-inventory.json](evidence/droidspaces-reference/zip-inventory.json)。没有执行包中任何脚本或二进制工具。

【已证实】本地 ZIP 的 Git blob SHA1 为 `5fa9eedce93abb0435d36c81ffc8e5c4882f9e4f`，与 `Goldzxcbug/Droidspaces-kernel` 固定提交 `3a7177a67b563833c03a2035edf10077a50caf24` 的同名文件 Git blob 及大小一致；这是同一发布文件的强身份对应，不是仅凭文件名关联。见 [provenance.json](evidence/droidspaces-reference/provenance.json)。

【间接证据】Droidspaces 官方社区设备表，固定提交 `cdadb9eb5d0f86aacffff60776333e6f6b73a30a` 的 `Documentation/community-supported-devices.md:187`，确实列出 Xiaomi 14 中国版、HyperOS 3 / Android 16、6.1.138、ReSukiSU，并链接本 ZIP。它是社区上报记录，没有 accompanying 的完整 boot/module 日志、systemd 版本/单元测试、模块集合与稳定性测试记录。不能把该表格理解为本轮独立复现，更不能把普通 Pad 7 的上报当作 Pad 7 Pro / muyu 验收。

本阶段仍以用户指定的 **OS3 6.1.138** 为目标；此前读取的 OS4 OTA 6.1.157 是另一个版本，不混用其配置、模块或验收结果。

## 2. 镜像与源码身份

【已证实】`Image` 是可直接扫描的 ARM64 原始镜像，头部 ARM64 magic 为 `41524d64`，不是 Image.gz。内嵌 banner：

```text
6.1.138-android14-11-g23d7c6efa1683-ab10030316-4k
Android clang 17.0.2, r487747c; LLD 17.0.2
#1 SMP PREEMPT Sun Dec 01 08:10:00 UTC 2024
```

【已证实】banner 的短 SHA 可解析到公开 common 提交 **`23d7c6efa1683634931690f4df06f025bdcc20d1`**。该提交 `Makefile` 确实为 6.1.138；它在现有候选 `0c3d559bcd85c64dae9c9c9687abbe5347fff3ad` 之上 **ahead 9、behind 0**，共同祖先就是候选提交，涉及 11 个文件。九个提交的完整 SHA、消息与差分保存在 [common-source-comparison.json](evidence/droidspaces-reference/common-source-comparison.json)。改动涉及 MTE/KVM、HID、FUSE、page-size migration 和 UNIX socket，不能把这九项自动归为 Droidspaces 补丁。

【尚未验证】这是 banner 指向的公开源码线索，不是镜像的完整 source-lock：没有准确生成本 ZIP 的 CI run、补丁快照、环境/manifest、vmlinux 或构建证明来固定“该提交 + 所有未提交补丁”的关系。不能据此声称已拿到发布二进制的全部源代码差分。

【已证实】参考编译仓库当前工作流允许改 localversion，并用 `KBUILD_BUILD_TIMESTAMP` 和 mkcompile_h 改写时间；Android14/6.1 工作流默认时间与该镜像的 2024 字符串完全相同。公开短 SHA 对应的提交日期却是 2026 年，因此 banner 时间不能当作真实构建日期。配置还有 `CONFIG_KSU_SUSFS_SPOOF_UNAME=y`，也不能仅依赖运行时 uname 认证来源。相关位置：固定 `95a5710108ff16941ddecc50264737b13b0e5d07` 的 `.github/workflows/build.yml:1462–1535`、`kernel-a14-6-1.yml`。

【已证实】配置/静态字符串可确认以下附加内容：

- `CONFIG_KSU=y`、`CONFIG_KPM=y`、`CONFIG_KSU_SUSFS=y`，启用若干 SUSFS 路径、挂载和 uname 隐藏功能。
- 镜像中存在 `v4.1.0-82d85024@ReSukiSU` 和 SUSFS `v2.1.0` 初始化字符串。它们支持 ReSukiSU/SUSFS 家族识别，不能替代完整源码/构建身份。
- 包内 `anykernel.sh` 使用 Wild Kernels 模板文案和链接，不能据此断言 WildKernels 是此包的精确构建来源。

证据：[reference-image.json](evidence/droidspaces-reference/reference-image.json)、[binary-markers.json](evidence/droidspaces-reference/binary-markers.json)、[banner-source-lead.json](evidence/droidspaces-reference/banner-source-lead.json)。

## 3. AnyKernel3 静态行为

【已证实】ZIP 包含 `Image`、AnyKernel3 shell 安装器与工具（magiskboot、busybox、magiskpolicy、fec、httools、lptools、snapshotupdater）。没有独立 `.ko`、Module.symvers、vmlinux、DTB、DTBO、init_boot/vendor_boot 镜像或设备专用 ramdisk。对 Image 扫描并验证 FDT 头边界，没有检出独立可解析的 FDT 候选；这不是穷尽所有嵌入数据的证明。镜像头的运行时 image_size 不宜直接当作磁盘文件长度，不能据两者不同就断言文件损坏。

| 检查项 | 实际逻辑及路径 |
|---|---|
| 设备名 | `anykernel.sh:7` 为 `do.devicecheck=0`，device.name1–5 为空 |
| boot 版本 | `do.check_boot_version=0`；`ak3-core.sh:1011–1015` 直接跳过检查 |
| 所谓 GKI 检查 | `anykernel.sh` 读取正在运行的 `/proc/version`，只匹配 `5.1* / 6.1* / 6.6*`；不校验目标硬件、KMI SHA 或模块 CRC |
| 目标分区 | `block=boot`；`setup_ak()` 解析 slot 后定位 boot 分区。常规为当前槽；postinstall 环境可选择非当前槽，不是固定 `_a` |
| 读取/重打包 | `split_boot()` 读旧 boot；用 ZIP Image 替换 kernel，经 magiskboot 保留/重打包原组件；有 ramdisk 时调用 unpack/write_boot |
| 实际写入 | `flash_boot()` 的 `blockdev --setrw` 及后续 `cat boot-new.img /dev/zero > $BLOCK` 或 dd/nandwrite 分支（`ak3-core.sh:441–449`） |
| 其他镜像 | `write_boot()` 包含 vendor_boot/vendor_kernel_boot/vendor_dlkm/system_dlkm/dtbo 的通用调用，但 `flash_generic` 先检查同名输入文件；本包没有这些输入，不能因为函数存在就宣称这些分区必定被写 |
| init_boot 自动分流 | 依赖包中 dtb/vendor_ramdisk/vendor_patch 等输入；本包不具备触发材料 |
| 模块安装 | `do.modules=0`、`do.systemless=0`，且没有模块文件 |
| Magisk/AVB | `no_magisk_check=1` 跳过常规 Magisk 探测；`patch_vbmeta_flag=auto` 的常规默认是 false，但会受已有导出环境/条件分支影响。不能保证“永不改变 AVB”，也没有证据表明本包常规路径单独刷写顶层 vbmeta |

完整原始脚本作为证据保存在 [installer/](evidence/droidspaces-reference/installer/)，行号来自 ZIP 实际文件；所有分支均只读分析。**本轮没有调用 shell 安装器、包中工具或任何设备命令。**

## 4. 三方配置与功能支持矩阵

原厂列来自既有 `muyu-gki-phase3/evidence/stock-full-config.txt`；候选列来自已完成构建的 `out/analysis/final.config`，不是 defconfig 推测。两份输入哈希在 [config-comparison.json](evidence/droidspaces-reference/config-comparison.json) 固定。

`缺项` 表示最终配置文本没有该行，不能当作 y；对 IPC_NS、DEVTMPFS_MOUNT，父依赖关闭又能解释其功能不可用。完整矩阵见 [feature-config-matrix.json](evidence/droidspaces-reference/feature-config-matrix.json)。

| 配置 | muyu 原厂 | 当前候选 | 参考 ZIP |
|---|---|---|---|
| CONFIG_SYSVIPC | n | n | y |
| CONFIG_POSIX_MQUEUE | n | n | y |
| CONFIG_IPC_NS | 缺项 | 缺项 | y |
| CONFIG_PID_NS | n | n | y |
| CONFIG_USER_NS | n | n | y |
| CONFIG_UTS_NS | y | y | y |
| CONFIG_NET_NS | y | y | y |
| CONFIG_CGROUPS | y | y | y |
| CONFIG_CGROUP_PIDS | n | n | n |
| CONFIG_CGROUP_FREEZER | y | y | y |
| CONFIG_CGROUP_BPF | y | y | y |
| CONFIG_DEVTMPFS | n | n | y |
| CONFIG_DEVTMPFS_MOUNT | 缺项 | 缺项 | y |
| CONFIG_SECCOMP | y | y | y |
| CONFIG_NAMESPACES | y | y | y |
| CONFIG_MODVERSIONS | y | y | y |
| CONFIG_MODULE_SIG | y | y | y |
| CONFIG_MODULE_SIG_FORCE | n | n | n |
| CONFIG_MODULE_SIG_PROTECT | y | y | y |

【已证实】参考配置相对候选共有 33 个文本条目差异：主要是 IPC/namespace/devtmpfs、tmpfs ACL/xattr、KSU/KPM/SUSFS 及随依赖生成的项。不是 33 项都与 Droidspaces 必需条件有关。`CONFIG_CFS_BANDWIDTH=n`、`CONFIG_FHANDLE=n` 在三者中相同；仅打开 namespace 仍不能保证当前任意 systemd 版本/服务或 Docker 的全部行为。

### 4.1 配置依赖与 systemd 原因分析

【已证实／源码】候选 `init/Kconfig:377–423,1211–1268`：SYSVIPC、POSIX_MQUEUE、PID_NS 等为 bool 功能，POSIX_MQUEUE 依赖 NET；IPC_NS 依赖 `(SYSVIPC || POSIX_MQUEUE)` 并位于 namespaces 条件下。原厂两种 IPC 均为 n，因此 IPC_NS 的缺项不是“其实已开启”。`NAMESPACES=y` 只表示总开关，不能覆盖 `PID_NS=n`。

【已证实／Droidspaces 源码】固定上游提交的 `src/monitor/monitor.c:70–74` 调用 `unshare(CLONE_NEWUTS | CLONE_NEWIPC)`，`:182–195` 创建新 PID namespace 后 fork 容器 init；`src/boot/init.c:131` 独立 mount namespace，随后处理根目录、/proc、/sys、cgroup、/dev 等。这说明参考配置为何具备启动该路径的基础，而原厂会在缺失 namespace 功能处遇到硬阻塞；不是 chroot 本身制造这些内核能力。

| 层次 | 参考内核已具备的静态基础 | 仍需的证据/条件 |
|---|---|---|
| Droidspaces 基础容器 | PID/IPC/UTS/mount namespace 的配置基础、SYSVIPC、POSIX_MQUEUE、seccomp、devtmpfs | 实际 unshare/mount 权限、Root/SELinux、用户空间版本、正确挂载与启动日志；host 网络可减少额外网络依赖 |
| systemd 作为容器 PID 1 | 新 PID namespace，cgroup 基础、proc/sysfs/epoll/signalfd/timerfd 等；USER_NS 可用于部分隔离特性 | systemd 的准确版本及功能、cgroup v1/v2 实际布局与可写委托、私有 /run 与 devpts、capabilities、服务 sandbox；不能将 SYSVIPC 视为所有 systemd 启动的单一总开关 |
| Docker 嵌套 | USER_NS、NET_NS、VETH、BRIDGE、OVERLAY_FS 等配置线索 | 存储/网络驱动、netfilter、设备/cgroup 委托、运行权限和 daemon 实测；PIDS/CFS 带宽控制未启用，相关限制缺失，不承诺完整支持 |

【间接证据】固定 systemd 源码 `7386493f3b3658e5cac075a4df7280e6ff4371d7` 的 README 列出 cgroup、devtmpfs、FHANDLE 等要求；Container Interface 说明 PID 1、/proc、/sys、/dev 以及 cgroup 的容器契约。该最新源码不能替代上报案例实际 systemd 版本。参考配置的 FHANDLE=n 与当前 README 的要求之间存在缺口，不能宣传为所有新版 systemd 特性完备。`DEVTMPFS_MOUNT=y` 也不会自动解决容器里的私有 /dev；容器管理器仍需自行布置挂载和设备节点。

## 5. kABI padding：真正可借鉴的部分

【已证实】参考 BTF 共解析 130,395 个类型。原厂与参考 `task_struct` 均为 **4,800 字节**；已比较的具名非 reserve 直接成员，其偏移/直接类型标签没有差异。参考匿名 union 显示：

| 参考字段 | 字节偏移 | 占用空间 | 对应原厂 reserve |
|---|---:|---:|---|
| sysvsem | 3640 | 8 | 6 |
| sysvshm | 3648 | 16 | 7、8 |
| thread | 3664 | 后续成员起点未移动 | 不占用 |

证据：[task-padding-comparison.json](evidence/droidspaces-reference/task-padding-comparison.json)。这是参考二进制实际使用 **6_7_8** 布局的强证据，与 Goldzxcbug 的 GKI/6.1 补丁及 Droidspaces 对应补丁内容一致；仍不足以从二进制确定究竟从哪个仓库复制过补丁。

【已证实／机制】候选 `include/linux/android_kabi.h:56–71,107–113` 在 `__GENKSYMS__` 下保留旧 reserve 表示，真实编译时以 union 放入新字段并约束大小/对齐。这解释了“运行时有 SYSVIPC 字段、共同导出 CRC 仍可保持不变”。它不是关闭 MODVERSIONS，但 CRC 不变也不会证明 vendor 没有私用同一 reserve 或内联语义全部相同。需核对准确 OEM 补丁和实际模块依赖。

### 5.1 用户所列几种“组合”的真实含义

这些数字表示 **task_struct 保留槽位编号**，不是把第 1/2/3 张补丁一起打，也不是可以累计开启的功能组合。

| 名称 | 固定源码调查结果 | muyu 评估 |
|---|---|---|
| 1_2_3 | sem 使用 1，shm 使用 2+3 | 现有候选 `sched.h:1550` 已将 reserve 1 用于 saved_state；参考/原厂 BTF 同样显示该匿名 union。不能再占用 1；此版不是当前基线的可直接使用补丁 |
| 3_4_5 | sem 使用 3，shm 使用 4+5 | 源码存在，但未做准确 OEM 私有用途/并发语义验证；不能以另一设备启动成功选择它 |
| 5_6_7 | 教程文字提到；本次固定目录、当前工作流选项、精确名称搜索和对应路径历史查询未恢复实际补丁 | **尚未验证**，不编造代码或视其与 6_7_8 等价 |
| 6_7_8 | 当前官方/Goldzxcbug 6.1 目录实际提供，参考 BTF 对应 | 最值得继续审计的候选布局；尚未在 muyu 验收，也不能解除已有 CRC/OEM 实现阻塞 |

固定 Droidspaces 提交提供 1_2_3、3_4_5、6_7_8；zzh 工作流提供 off/123/345/678。检索范围和源码位置见 [sources.json](evidence/droidspaces-reference/sources.json)、[provenance.json](evidence/droidspaces-reference/provenance.json)。缺少 5_6_7 的结论限于该范围，不是宣称互联网不存在任何同名版本。

## 6. ABI/KMI 与模块签名：没有解决 muyu 阻塞

### 6.1 原始导出表的部分比对

【已证实／静态提取】沿用 Phase 4 在候选 ELF/Module.symvers 上校验过的 PREL32 表解析器，从参考 Image 恢复 **8,145** 个导出。用 `__page_file_index`、`page_swap_info`、`unuse_swap_pte` 三个锚点得到相同边界与列表，见 [raw-table-validation.json](evidence/droidspaces-reference/raw-table-validation.json)。

| 对照 | 共同导出 | 相同 CRC | 差异 |
|---|---:|---:|---|
| 参考 vs 现有 Google 候选 | 8142 | 8142 | 无共同项 CRC 差异；新增 from_kuid、from_kuid_munged、make_kuid |
| 参考 vs muyu 原厂 | 8142 | 8138 | 仍是原先四项冲突 |

| 符号 | muyu 原厂 CRC | 参考 CRC＝现有候选 CRC |
|---|---|---|
| __page_file_index | `12d686c5` | `39ba4984` |
| add_swap_extent | `3da4a325` | `2a731aba` |
| page_swap_info | `138a96b6` | `b7074429` |
| unuse_swap_pte | `2dd1c10f` | `440b776b` |

【已证实】将既有 790 份原厂模块变体的 __versions 再与参考 vmlinux 导出 CRC 交叉比较，发现冲突的仍只有 **cifs** 变体，涉及前两个符号。cifs SHA256 `694d665f4a19208600b132c7a5ecdc9fc1305ce330d79abbea81513fbfdd5116`。参考镜像没有自然修复此问题。

【尚未验证】ZIP 不含 Module.symvers、STG/ABI 报告或 vmlinux，故这里只是 **原始表的部分静态比较，绝非已完成 ABI/KMI 兼容性验收**。其他模块提供的符号不在 vmlinux 表中是正常情况，不能直接报成缺符号。相同 CRC 不证明结构实际语义、inline、调用约定、模块签名与硬件行为完全兼容。完整表与差异见 [reference-exports.tsv](evidence/droidspaces-reference/reference-exports.tsv)、[reference-crc-comparison.json](evidence/droidspaces-reference/reference-crc-comparison.json)。

### 6.2 签名和保护导出

【已证实】参考内嵌证书 DER SHA256：
`314c658476e4e76c0f4854f8720bf5f9ebc2f13f2a5721f5295017c6e3d94e70`。
SPKI SHA256：`ee986d77a2042cdb36f846ba902fc9980d78abc0cf560519cd7cd66dcf1a1ff2`。

其公钥与原厂/候选均不同；对 Phase 4 已保存的 **120 份原厂 system_dlkm 模块变体**，使用该参考公钥的 CMS 密码学验证结果 **0/120**。其中包含小米签名及历史 Google 签名两组，不能称为 120 个不同模块名称。证据：[reference-key-stock-module-tests.json](evidence/droidspaces-reference/reference-key-stock-module-tests.json)。原厂 60 份小米变体需要已恢复的 OEM 公钥，Phase 5 的最小额外信任根方案仍可作为未来设计输入；本包没有提供它。

配置 `MODULE_SIG=y / PROTECT=y / FORCE=n` 不能证明二进制中的签名路径从未修改。在保留已审计上游验证逻辑的前提下，不受信任的原厂 GKI 模块不能得到 sig_ok，实际保护导出/导入会构成加载门槛。**尚未反汇编证明参考内核的整个验签与 check_version 路径完全未改，也没有运行加载测试**；仅因 MODVERSIONS=y 不能排除人为 bypass。镜像含普通 CRC 警告字符串、未检出旧 OKI 补丁的 `But ignore` 文案，只是辅助线索，不是排除绕过的证明。

因此无法用“houji 上能启动”证明 muyu 的签名链有效；两设备可能使用不同模块、加载顺序、根信任和功能覆盖。没有 houji 完整日志时，不将这些可能性写成根因解释。

### 6.3 OEM 专有实现仍缺失

【已证实】参考配置与候选一样，没有 `CONFIG_ARM64_CONTPTE` 和 `CONFIG_XIAOMI_DMABUF_HUGETLB`；原厂两者均为 y。参考 BTF 没有 Phase 4/5 找到的 contpte/dmabuf_huge 函数名。因此该发布案例没有提供对应 OEM 功能的可移植实现，也没有解释四项 CRC 的 GENKSYMS 原因。不能绕过 Phase 5 把“共同 CRC 8142 项一致”写成 OEM 兼容性已收敛。

## 7. 补丁和构建流程来源评估

固定调查提交：

| 项目 | 提交 |
|---|---|
| Goldzxcbug/Droidspaces-kernel | `3a7177a67b563833c03a2035edf10077a50caf24` |
| Goldzxcbug/Droidspaces_Kernel_patch | `dc0f76bedd790b7738e5695509297ee71ca4a2c2` |
| zzh20188/GKI_KernelSU_SUSFS | `95a5710108ff16941ddecc50264737b13b0e5d07` |
| ravindu644/Droidspaces-OSS | `cdadb9eb5d0f86aacffff60776333e6f6b73a30a` |

【已证实／源码】Goldzxcbug 的 GKI/6.1 `GKI-6.1-sysvipc_kabi_6_7_8.patch` 与 Droidspaces 6_7_8 文件 blob 同为 `5fb2a9ee7c2ea7de781e023737d9acfecb639098`。它只移动 SYSVIPC 任务字段，不负责自动启用全部 namespace，也不修复 OEM cifs。

zzh 的 `build.yml:877–881,912–1016` 从浮动 Droidspaces main 克隆补丁，按用户编号选择 SYSVIPC kABI 补丁，开启 SYSVIPC/POSIX_MQUEUE/IPC_NS/PID_NS/DEVTMPFS/USER_NS；可选网络项独立处理。补丁失败仅输出 warning 并继续（`:934–944`），不符合本项目应有的失败即停止要求。其当前 workflow 不能倒推发布 ZIP 当年的准确 inputs。

【已证实／不能照搬】同一工作流还存在去掉 check_defconfig（`:1429`）、删除 `KMI_SYMBOL_LIST_STRICT_MODE` 和关闭 system_dlkm 构建（`:1572–1574`）等策略；可选 zram 路径甚至包含 `CONFIG_MODULE_SIG=n`（`:1193`）。这些不能迁移到本项目，也不能因当前 ZIP 的签名开关仍为 y 就认定整个流程适合 OEM 验收。

Goldzxcbug 的 `OKI/6.1/01.6.1+_disable_crc_checks_for_lkms.patch` 明确把 `bad_version` 的失败返回改成成功。**它属于禁止采用的兼容性绕过，不是本项目解决方案。** 不能因为它与可用的 GKI SYSVIPC 补丁在同一仓库就整套应用，也没有证据证明本 ZIP 使用了这个 OKI 补丁。

POSIX_MQUEUE 的旧 user_struct padding 补丁也必须按实际版本审查：现有 Google 6.1 的 `include/linux/sched/user.h` 根本没有该旧 `mq_bytes` 原始成员，不能无条件套用旧 OKI/5.15+ 示例；Droidspaces 当前 GKI 指南只要求 5.10 及更早额外应用该 POSIX 补丁。本轮参考二进制与候选共同 CRC 未改变，为该具体构建提供线索，但不是对任意 POSIX 补丁安全性的保证。

| 内容 | 与目标关系 | 最小方案取舍 |
|---|---|---|
| PID/IPC/SYSVIPC/POSIX_MQUEUE | Droidspaces 主要缺口 | 必须针对准确基线和 ABI 审计 |
| SYSVIPC padding | 避免直接插入 task_struct 移动后续成员 | 6_7_8 可作为有实物 BTF 支持的候选方法 |
| DEVTMPFS | Droidspaces 设备访问路径 | 依照需要纳入；MOUNT 选项不代替容器挂载 |
| USER_NS | 部分 sandbox/rootless/Docker 路径 | 不是每个 rootful systemd 启动的绝对前提；按选定用户空间需求和安全补丁审查 |
| tmpfs xattr/ACL | 某些发行版和服务能力 | 有明确需求再单独纳入 |
| ReSukiSU / KernelSU | 提供 Root 的一种方式 | 不等于 namespace 实现；已有 Root 不必为 systemd 再集成该 fork |
| SUSFS、KPM、隐藏/伪装 | 非 systemd 或基本容器必要功能 | 从最小迁移方案排除 |
| NTsync | Wine/Windows 同步对象用途 | 非 systemd/PID namespace 基础需求，排除 |
| UFW、Fail2ban、zram、BBG、Re-Kernel | 不同附加需求 | 不与最小容器支持捆绑 |
| 关闭 CRC/签名/KMI 检查 | 制造假阳性 | 禁止采用 |

## 8. 三条迁移路线

| 路线 | 已证实基础与缺口 | 可行性结论 |
|---|---|---|
| A：原厂内核 + systemd | 有 mount/UTS/NET namespace 和 cgroup 基础，但 PID_NS=n、两类 IPC=n、IPC_NS 不可用、DEVTMPFS=n | **无法通过 Root + mount namespace + chroot 实现本任务要求的独立 systemd PID 1 容器。** Root 不会补回编译掉的 bool 功能；普通 chroot Linux 命令或用户服务管理不等于完整 Droidspaces/systemd 容器 |
| B：现有基线 + 最小补丁 | 有固定可复现基线；新证据支持 SYSVIPC 6_7_8 可在参考构建中保持共同 CRC | 最适合形成最小设计，但 **当前仍被 OEM CRC、签名集成及两项 MM 实现阻塞**；不能先用功能编译掩盖 pristine 未通过 |
| C：参考内核移植 | 有可提取的配置、实际 BTF padding 布局、上游 common +9 提交的来源线索 | 复用研究方法和经过筛选的源码方案，不复用二进制/整套配置/宽松工作流。没有达到 muyu 可直接启动/稳定运行的证据门槛 |

### 8.1 不重新完整编译内核的可能方案

【已证实／结论】对于 **当前原厂共享宿主内核的原生 Droidspaces + systemd PID 1 路径**，没有已验证的免换内核方案。PID_NS 等不是加载一个普通模块就能补上的选项；Root、chroot、bind mount、用户态 systemctl shim 或伪造 /proc 不会创造缺失的内核 namespace。`systemd --user` 即使在某种环境可运行，也不是容器 PID 1，不能当作目标达成。

【推测／不同架构的备选】可研究使用已有、功能齐全的 guest kernel 在用户态全系统虚拟机中启动 systemd，宿主不换内核，也不必自行编译完整 guest kernel；但这已经是 VM 而非共享宿主内核的 Droidspaces 路线。CPU 仿真、存储/图形/音频、功耗与性能均需另行评估。原厂 `CONFIG_KVM=y` 不证明 /dev/kvm 对应用开放或硬件虚拟化可用，不能承诺 KVM 加速。本轮未启动 VM，也未取得适用于 muyu 的其他已验收预编译内核。

## 9. 最小建议与下一步证据门槛

【建议】保留 baseline 原状，先完成 Phase 5 解除阻塞所需材料；只把以下内容带入待审核设计：

1. 把参考配置视为需求清单：核心 SYSVIPC/POSIX_MQUEUE/PID_NS/IPC_NS/DEVTMPFS；保留现有 UTS/NET/SECCOMP/CGROUPS。USER_NS、tmpfs 扩展和网络增强按具体用户空间需求逐项决定，不复制 33 个配置差异。
2. 针对准确 muyu/Google 结构审查 6_7_8 reserve 用法。先用离线布局/类型表示实验确认字段偏移、大小/对齐、没有 reserve 重复使用，审计所有条件编译和关键 anonymous union；不按“刷到哪个不重启”为依据选择槽位。本轮不应用功能补丁。
3. 继续自然复现四项 OEM CRC，不硬编码或忽略；将 Phase 5 固定 OEM 公钥方案与实际 Linux 证书/keyring 集成验收分开记录；获取完整 contpte/dmabuf hugepage 当前 OEM 实现。参考案例不提供这三项答案。
4. 请求/查找参考包准确 CI run、common/Root/SUSFS/补丁提交、全部 inputs、Module.symvers、vmlinux 与最终配置，以及 houji 的加载模块列表、模块签名、droidspaces check、systemd 版本/日志和长期测试记录。不能仅凭社区表格推断稳定性或 CRC/签名保护未被绕过。
5. 获批后按独立阶段推进：先 pristine 原厂静态验收，再最小容器变更的 ABI/配置验收，最后另行授权设备实验。编译结束、上游 ABI/STG、OEM 模块验收、systemd 服务验收和长期硬件稳定性分别给出结果，不能合并成一个“通过”。

CPU/进程限额并非第一阶段目标：参考仍将 CGROUP_PIDS、CFS_BANDWIDTH 保持关闭。不要为开启所有 Docker 选项而扩大结构变更面。

## 10. 可安全迁移的成果究竟是什么

**已取得、可复用的是：** 同一发布 ZIP 的身份与可提取配置；Droidspaces 核心缺项的准确清单；参考二进制确实使用 SYSVIPC 6_7_8 padding、保持 task_struct 大小与已比较具名字段偏移、共同 8,142 项 CRC 不变的静态证据；以及 common 基线之上九项公开提交的可追溯差分。

**尚未取得、不能承诺的是：** 6_7_8 在准确 muyu OEM 语义上的安全验收、原厂四 CRC 收敛、原厂模块信任链、两项 OEM MM 实现、设备启动及 systemd/硬件稳定性。参考包不能直接使用，功能方案也尚未成为经验证的 muyu 补丁集。

因此，本轮结论是 **“有价值的最小方案参考，未达到二进制移植或新功能构建准入”**。Phase 5 的 BLOCKED 状态继续保留。

## 11. 复核材料与执行边界

新增证据位于 `evidence/droidspaces-reference/`；`SHA256SUMS` 固定报告、脚本和证据。`scripts/inspect_droidspaces_reference.py` 为分析入口：在原有离线快照中设置 `MUYU_PROJECT_ROOT`，传入用户 ZIP 绝对路径，安全解压后读取 Image；它导入 Phase 4 已审计解析函数，依赖 Python cryptography。不会执行 ZIP 内工具；大型 ZIP、Image、boot 和原厂模块不重新发布到仓库。

复核命令示例（仅静态分析）：

```powershell
$env:MUYU_PROJECT_ROOT = '原有离线快照根目录'
python scripts/inspect_droidspaces_reference.py '用户提供的 ZIP 绝对路径'
```

除已说明的原始表与密码学验证外，没有运行新内核、完整编译、动态内核补丁或设备读写。没有执行 fastboot、ADB、刷机脚本、重启或槽位切换；没有覆盖此前报告和证据；没有修改 baseline 或降低 ABI/KMI/签名检查。报告提交到独立分支后停止，等待审核。
