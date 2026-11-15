# OFFICIAL_MUYU_SOURCE_AUDIT

审计日期：2026-11-15（北京时间）。项目：hanjb51/muyu-gki-baseline。阶段：源码分析、离线比对和方案设计。

**结论〔推测／方案建议〕：采用两者结合的架构。保留 Google GKI 6.1.138 作为现有实验和对照基线，以小米官方 muyu 源码作为厂商适配、模块及补丁参考；优先取得当前 OEM 的准确 common/GKI 提交与 manifest，再决定实际产品内核基线。现有候选尚不合格，不能因“结合”而跳过兼容性门槛，也不建议直接改用官方 6.1.68 树。**

本报告不批准功能编译、基线替换或刷机。所有事实按“已证实”“推测”“尚未验证”标注；编译成功、上游 ABI 通过、原厂兼容是三件不同的事。

## 1. 审计范围和现有材料

〔已证实〕已读取本地 `muyu-gki-phase1/BUILD_REPORT.md`、`muyu-gki-phase3/BASELINE_REPORT.md`，以及专用 baseline 工作流、继承的旧 build.yaml、构建及验收脚本、source-lock manifest/LOCK、已有 SYSVIPC 补丁和 DroidSpaces fragment。已有取证、790 份模块元数据及 run 43708070680 产物均保留。

〔已证实〕当前远端 `baseline/muyu-gki` 仍为 `f99f842f61b1ae660badbe97d933b3705916b9f7`。本次报告进入同一仓库的 `audit/official-muyu-source-20261115` 文档分支，不修改现有基线及其源码锁。

设备事实来自既有取证及用户给定信息，本轮没有重新连接设备：

| 项目 | 信息 | 状态 |
|---|---|---|
| 设备／代号 | Xiaomi Pad 7 Pro／muyu | 已证实：既有取证 |
| 系统 | OS3.0.307.0.WOYCNXM | 已证实：既有取证 |
| 当前内核 | `6.1.138-android14-11-g7b9e94e37cfa-mi` | 已证实：既有取证 |
| 活动槽 | `_a` | 已证实：既有取证；本轮未实时检查 |
| boot_a／boot_b | /dev/block/sde11、/dev/block/sde39 | 已证实：既有取证 |
| vendor_boot_a／vendor_boot_b | /dev/block/sde21、/dev/block/sde49 | 已证实：既有取证 |
| 模块盘点 | 790 个变体、508 个唯一名称，覆盖 504 个已加载名称 | 已证实：离线材料 |

〔已证实〕GitHub API 报告 Xiaomi_Kernel_OpenSource 整库 size 为 5,704,744 KiB，约 5.44 GiB。此值是仓库整体存储规模指标，不是 muyu 分支的检出或下载体积。本轮没有 clone 整库，使用分支元数据、必要 Git tree 和文件 API，保存 62 项唯一文件快照；62 项均独立重算 Git blob SHA1 与 API 返回值一致，并记录 SHA256。

〔尚未验证〕没有下载完整源码树或重建全部构建环境，不能把必要文件审计称为全仓逐文件审计。一次大 arch 递归 tree 查询发生传输错误，随后改用小目录查询和明确文件路径；没有把该失败当成“文件不存在”的证据。

## 2. 官方分支、提交和版本

### 2.1 固定的官方来源

| 仓库／分支 | 完整提交 | 分支头 committer 时间（北京时间） | 状态 |
|---|---|---|---|
| MiCode/Xiaomi_Kernel_OpenSource / muyu-v-oss | `681e88870888dec258dd48b0ab8c908b303eb159` | 2025-01-09 09:02:55 | 已证实 |
| MiCode/kernel_devicetree / muyu-v-oss | `21b354440459b84995dd7266c95cd17c0abc110c` | 2025-01-03 09:22:01 | 已证实 |
| MiCode/kernel_build / muyu-v-oss | `3b5ab5980990c0406c68d05baecd422ad5e30b8f` | 2025-01-08 09:27:10 | 已证实 |
| Droidspaces-OSS（本轮文档参考） | `cdadb9eb5d0f86aacffff60776333e6f6b73a30a` | 2026-11-07 20:31:27 | 已证实；提交说明 v7.2.0 |

