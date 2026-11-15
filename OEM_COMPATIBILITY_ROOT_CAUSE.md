# OEM_COMPATIBILITY_ROOT_CAUSE

日期：2026-11-15（北京时间）。项目：hanjb51/muyu-gki-baseline。阶段：Phase 4 原厂兼容性根因调查。工作分支：`investigate/oem-compatibility-phase4`。

**决策结论〔推测／建议〕：现有 Google GKI 6.1.138 有继续收敛调查的现实依据，但本阶段仍不能证明它最终能收敛为“与当前 OEM 全部原厂模块完整兼容”的基线。** 本轮将原厂与候选的差异缩小到了可复核的导出 CRC、特定能力和签名信任项，并排除了若干假设；没有定位到原厂 CRC 的完整生成根因，也没有解决全部兼容性门槛。暂停于报告审核，不进入功能编译。

## 1. 输入、授权范围与证据等级

〔已证实〕已完整读取前阶段 OFFICIAL_MUYU_SOURCE_AUDIT.md、BASELINE_REPORT.md、现有 source-lock／manifest，以及 run 43708070680 的 source-verification、最终 .config、Module.symvers、编译产物与模块清单。所读关键文件的 SHA256 保存在 `evidence/phase4/phase4-inputs-read-and-hashed.json` 对应本地原始记录中。

〔已证实〕目标仍为 muyu／OS3.0.307.0.WOYCNXM，当前原厂版本来自既有采集：
`6.1.138-android14-11-g7b9e94e37cfa-mi`。本轮只读已有文件，没有实时访问设备。

〔已证实〕本轮仅进行了：公开源码查询、历史源码稀疏检出、C 预处理、host genksyms 小工具构建、现存 Image 的 BTF／导出表解析，以及现存模块的密码学验签。没有构建新的完整内核，没有启用 namespace 配置，没有生成可刷入包，没有修改 baseline 分支、ABI 规则、保护导出、MODVERSIONS、设备分区或槽位。

证据等级：

| 等级 | 用法 |
|---|---|
| 已证实 | 文件字节、固定提交、可复现输出、独立交叉检查直接支持 |
| 推测 | 可解释现象或提出后续路径，但尚缺原厂生成链／完整验证 |
| 证据不足 | 缺来源、布局、构建输入或运行验证，不能当作通过 |
| 已证实不匹配 | 实测 CRC 或特定签名验证不满足候选当前要求；不自动推断所有运行行为 |

〔已证实〕本机 CI 输入包重传曾被自动审批拒绝，原因是没有明确授权将该输入包公开；该传输未被继续重试。本轮分析改为在同一 GitHub 仓库内读取已经存在的 Actions 产物，公开源文件来自固定提交。新记录没有发布 boot、私钥或完整设备镜像。

## 2. 任务 A：准确 OEM 来源追踪

### 2.1 固定来源

| 来源 | 固定提交／标识 | 本轮确认的作用 |
|---|---|---|
| MiCode/Xiaomi_Kernel_OpenSource / muyu-v-oss | `681e88870888dec258dd48b0ab8c908b303eb159` | 官方 muyu 厂商源树，Makefile 实际为 6.1.68 |
| MiCode/kernel_devicetree / muyu-v-oss | `21b354440459b84995dd7266c95cd17c0abc110c` | 设备树参考 |
| MiCode/kernel_build / muyu-v-oss | `3b5ab5980990c0406c68d05baecd422ad5e30b8f` | 官方 Kleaf／构建规则参考 |
| 当前 Google 实验 common | `0c3d559bcd85c64dae9c9c9687abbe5347fff3ad` | 6.1.138；对应已采集的一套 Google 配套模块，不是已证明的 OEM 上游 |
| AOSP 历史 common，android14-6.1-2024-02_r1 | `0cfa80d3c398c747f9d502f5812465b082ad675a` | Makefile 为 6.1.68；用于历史源码比较 |
| CodeLinaro-mirror/la_kernel_manifest，aosp-new/common-android14-6.1-2025-06 | `977aade5c9020844157e9fb79865d0d21d41c0f3` | 找到保留的 June ACK manifest 参考；不是当前 OEM manifest |
| 既有构建锁的 AOSP manifest／superproject | `848f8dbd7fc7c40a884b614ad29f5d89199ddaff`／`c5fd854d46f3fe29b89a80e5f2cf3bc643c64f20` | 已运行 Google 候选的完整依赖锁，保持不变 |