〔已证实〕上述时间是查询时分支头提交的 committer 日期，不能据此反推出 GitHub 分支最后一次 push 的精确时间。分支名称检索本次仅返回 muyu-v-oss；检索范围和时间有限，不构成其他源码从未发布的证明。

〔已证实〕官方默认 README 索引明确列出 muyu／Xiaomi Pad 7 Pro／Android U／Base tag `LA.VENDOR.14.3.0.r1-14500-r1.0.r1_00042.0`。源码提交说明也引用同一 tag。这是设备归属证据，版本结论另由 Makefile 核实。

来源：[官方索引](https://github.com/MiCode/Xiaomi_Kernel_OpenSource/blob/README/README.md)、[内核固定提交](https://github.com/MiCode/Xiaomi_Kernel_OpenSource/commit/681e88870888dec258dd48b0ab8c908b303eb159)、[设备树固定提交](https://github.com/MiCode/kernel_devicetree/commit/21b354440459b84995dd7266c95cd17c0abc110c)、[构建固定提交](https://github.com/MiCode/kernel_build/commit/3b5ab5980990c0406c68d05baecd422ad5e30b8f)。

### 2.2 实际 Linux 版本和源码形态

〔已证实〕固定提交的 Makefile 明确为 VERSION=6、PATCHLEVEL=1、SUBLEVEL=68，即 **Linux 6.1.68**，不是 6.1.138。该结论来自文件内容，不是 README、设备代号或 tag 名称。

〔已证实〕该树有 Linux 核心目录和文件，包括 arch、include、init、kernel、mm、fs、drivers，存在实际实现代码、Kconfig 和 Makefile，属于包含厂商修改的 Linux 内核源树，不只是一个设备补丁包。

〔尚未验证〕“存在 Linux 源树”不等于“具备当前系统完整、可独立复现的构建发布”。尚未取得将 common、msm-kernel、build/kernel、设备树、工具链及所有外部模块绑定到当前系统的完整 manifest。私有或外部驱动依赖的可用性也没有全部核实。

〔已证实〕存在以下构建内容：

| 内容 | 具体证据 | 解释 |
|---|---|---|
| 通用 GKI 配置 | arch/arm64/configs/gki_defconfig | 这是源配置，不是生成的最终 .config |
| muyu 专用配置 | arch/arm64/configs/vendor/muyu_GKI.config | 官方提交说明中提到的文件；实际是设备 fragment |
| muyu 构建定义 | muyu.bzl、build.config.msm.muyu | 配合 pineapple 和小米共同模块定义 |
| Bazel／Kleaf | BUILD.bazel、bazel.WORKSPACE；kernel_build 中有 kleaf 实现 | 存在规则，不代表依赖已齐备 |
| KMI generation | build.config.common 的 KMI_GENERATION=11 | 与当前内核字符串 generation 相同，不能推导完整 ABI 相同 |
| 工具链标识 | build.config.constants 的 CLANG_VERSION=r487747c | 标识可识别，未取得该发布全部工具二进制锁定信息 |
| 设备树 | kernel_devicetree 的 qcom/muyu-sm8635-overlay.dts 及关联 dtsi | model 明确指向 Muyu based on SM8635 |
| 外部设备树连接 | arch/arm64/boot/dts/vendor 是 symlink | 完整构建需要正确的多仓目录布局 |

〔已证实〕muyu_GKI.config 包含指纹、触觉、NFC、手写笔无线、电源和 USB 等设备相关配置；muyu.bzl 包含相应设备模块清单。arch/arm64/Kconfig 还定义了 FACTORY_BUILD，默认 n。官方头提交是相对于 Qualcomm 父提交 `8c4831987d962795dd58ffd50a1953eeed524979` 的小米设备修改提交，不能将整个 6.1.68→6.1.138 差异全算作“小米补丁”。

来源：[Makefile](https://github.com/MiCode/Xiaomi_Kernel_OpenSource/blob/681e88870888dec258dd48b0ab8c908b303eb159/Makefile)、[muyu 配置](https://github.com/MiCode/Xiaomi_Kernel_OpenSource/blob/681e88870888dec258dd48b0ab8c908b303eb159/arch/arm64/configs/vendor/muyu_GKI.config)、[muyu 规则](https://github.com/MiCode/Xiaomi_Kernel_OpenSource/blob/681e88870888dec258dd48b0ab8c908b303eb159/muyu.bzl)、[设备树](https://github.com/MiCode/kernel_devicetree/blob/21b354440459b84995dd7266c95cd17c0abc110c/qcom/muyu-sm8635-overlay.dts)。

### 2.3 官方规则所显示的混合构建架构

〔已证实〕build.config.msm.muyu 继承 `msm-kernel/build.config.msm.pineapple`。build.config.msm.gki 设置 `GKI_BUILD_CONFIG=common/build.config.gki.aarch64`。msm_kernel_la.bzl 的普通变体使用 `base_kernel = "//common:kernel_aarch64"`，consolidate 使用另一套 common 目标。muyu 定义通过这些规则构建设备模块。

〔已证实〕因此，官方规则明确存在 **common/GKI 基础内核＋MSM／厂商模块＋设备树** 的关系。不能因为 msm-kernel 源树带有通用 BUILD.bazel 和 gki_defconfig，就将其当成当前系统实际 common/GKI 发布的唯一源码。

〔尚未验证〕本次没有找到当前 OS3.0.307 对应的完整官方 kernel manifest。检查了内核根目录以及 kernel_build、kernel_devicetree 的可取得 tree；kernel_build tree 没有对应 manifest XML。对 MiCode/kernel_manifest、MiCode/GKI_Kernel_OpenSource 的精确仓库查询均为 404，官方组织的 kernel manifest 仓库搜索也未返回结果。这些是有限范围的“未找到”，不是证明 manifest 不存在；Base tag、WORKSPACE、build.config 或设备树都不能替代 manifest。

〔尚未验证〕官方 Bazel 发布版本与所有 prebuilts 的 commit／SHA256 未形成完整锁。不能因 Clang 名称同为 r487747c，就认定其与当前系统的每个工具二进制完全一致。

来源：[MSM/GKI 配置](https://github.com/MiCode/Xiaomi_Kernel_OpenSource/blob/681e88870888dec258dd48b0ab8c908b303eb159/build.config.msm.gki)、[混合构建规则](https://github.com/MiCode/Xiaomi_Kernel_OpenSource/blob/681e88870888dec258dd48b0ab8c908b303eb159/msm_kernel_la.bzl)、[工具链标识](https://github.com/MiCode/Xiaomi_Kernel_OpenSource/blob/681e88870888dec258dd48b0ab8c908b303eb159/build.config.constants)。

## 3. 与当前原厂内核的对应关系

| 项目 | 当前原厂 | 官方 muyu 树 | 现有 Google 候选 | 状态 |
|---|---|---|---|---|
| Linux 版本 | 6.1.138 | 6.1.68 | 6.1.138 | 已证实 |
| ACK 标识／generation | android14／11 | build.config 为 android14-6.1／11 | android14／11 | 已证实；相同标识不保证完整兼容 |
| 源码提交 | 仅知 7b9e94e37cfa 前缀 | 681e88870888dec258dd48b0ab8c908b303eb159 | 0c3d559bcd85c64dae9c9c9687abbe5347fff3ad | 已证实 |
| 与原厂 exact match | 目标对象 | 未证明 | 未证明 | 尚未验证 |
| 配套用途 | 当前运行内核 | 旧设备／厂商源码参考 | 已采集 Google 配套模块对应的实验候选 | 已证实：已有证据边界 |

〔已证实〕对 MiCode/Xiaomi_Kernel_OpenSource 和 AOSP 官方 GitHub 镜像 aosp-mirror-neo/kernel_common 的 commits/7b9e94e37cfa 查询均返回“无该提交”。对 cifs 模块携带的 c96cc383b8ab 前缀查询同样未找到。

〔尚未验证〕这不能证明提交不存在于私有仓库、其他官方镜像或未发布的树中，也不能据此还原当前 OEM 提交的父链。**当前 OEM 内核的确切上游 GKI 基线仍未定位。** Google 候选 0c3d559… 只与已采集的一套 Google 配套模块有已知对应，不能升级为 7b9e94… 的精确上游。

〔推测〕官方 6.1.68 树与设备中保留的 6.1.68 厂商模块可能属于相关历史软件线，可用于理解模块环境。仅凭版本一致仍不能证明它就是 c96cc… 的源码，不能保证重新构建即可得到同样 CRC。

## 4. 现有 GKI 基线与工作流复评

〔已证实〕run 43708070680 已结束，工作流 failure。实际内核编译和强制上游 ABI/STG 比较成功，失败发生在随后离线验收。产物完整性复核及 790 份模块比较已完成，结论继续有效。

| 已有问题 | 官方 muyu 源码能否直接解决 | 本轮结论 |
|---|---|---|
| cifs 两个 CRC 不匹配 | 未经复现不能确认 | 尚未验证；提供旧源码比较线索 |
| 四项最终配置差异 | 找到 FACTORY_BUILD 的定义与默认 n | 已证实：仅解释其中一项；未证明其余项解决 |
| protected GKI 模块签名信任 | 源码和设备配置不能提供 OEM 私钥或自动建立信任 | 尚未验证；没有解决 |
| 当前完整 OEM ABI／布局 | 同 KMI generation 不足以证明 | 尚未验证 |
| 原厂内核准确源码 | 公开 6.1.68 与运行的 6.1.138 不同 | 已证实：不能直接视为 exact source |

〔已证实〕专用 baseline.yml 固定 ubuntu-22.04、Actions commit，使用 pristine gki_defconfig、ThinLTO、MODVERSIONS、CFI、4 KiB 页和原保护名单；检查最终 Image 解出的 .config，并保留 ABI 非零退出码。SYSVIPC 补丁仅检查，未应用。

〔已证实〕继承的旧 `.github/workflows/build.yaml` 是另一条 workflow_dispatch 流程，其输入默认 `remove_abi_gki_protected_exports=true`、`lto=none`。它不满足本项目的默认保护目标，不能代替专用 baseline 工作流。报告分支的文档提交不匹配 baseline.yml 的 push 分支条件，也没有调用旧工作流。

〔尚未验证〕本地旧源码锁和历史报告中曾有前两次失败的中间状态。本次以远端 f99f842… 和 run 3 封存的 source-lock／source-verification 为当前构建事实来源，不将旧文件覆盖为“已匹配原厂”。

来源：[现有任务](https://github.com/hanjb51/muyu-gki-baseline/actions/runs/43708070680)、[专用工作流](https://github.com/hanjb51/muyu-gki-baseline/blob/f99f842f61b1ae660badbe97d933b3705916b9f7/.github/workflows/baseline.yml)、[继承的旧工作流](https://github.com/hanjb51/muyu-gki-baseline/blob/f99f842f61b1ae660badbe97d933b3705916b9f7/.github/workflows/build.yaml)。

## 5. cifs CRC 调查

### 5.1 已证实的失败

〔已证实〕失败变体为 `lib/modules/cifs.ko`，SHA256 `694d665f4a19208600b132c7a5ecdc9fc1305ce330d79abbea81513fbfdd5116`。模块元数据携带 `6.1.68-android14-11-gc96cc383b8ab`，名称 cifs 出现在已加载清单。按名称覆盖不等于已通过运行时 Build ID 证明具体文件来源；本次按要求保留并检查全部变体。

| 符号 | 原厂模块要求 CRC | 候选 vmlinux CRC | 状态 |
|---|---|---|---|
| __page_file_index | 0x12d686c5 | 0x39ba4984 | 已证实：不匹配 |
| add_swap_extent | 0x3da4a325 | 0x2a731aba | 已证实：不匹配 |

〔已证实〕两者均为 GPL 导出，cifs 的 GPL 许可证不是这次失败原因；两者都在候选 ABI symbol list 中。不能将上游 STG 通过解释为“这些符号没检查”，也不能将与 Google 参考的 STG 比较解释为已核对小米原厂的完整 ABI。

### 5.2 本轮源码比较结果

| 比较对象 | 官方 6.1.68 与 Google 6.1.138 的结果 | 状态 |
|---|---|---|
| include/linux/mm_types.h | Git blob 完全相同：4e9453ab5985d4f593a497227cd136d80e21a645 | 已证实 |
| __page_file_index 声明 | 均为 pgoff_t __page_file_index(struct page *page) | 已证实 |
| add_swap_extent 声明 | 均为 int，参数为 swap_info_struct 指针、两个 unsigned long、sector_t | 已证实 |
| swap_info_struct 的直接文本定义 | 已取文件对比中没有该定义的变更 | 已证实；预处理后的依赖布局仍未知 |
| include/linux/mm.h、swap.h、fs.h | 存在其他声明、内联逻辑及维护差异 | 已证实 |
| mm/swapfile.c | 两个导出函数均在此翻译单元；存在其他实现及导出差异 | 已证实 |
| scripts/genksyms/genksyms.c | 存在符号内存管理实现差异 | 已证实；不等于证明 CRC 因它变化 |

〔已证实〕因此，“struct page 在 mm_types.h 中被小米直接改大”或“这两个函数签名不同”都没有得到当前比较的支持。相同头文件也不能证明实际编译看到的类型完全相同，因为宏、间接类型、包含顺序和编译配置仍会影响展开。

〔推测〕值得验证的方向包括：该翻译单元的实际预处理类型依赖、genksyms 的输入和类型遍历，以及历史 common／vendor 源码组合的差异。本轮没有将任何一个方向标为已确认根因。

〔尚未验证〕缺少原厂准确 common／vendor 源码组合及构建时 .symtypes／预处理输入，无法还原两个原厂 CRC。尚未在相同工具链与最终配置下交叉运行旧／新 genksyms，也没有基于官方树生成新的 Module.symvers。**本轮没有定位到真正的 CRC 根因，也没有证明切换官方树可以消除冲突。**

〔推测／下一步方法〕先取得两端相同条件下的 mm/swapfile.i 和 .symtypes，对上述导出逐层比较类型展开；再单因素替换头文件、宏条件或 genksyms，分别复现原厂和候选 CRC。必须同时检查结构布局，不能把“设法重现 CRC”视为安全修复，更不能写死原厂 CRC。

## 6. 原厂配置、模块和签名风险

〔已证实〕原厂与现有候选最终配置的四项差异如下：

| 配置 | 原厂 | 候选最终 .config | 官方源码调查 |
|---|---|---|---|
| CONFIG_ARM64_CONTPTE | y | MISSING | 尚未验证：未在本轮取样的核心 Kconfig 中定位完整实现 |
| CONFIG_XIAOMI_DMABUF_HUGETLB | y | MISSING | 尚未验证：未定位可直接用于当前 common 的定义与实现 |
| CONFIG_FACTORY_BUILD | n | MISSING | 已证实：官方 arch/arm64/Kconfig 定义 bool，默认 n |
| CONFIG_GKI_HACKS_FOR_DEBUG_CONFIG | n | MISSING | 尚未验证：本轮未定位完整定义与影响 |

〔已证实〕MISSING 不等于 n。两项原厂为启用、两项为关闭，不能统称为“缺少四项启用功能”。找到厂商 fragment 不能代表把它合入 common 就能得到正确最终配置；其中许多是设备模块选项。

〔尚未验证〕没有对全仓完成所有相关符号的穷尽检索，因此未定位实现不等于官方仓库绝对不存在实现。也没有证据把这四项中的任何一项直接认定为 cifs CRC 的根因。

〔已证实〕此前 789 个变体通过的是当前静态导入 CRC／导出关系检查；不包含完整的运行布局、模块加载时序、硬件行为及 OEM 签名信任证明。504 个加载名称覆盖中包括 cifs，不能按“唯一一个失败”忽略它。

〔尚未验证〕protected GKI 签名信任、OEM 证书链以及所有实际模块布局仍未完成。公开源码不会自动赋予候选构建信任原厂模块签名的能力；本轮不生成新签名或修改验证策略。

## 7. DroidSpaces Namespace 可行性

### 7.1 已有最终 .config 与 Kconfig 依赖

〔已证实〕以下“原厂”和“候选”列来自已保存的原厂完整配置与 run 3 的 Image 解出的最终 .config，不是 fragment 的预期值。依赖由固定官方源码及 Google 候选的 init/Kconfig、arch/Kconfig、drivers/base/Kconfig 对照核查。

| 配置 | 原厂 | 现有候选最终值 | Kconfig 依赖／本轮判断 |
|---|---|---|---|
| CONFIG_SYSVIPC | n | n | 已证实：bool；启用会影响 task_struct，需 kABI 审计 |
| CONFIG_POSIX_MQUEUE | n | n | 已证实：依赖 NET；NET 已为 y |
| CONFIG_PID_NS | n | n | 已证实：处于 if NAMESPACES 中，default y 不能覆盖显式 n |
| CONFIG_IPC_NS | MISSING | MISSING | 已证实：NAMESPACES 下依赖 SYSVIPC 或 POSIX_MQUEUE；当前依赖未满足 |
| CONFIG_USER_NS | n | n | 已证实：NAMESPACES 下默认 n；官方文档列为 sandboxing 推荐项 |
| CONFIG_NAMESPACES | y | y | 已证实：依赖 MULTIUSER；已有最终配置启用 |
| CONFIG_SECCOMP | y | y | 已证实：依赖 HAVE_ARCH_SECCOMP；已有启用 |
| CONFIG_CGROUPS | y | y | 已证实：menuconfig 并 select KERNFS；已有启用 |
| CONFIG_DEVTMPFS | n | n | 已证实：bool；未开启，官方文档将其关联硬件访问 |

〔已证实〕SECCOMP_FILTER 两端均 y；其 Kconfig 依赖 HAVE_ARCH_SECCOMP_FILTER、SECCOMP 和 NET。NET、UTS_NS、NET_NS、MEMCG 两端均 y。DEVTMPFS_MOUNT 是额外的自动挂载选项，不等于具备 DEVTMPFS 本身，也不能代替容器内的权限与挂载管理。

〔尚未验证〕没有生成“修改后的官方最终 .config”，也没有通过 fragment 推导并冒充生成结果。当前缺完整官方 manifest／构建环境，且本轮限定为分析设计。下一阶段经批准生成配置后，仍必须用 Image 中的最终配置逐项验收，并检查 Kconfig 自动 select／默认值引入的其他变化。

来源：[官方 Kconfig](https://github.com/MiCode/Xiaomi_Kernel_OpenSource/blob/681e88870888dec258dd48b0ab8c908b303eb159/init/Kconfig)、[seccomp Kconfig](https://github.com/MiCode/Xiaomi_Kernel_OpenSource/blob/681e88870888dec258dd48b0ab8c908b303eb159/arch/Kconfig)、[devtmpfs Kconfig](https://github.com/MiCode/Xiaomi_Kernel_OpenSource/blob/681e88870888dec258dd48b0ab8c908b303eb159/drivers/base/Kconfig)。

### 7.2 官方补丁及其边界

〔已证实〕DroidSpaces 固定文档要求 GKI 使用对应的 SYSVIPC kABI 补丁，并直接编辑正确的 common GKI defconfig。6.1 对应 below-kernel-6.12 的补丁系列；5.10 或更早的 POSIX_MQUEUE padding 补丁不能仅因名字含 POSIX_MQUEUE 就套在 6.1 上。

〔已证实〕本次取得的 6/7/8 补丁与现有文件逐字节相同，SHA256：
`47fc945b2d73d9737d56c0f1c3a74cda0a95c30f9dc1b1abe546fa48940c4460`。

〔已证实〕对小米固定提交的 sched.h 文件快照执行 git apply --check --verbose 成功：两个 hunk 分别在 1096、1551 行匹配。这与已有候选快照检查一致，补丁未被应用。官方 task_struct 中 slot 1 已由 saved_state 使用，6/7/8 在所见源码中保留；不得盲目换成其他槽位补丁。

〔尚未验证〕文件适用性不证明槽位在当前 OEM 的真实布局中可用，也不证明新增 IPC 功能后的尺寸、对齐和模块 CRC 都保持。不能采用上游文档中“bootloop 后换槽位试”的方式替代本项目的静态布局与 ABI 证明。

〔已证实〕当前官方文档将 CONFIG_CFS_BANDWIDTH、CONFIG_CGROUP_PIDS 列为会破坏 GKI kABI、且无所列 padding 补丁覆盖的选项。现有最终配置两者均 n。方案继续保留该状态；需要 CPU／PID 限制不是关闭 MODVERSIONS 或重建部分模块的理由。

〔尚未验证〕USER_NS、IPC、seccomp、SELinux、cgroup v2 委派及容器运行时的组合行为，不能仅凭官方文档的普遍兼容声明视为本机已验证。Droidspaces 的 requirements 检测代码实际探测运行内核；配置通过之后仍有运行时验收，但不在本轮访问设备。

来源：[DroidSpaces 固定配置指南](https://github.com/ravindu644/Droidspaces-OSS/blob/cdadb9eb5d0f86aacffff60776333e6f6b73a30a/Documentation/Kernel-Configuration.md)、[固定补丁](https://github.com/ravindu644/Droidspaces-OSS/blob/cdadb9eb5d0f86aacffff60776333e6f6b73a30a/Documentation/resources/kernel-patches/GKI/below-kernel-6.12/001.GKI-below-6.12-fix_sysvipc_kabi_6_7_8.patch)、[运行检测代码](https://github.com/ravindu644/Droidspaces-OSS/blob/cdadb9eb5d0f86aacffff60776333e6f6b73a30a/src/cli/check.c)。

### 7.3 更可靠的支持方式

〔推测／方案建议〕最可靠路径是“当前 OEM 对应的 common/GKI＋已证明必要的最小 namespace 改动＋原厂模块完整验收”。公开旧版设备源码用于追踪厂商要求，不能使旧版内核自动适配新版系统。

〔已证实〕这些核心 IPC／namespace 配置是 bool，不是安装一个普通可加载模块就能补全的功能。现有缺失功能也不会因切换容器用户空间而自动出现。

〔推测／方案建议〕若准确 OEM 源码或兼容性始终无法建立，应保留原厂内核并暂停 DroidSpaces 内核路线。chroot／PRoot 等用户空间方案可以另行评估，但不等价于 DroidSpaces 的 namespace 隔离及完整 systemd 容器能力，本报告没有将其宣布为已验证替代品。

## 8. 推荐源码与构建架构

| 方案 | 本轮评估 | 决策状态 |
|---|---|---|
| 原样继续使用现有 Google 6.1.138 并进入功能编译 | 已知 cifs CRC 失败及其他未解决门槛 | 不建议进入实施 |
| 直接以公开 muyu 6.1.68 替换整个内核 | 版本不同、缺当前 manifest、未知原厂完整 ABI 和签名关系 | 不建议替换 |
| Google common/GKI＋小米厂商源码参考，最终优先收敛到 exact OEM common | 符合已观察到的官方混合构建分层，可保留现有证据并逐项定位差异 | 推荐的方案设计；等待批准 |

〔推测／方案建议〕推荐三层安排：

1. **common/GKI 层**：当前保留 0c3d559… 为实验对照；优先定位 7b9e94… 的准确源码和工具锁。只移植已证明必要的 common 修复，不整树混合 vendor 代码。
2. **厂商适配参考层**：固定官方 681e888…、设备树 21b354… 和构建规则 3b5ab5…，用于解释 Qualcomm／小米模块接口、设备配置和历史补丁。muyu_GKI fragment 的设备模块设置不直接灌入 common。
3. **验收层**：独立保留 Google STG 比较、原厂全部 790 变体／508 名称检查、配置与布局比较、保护名单、KMI generation、签名信任及 release 差异报告。所有门槛保持可见。

〔尚未验证〕这个架构是调查和后续实现建议，不是已经选定并证明可用于当前系统的最终 kernel commit。准确来源仍是最高优先级，不能因同版本 Google GKI 容易构建就跳过 OEM 差异。

## 9. 下一阶段计划与准入条件

以下均为待用户批准后的计划，本轮不执行功能修改和编译：

| 步骤 | 工作 | 完成标准 |
|---|---|---|
| A：补齐当前源码身份 | 继续追踪 OEM 7b9e94…、对应 common／vendor 及工具链 manifest；向可取得的官方发布记录交叉核对 | 精确提交／依赖齐备，或明确记录无法取得及替代风险 |
| B：复现 cifs CRC | 在固定环境生成 mm/swapfile 的预处理输入与 .symtypes，比较类型展开；单因素验证根因 | 两个 CRC 的差异原因可复现，布局影响有证据，禁止伪造 CRC |
| C：先解决 pristine 兼容性 | 明确四项配置的真实定义／实现，处理受保护模块签名信任和原厂布局证据 | 基线问题解决或形成明确不可通过结论；不能直接跳到功能构建 |
| D：最小 namespace 设计 | 对确切 common 审核 6/7/8 槽；逐项设计 SYSVIPC、MQUEUE、PID／IPC／USER_NS、DEVTMPFS 变更 | 依赖、结构尺寸、对齐、预留位使用均审查；不启用 CFS_BANDWIDTH／CGROUP_PIDS |
| E：经批准的功能实验 | 保留 ThinLTO、CFI、4 KiB 页、MODVERSIONS、protected exports；记录最终 .config 和 ABI | 全部静态验收及证据完成，仍不自动获得设备操作授权 |

〔已证实〕本轮没有触发 GitHub Actions 构建，没有替换基线，没有生成可直接刷入的内核包，没有访问设备、刷写、重启、切槽或修改温控／GPU／调度器。

## 10. 证据索引与可复核性

〔已证实〕本地证据位于 `muyu-gki-phase3/evidence/official-audit/`：

- `SOURCE_INDEX.json`：62 项唯一文件的固定 ref／路径／Git blob SHA／SHA256／来源 URL；全部 blob 身份复核通过。
- `retrieved-files*.json`：API 返回的源码文本及元数据，包括未找到的路径记录。
- `blobs/<Git-blob-SHA>.txt`：原始 UTF-8 文件字节；扁平命名避免 Windows 路径长度与 README 大小写碰撞。
- `initial-0.json` 至 `initial-6.json`：分支头、根 tree、远端工作流和仓库体积等初始查询快照。
- `oem-buildtree.json`、`oem-dttree.json`、`ds-tree.json` 及小目录查询：相关仓库目录证据。
- `oem-exact.json`、`gki-exact.json`、`oem-c96.json`、`gki-c96.json`：准确提交前缀查询结果；只代表这些仓库中的本次查询。
- `diffs/`：mm_types.h、mm.h、swap.h、fs.h、swapfile.c 和 genksyms.c 的必要文件比较。
- `sysvipc-official.patch` 及补丁检查记录：只读适用性验证，未应用。

〔已证实〕此前 BASELINE_REPORT、BUILD_REPORT、原始镜像、模块归档、Actions 记录及 source-lock 均保留。当前报告不改写此前验收失败结论。

**最终决策建议〔推测／方案建议〕：两者结合，但保留现有 Google GKI 仅作未合格的实验基线。官方 6.1.68 作为厂商参考，不直接替换当前 6.1.138；优先补齐准确 OEM common／manifest，并解决 cifs、配置与签名门槛。完成本审计后等待用户审核，再决定下一阶段实施。**