〔已证实〕历史 common 0cfa80… 的 mm/swapfile.c Git blob 为 `ce706c4a9b38ace0fcdca5e622e4a03a65149ac1`，与官方 muyu 681e888… 中该文件相同；include/linux/swap.h 也为同一 blob `6d17e7bb330ca6bbf9107b8ac42e89e2374f784d`。这是必要文件的字节对应，不是整棵树或 Git 父链完全一致的证明。

〔已证实〕CodeLinaro 的上述 manifest 使用 common 的 `android14-6.1-2025-06` 引用及 superproject，同时含浮动项目 revision。它可以提供历史 ACK 发布线线索，不能直接当作已锁定的当前 OEM 构建，也没有将 7b9e94… 映射到某个 common。

来源：[官方 muyu](https://github.com/MiCode/Xiaomi_Kernel_OpenSource/commit/681e88870888dec258dd48b0ab8c908b303eb159)、[历史 ACK](https://github.com/aosp-mirror-neo/kernel_common/commit/0cfa80d3c398c747f9d502f5812465b082ad675a)、[CodeLinaro manifest](https://github.com/CodeLinaro-mirror/la_kernel_manifest/blob/977aade5c9020844157e9fb79865d0d21d41c0f3/default.xml)。

### 2.2 查询范围及没有证明的关系

〔已证实〕本轮对以下 GitHub 源的 commits/7b9e94e37cfa 查询均得到“没有该提交”的响应：MiCode/Xiaomi_Kernel_OpenSource、aosp-mirror-neo/kernel_common、CodeLinaro-mirror/la_kernel_common。GitHub 全局 commit 前缀搜索没有命中；全局 code 搜索的 8 个命中是社区内核 profile／文档引用，不是目标源码提交。

〔已证实〕CodeLinaro 存在 la_kernel_manifest，且本轮定位了上述 June 分支和完整 SHA。对 la_platform_manifest 的给定 `LA.VENDOR.14.3.0.r1-14500-r1.0.r1_00042.0` commit/ref 查询没有命中。前阶段 MiCode 公开索引与设备归属证据继续有效。

〔证据不足〕Android Gitiles 和 CodeLinaro 原站的准确提交页面在本工具中不可访问；不能把访问错误写成“原站确认不存在”。GitHub 镜像中的未找到也不能排除私有仓库、未公开分支、其他镜像或未发布的厂商提交。

〔证据不足〕未取得 7b9e94e37cfa 对应的完整 SHA、父链、当前系统 common／vendor 组合及 OEM manifest。未找到 cifs 的 c96cc383b8ab 编译来源。**准确 OEM GKI 来源仍未闭环，不能把 0c3d559…、0cfa80… 或 681e888… 冒充为精确匹配。**

## 3. 新的原厂二进制基准：完整导出 CRC

### 3.1 提取和交叉验证

〔已证实〕从现存 boot_a 备份中取出的原厂 raw Image SHA256：
`dd875f16a86fd08cdd68903766573a33c08426afd69b4ab2efbcade1ec15922f`。

〔已证实〕已构建 Google 候选 Image SHA256：
`208b4d40229d107bd1a46f90a606c306ea6fc237cbf6490ae5c07e19223896c9`。

〔已证实〕本轮解析 PREL32 __ksymtab／__ksymtab_gpl 与对应 __kcrctab，直接恢复两份 raw Image 的导出名称和 CRC。算法首先在候选上以 ELF 中表边界和完整 Module.symvers 验证全部 8,142 项，再应用于原厂 Image。原厂恢复后的导出名称集合与候选完全相同。

〔已证实〕原厂表还与 790 份模块进行 39,212 次导入 CRC 对照，覆盖 3,608 个被这些模块使用的原厂内核导出，没有冲突。此交叉检查支持表边界和名称／CRC 配对正确；它不是完整布局或运行兼容性证明。

### 3.2 全部差异

| 导出符号 | 原厂 Image CRC | 候选 Image CRC |
|---|---|---|
| __page_file_index | 0x12d686c5 | 0x39ba4984 |
| add_swap_extent | 0x3da4a325 | 0x2a731aba |
| page_swap_info | 0x138a96b6 | 0xb7074429 |
| unuse_swap_pte | 0x2dd1c10f | 0x440b776b |

〔已证实〕8,142 项中有 **8,138 项 CRC 相同、4 项不同**。这四个导出在当前候选源码中都来自 mm/swapfile.c。之前 790 份模块比较只发现两个导入冲突，是因为检查范围是“模块实际导入的符号”，当时还没有原厂完整导出表；并不表示原厂全部导出只有两项差异。

〔已证实不匹配〕原厂 Image 的前两个 CRC 确实等于 cifs.ko 要求，当前候选则不同。冲突不是仅由模块元数据推断出来，也不是检查程序把原厂表和候选表混淆。仍禁止覆盖 CRC 或修改检查结果来获得通过。

证据：`phase4-verified-summary.json`、`stock-raw-export-crcs.json`、`candidate-raw-export-crcs.json`、`raw-export-crc-differences.json` 及提取脚本。

## 4. 任务 B：genksyms／预处理／类型调查

### 4.1 实验环境与有效性

〔已证实〕独立分析工作流只读取原仓库已经保留的 run 43708070680 artifact，校验 ZIP SHA256 `c4c49179a93518658c18a81f60d4f978f64cf2c5f6cd6517ab288828963ad9ab`，复用生成头文件、最终配置及实际 CI host genksyms。公开 mm 源文件均固定到上述完整 SHA；官方旧树采用 blobless shallow fetch 加稀疏检出，没有克隆多分支完整历史。

〔已证实〕C 预处理使用 Ubuntu clang 14.0.0-1ubuntu1.1，目标 aarch64-linux-gnu；它不同于原内核构建的 Clang 17.0.2，因此本实验没有冒称精确重建整个原编译器环境。有效性控制是：同一输入链精确重现候选的目标 CRC，独立重建的候选 genksyms 也得到同样结果。

〔已证实〕genksyms 输入使用 __GENKSYMS__、__KERNEL__ 和已有最终配置；没有启用 namespace。记录了预处理命令、输入 SHA256、.symtypes、输出 CRC、工具源码／二进制哈希和编译器版本。输入 .i 的哈希与再生成步骤保留，未将原始 CI 输入包另行公开上传。

主要分析任务：

| 任务 | 作用 | 结果 |
|---|---|---|
| [43724800287](https://github.com/hanjb51/muyu-gki-baseline/actions/runs/43724800287) | 候选重现、导出顺序及源码单因素控制 | 分析成功；没有内核编译 |
| [43725373429](https://github.com/hanjb51/muyu-gki-baseline/actions/runs/43725373429) | 官方旧头文件和旧 C 文件交叉控制 | 分析成功 |
| [43725704320](https://github.com/hanjb51/muyu-gki-baseline/actions/runs/43725704320) | BTF type-tag 控制 | 分析成功；没有重现原厂 CRC |
| [43726785665](https://github.com/hanjb51/muyu-gki-baseline/actions/runs/43726785665) | 配套旧 genksyms 完整工具重建 | 分析成功；没有重现原厂 CRC |

〔已证实〕另保留了中间实验记录，包括解析结果正则修正，以及完整旧 parser 首次链接缺少 YYDEBUG 编译标志的失败任务 43726603622。后者已按匹配的生成器编译要求修正；这些是分析工具故障，不是新内核构建失败，也没有隐藏失败产物。

### 4.2 单因素结果

| 分析输入／工具 | __page_file_index | add_swap_extent | 解释 |
|---|---|---|---|
| 原厂 Image／模块要求 | 0x12d686c5 | 0x3da4a325 | 要解释的目标 |
| 候选原始输入＋原 CI genksyms | 0x39ba4984 | 0x2a731aba | 精确重现候选 |
| 仅移除新增 unuse_swap_pte 导出 | 0x39ba4984 | 0x2a731aba | 不是该导出单独导致 |
| 仅移除新增 page_swap_info 导出／同时移除两者 | 0x39ba4984 | 0x2a731aba | 没有恢复原厂值 |
| 反转导出声明顺序 | 0x39ba4984 | 0x2a731aba | 排除本次顺序假设 |
| 官方旧 swapfile.c＋候选头文件 | 0x39ba4984 | 0x2a731aba | 单换 C 文件没有恢复 |
| 官方旧 C 文件＋官方旧头文件，复用候选生成配置 | 0x39ba4984 | 0x2a731aba | 不是精确旧发布复现；是头文件控制 |
| 候选 C 文件＋官方旧头文件 | 0x39ba4984 | 0x2a731aba | 同上 |
| 移除预处理输入中的 BTF type-tag 注解 | 0xe1efd216 | 0xaf8bf7b9 | CRC 会变，但不是原厂值 |
| __BINDGEN__ 注解控制 | 0xe1efd216 | 0xaf8bf7b9 | 独立得到同一注解控制结果 |
| 独立重建候选 genksyms | 0x39ba4984 | 0x2a731aba | 工具重建控制通过 |
| 完整配套重建官方旧 genksyms | 0x39ba4984 | 0x2a731aba | 旧工具本身仍未给出原厂值 |

〔已证实〕完整旧工具使用该官方提交自己的 genksyms.c、genksyms.h、parse.y、lex.l、keywords.c，以 GCC 11.4.0、Bison 3.8.2、Flex 2.6.4 构建，生成器二进制 SHA256 `9ebfe1207542c7dca248683ec8adc87077c563fec4a7e738c7bff735763a6a88`。它与候选工具在相同输入上结果一致。

〔已证实〕曾有“只替换旧 genksyms.c、仍用新头文件／生成 parser”的混合控制，出现 const 警告及另一组 CRC。该组合不是配套历史工具，已在记录中标为 hybrid，**不把它用于原厂根因结论**。完整配套重建结果取代这种不充分推断。

〔证据不足〕官方旧头文件实验复用现有候选生成配置，且不是 c96cc… 当年的完整模块构建环境。实验的否定结论有范围：它排除了这些单因素组合，不能证明官方旧源码永远无法对应原厂，也不能证明所有可能的构建条件都已覆盖。

### 4.3 已定位和未定位的层次

〔已证实〕四个 CRC 差异聚集于 mm/swapfile.c；原厂模块要求与原厂 raw Image 相符；候选 CRC 能重现；公开旧 C／头文件、导出顺序、完整旧 genksyms 这些控制没有复现原厂值。BTF 注解影响 CRC，但已测试的注解控制不是答案。

〔推测〕调查范围应集中于 OEM 的该翻译单元及其 __GENKSYMS__ 可见类型／宏／头文件包含状态、原厂符号类型参考输入或未公开的 kABI 保留处理，而不是继续任意切换月度版本。相同实际布局也可能存在不同类型文本或生成链，仍需原始输入证明。

〔证据不足〕**尚未解释出原厂两个 CRC 的完整生成根因。** 缺少 OEM 该单元的预处理输入、.symtypes／可能的 .symref 与实际编译命令，也缺 cifs 原始 6.1.68 构建配置和类型基准。因此没有提出或实施“修复 CRC”的源码补丁。

## 5. 实际结构布局：BTF 交叉证据

〔已证实〕从两份 raw Image 中解析了嵌入 BTF，原厂含 129,267 个 type ID，候选含 129,148 个。不是从 defconfig 猜测结构尺寸。

| 结构 | 原厂字节 | 候选字节 | 本次表示比较 |
|---|---:|---:|---|
| page | 64 | 64 | 相同 |
| folio | 96 | 96 | 相同 |
| swap_info_struct | 296 | 296 | 相同 |
| swap_extent | 48 | 48 | 相同 |
| address_space | 240 | 240 | 相同 |
| file | 264 | 264 | 相同 |
| inode | 704 | 704 | 相同 |
| mm_struct | 960 | 960 | 相同 |
| task_struct | 4800 | 4800 | 相同 |
| signal_struct | 1128 | 1128 | 相同 |
| module | 1088 | 1088 | 相同 |
| dma_buf | 304 | 304 | 相同 |

〔已证实〕上述比较不仅看 sizeof，还比较成员名、位偏移、位域宽度、类型标记及匿名嵌套成员的表示；忽略不同构建中的 type ID 数值。进一步从目标 genksyms 依赖名称映射到两份 BTF 的 682 条命名类型记录，在本次规范化表示下没有差异。

〔证据不足〕这不是全内核结构布局相等、所有 508 个模块类型契约相等或函数语义相等的证明。BTF 与 genksyms 的输入／表示不同；预处理专用定义、注解、未映射／前向声明类型和运行语义不由该比较完全覆盖。

〔已证实〕原厂 cifs 的 ELF 含 split BTF，字符串段首字节不是普通完整 BTF 的空字符串。其 .comment 指向 r487747c／Clang 17.0.2。**不能把当前原厂 6.1.138 的 base BTF 任意套到该 6.1.68 模块上解析 type ID**；它真正编译时的 base BTF 尚未取得。

## 6. 任务 C：四项配置的实质

| 配置 | 原厂／候选 | 本轮新证据 | 判断 |
|---|---|---|---|
| CONFIG_ARM64_CONTPTE | y／MISSING | 原厂 BTF 有 contpte_ptep_get、contpte_set_ptes、__contpte_try_fold 等；候选无这些 feature 名称 | 已证实有对应实现差异；不是仅配置文本差异 |
| CONFIG_XIAOMI_DMABUF_HUGETLB | y／MISSING | 原厂 BTF 有 dmabuf_huge_remap_pfn_range、dma_buf_hugetlb_get_unmapped_area、split／zap_dmabuf_huge_pmd 等；候选无 | 已证实存在厂商内存映射实现；完整源代码和依赖未知 |
| CONFIG_FACTORY_BUILD | n／MISSING | 官方 arch/arm64/Kconfig 定义 bool、默认 n | 已证实定义来源；当前未启用，不等于缺少已启用能力 |
| CONFIG_GKI_HACKS_FOR_DEBUG_CONFIG | n／MISSING | 官方 init/Kconfig.gki-debug 有定义，select TRACE_PREEMPT_TOGGLE、TRACE_IRQFLAGS、GKI_HIDDEN_RCUTORTURE；后者 select TASKS_RUDE_RCU | 已证实此前未定位的定义；当前该选项 n |

〔已证实〕ARM64_CONTPTE 的上游功能引入可追到 Linux 提交 `4602e5757bcceb231c3a13c36c373ad4a750eddb`，其 Kconfig 依赖 TRANSPARENT_HUGEPAGE，支持用户映射连续 PTE。该上游提交提供功能来源，不证明 OEM 精确采用同一补丁或完整系列。

〔证据不足〕尚未取得 OEM 的 contpte 回移植系列及 XIAOMI_DMABUF_HUGETLB 的完整实现、Kconfig 依赖和厂商调用约束。搜索只命中配置 dump，不足以反推实现。不能给候选配置简单加 y 来替代实际代码。

〔推测〕两项 y 所对应的地址映射语义、TLB 和大页行为，可能是需要恢复的 OEM 能力差异；即使 CRC 全部一致仍不能自动忽略。未证明它们必然使某个模块加载失败，也未证明它们是四个 CRC 的直接原因。

〔已证实〕两项 n 与缺失定义不能机械等同，但不能再称为“缺少四项启用功能”。本轮没有为追求配置文本相等而添加无实现的占位 Kconfig，也没有改变原厂配置。

来源：[上游 contpte](https://github.com/torvalds/linux/commit/4602e5757bcceb231c3a13c36c373ad4a750eddb)、[官方 debug Kconfig](https://github.com/MiCode/Xiaomi_Kernel_OpenSource/blob/681e88870888dec258dd48b0ab8c908b303eb159/init/Kconfig.gki-debug)。

## 7. 模块签名、保护导出和信任

### 7.1 从镜像恢复公钥并验签

〔已证实〕两份 Image 均发现一张 Build time autogenerated kernel key 证书，但公钥不同。不能因 CN 字符串相同认定是同一密钥。

| 项目 | 原厂 | 候选 |
|---|---|---|
| 证书 SHA256 | 1ab85e414a2cdae609f86beb41f172da760df8a72ef486de320bc7c295624505 | 4bfd7d54a94838093efb3bb6476de8821ebf7aec70edba08131d77eab654ab5b |
| 公钥 SPKI SHA256 | 753fb984c5b3678f730f389f29e5ee23601b9ed959e5d37230aa0d876663c0ca | 0df0aef8e998fcedf1b4ade76824a9fda9cb6a9e0988b533b33620a8cda172e1 |
| 原厂小米组 60 模块，用该公钥验签 | 60 PASS | 60 FAIL |
| 保留的 Google 组 60 模块，用该公钥验签 | 60 FAIL | 60 FAIL |

〔已证实〕已逐个验证 PKCS#7/CMS 数字签名，不只是比较 signer 名称或序列号。原厂公钥通过的 60 个文件位于 g7b9e94…-mi 目录；另一组 signer serial 不同。作为负控制，修改一个已通过模块的单个被签名字节后，验签失败。

〔证据不足〕Google 组在“原厂这把公钥”下失败，不等于证实它们在所有可能系统信任环境中都不可加载，也不能据此推断它们就是当前正在使用的文件。文件库存、名称加载清单与运行时具体文件身份仍应区分。

### 7.2 与 MODULE_SIG_PROTECT 的关系

〔已证实〕原厂和候选相关最终配置包含 MODULE_SIG=y、MODULE_SIG_PROTECT=y、MODULE_SIG_ALL=y，MODULE_SIG_FORCE=n，SYSTEM_TRUSTED_KEYS 为空、SECONDARY_TRUSTED_KEYRING=n。签名保护不等于强制全部 Vendor 模块都带签名。

〔已证实〕候选的 kernel/module/signing.c 对未验证签名不授予 sig_ok；kernel/module/main.c 在模块没有 sig_ok 却导出受保护符号时返回 EACCES。签名策略的正常工作正是要保留这种区分，不能删除名单来绕过。

〔已证实〕清单中有 50 个 GKI 文件变体、25 个唯一名称实际导出了当前保护名单中的符号。它们不是仅因为“目录属于 system_dlkm”就被判为受保护，而是由导出集合与保护名单求交得到。

〔已证实不匹配〕候选默认嵌入的公钥不能验证这些原厂文件；对需要 sig_ok 的受保护导出模块，这是实际的默认信任阻塞。仍需结合完整 keyring 初始化证明最终 kernel acceptance，不能把离线验签直接等同于加载成功。

〔推测／可行路径〕如果将来选择继续，优先审计如何保持原厂已有公钥信任关系，并验证受保护导出及全部原厂签名。**验证已经签好的旧模块只需要正确的公钥，不必取得 OEM 私钥。** 这与签出新的 OEM 身份模块不同，也不能扩展为信任任意自签名密钥。此建议尚未实施，必须经过后续审核。

〔证据不足〕从当前备份取得公钥、并验证其与模块的密码学关系，不等于独立验证完整 OEM AVB 制造商根信任链。本轮没有操作或改写 keyring、证书配置、签名算法或保护规则。

来源：[签名路径](https://github.com/aosp-mirror-neo/kernel_common/blob/0c3d559bcd85c64dae9c9c9687abbe5347fff3ad/kernel/module/signing.c)、[保护导出路径](https://github.com/aosp-mirror-neo/kernel_common/blob/0c3d559bcd85c64dae9c9c9687abbe5347fff3ad/kernel/module/main.c)。

## 8. 兼容性状态分类

| 事项 | 分类 | 证据边界 |
|---|---|---|
| 8,138 个同名内核导出的 CRC | 已证实该项相同 | 不推出全部布局或语义相同 |
| 4 个 swapfile 导出 CRC | 已证实不匹配 | 两个被现存 cifs 导入，两个是原厂完整表比较新发现 |
| 12 个核心结构及映射到的 682 条命名 BTF 表示 | 已证实本次表示相同 | 不覆盖全内核、所有模块或 genksyms 专用表示 |
| 原厂小米 GKI 组数字签名与恢复公钥 | 已证实密码学验证通过 | 不直接宣称候选完整加载成功 |
| 这些模块与候选默认公钥 | 已证实不匹配 | 默认保护模块信任需处理 |
| 两项原厂 y 功能实现 | 已证实与候选存在能力差异 | 未证明所需 OEM 具体补丁全集 |
| 当前准确 OEM 源码／manifest／完整生成链 | 证据不足 | 不能宣布 exact source match |
| 完整原厂 Vendor／GKI 模块兼容 | 未通过／证据不足 | 保持此前 NOT_ACCEPTED 结论 |

## 9. 尚未解决的阻塞与下一阶段建议

以下是建议，不是本轮已执行的基线修改：

1. **CRC 闭环**：取得 OEM mm/swapfile 的实际 __GENKSYMS__ 预处理输入、.symtypes／可能的 .symref、编译命令和类型保留规则。另需 cifs 的 c96cc… 构建配置与 base BTF。以相同输入精确重现四个原厂 CRC，再解释必要的源码差异。不得硬编码 CRC、关闭 MODVERSIONS 或忽略失败。
2. **当前源码身份**：继续追踪 7b9e94… 的完整源码和 common／vendor／工具链 manifest。若无法取得，明确将后续工作定义为“重建近似基线”，不得改名为原厂精确重建。
3. **启用能力的来源**：补齐当前 contpte 回移植和 Xiaomi dma-buf 大页实现，分析对模块及用户映射的要求。不能仅恢复两行配置文本。
4. **信任复现**：在不放宽签名保护的前提下设计原厂公钥信任保留方案，再对 120 个 GKI 文件及相关保护关系验收；不要求获取用于验证旧签名并不需要的私钥。
5. **扩展验收**：对全部 508 个名称的相关类型与调用关系继续验证；保留 790 份变体、最终配置、布局检查及原厂／Google ABI 对照。namespace 功能应继续等待 pristine 兼容性问题有结论之后再单独审核。

## 10. 对最终问题的明确回答

**现有 Google GKI 6.1.138 是否具备收敛的现实可能？**

〔推测／建议〕**有条件性的技术可能，值得继续做有边界的根因调查；但现在不能证明存在一条已经可执行且保证成功的完整收敛路径。** 有利证据是：两边导出集合相同，8,138/8,142 个 CRC 相同；已比较的核心 BTF 表示相同；原厂小米模块的签名验证公钥已经恢复，信任问题有可研究的具体对象。

〔证据不足〕缺的不是“再编译一个能成功的 Image”，而是：

- 能复现四个原厂 CRC 的准确生成输入、源码／保留规则与模块历史类型基准；
- 当前 OEM 源码身份及两项原厂已启用能力的完整实现；
- 保持原保护策略的完整信任复现、全部模块类型契约和运行语义证据。

〔决策〕本阶段保持 **NOT_ACCEPTED**。不替换 baseline，不进入功能内核编译，不将有限 CRC／布局相同写成原厂全面兼容。报告及证据提交独立分支后停止，等待审核。
