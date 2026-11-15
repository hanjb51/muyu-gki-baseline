# Phase 5：OEM Compatibility Convergence Feasibility

目标：Xiaomi Pad 7 Pro / muyu，HyperOS 3.0.307.0.WOYCNXM，原厂 `6.1.138-android14-11-g7b9e94e37cfa-mi`。

**决策：BLOCKED。当前没有足够证据，值得开展一次以“原厂模块兼容性收敛”为目标的新 pristine GKI 实验构建。** 这是当前可验证路线的阻塞判断，不是证明 Google GKI 永远不能适配。离线签名信任方案取得进展，但完整 OEM 功能实现及四个 CRC 的原厂生成输入仍缺失；再次完整编译不会自动补上这些证据。

## 1. 范围与固定基准

【已证实】本阶段仅执行源码/API 调查、既有二进制与 BTF 分析及 Python 离线验证。没有完整内核编译、设备连接、刷写、重启、槽位切换或 namespace 功能启用。未修改基线源码、配置、ABI/KMI 规则、保护导出表或 Module.symvers。没有生成可刷写包。

审阅前置材料：`OFFICIAL_MUYU_SOURCE_AUDIT.md`、`BASELINE_REPORT.md`、`OEM_COMPATIBILITY_ROOT_CAUSE.md`、现有 source-lock、Phase 4 最终 CRC 产物及原厂公钥验签记录。沿用 Phase 4 的排除结果，不重复历史控制实验。

| 对象 | 固定身份 / 证据 |
|---|---|
| 不变 baseline 分支 | `baseline/muyu-gki`，`f99f842f61b1ae660badbe97d933b3705916b9f7` |
| Phase 4 父提交 | `6a7a3d83a21183b676f6c881e102bf54090c77f6` |
| 本阶段独立分支 | `investigate/phase5-convergence-feasibility` |
| Google common 候选 | `0c3d559bcd85c64dae9c9c9687abbe5347fff3ad`，Linux 6.1.138 |
| 小米官方 muyu-v-oss | `681e88870888dec258dd48b0ab8c908b303eb159`，实际 Linux 6.1.68 |
| AOSP manifest / superproject | `848f8dbd7fc7c40a884b614ad29f5d89199ddaff` / `c5fd854d46f3fe29b89a80e5f2cf3bc643c64f20` |
| 现有完整构建 | [run 43708070680](https://github.com/hanjb51/muyu-gki-baseline/actions/runs/43708070680)：编译及上游 STG 通过，原厂兼容性未通过 |
| Phase 4 最终定向工具验证 | [run 43726785665](https://github.com/hanjb51/muyu-gki-baseline/actions/runs/43726785665)，分析提交 `277c66b8676cafbaf75f50aeed3a5cd1755b1a81` |

Phase 4 最终 ZIP SHA256：`48b9533a1b0fee8ee0fedafa99381e42c778e01c04c9b033b7695764908ebef2`。
原厂 Image SHA256：`dd875f16a86fd08cdd68903766573a33c08426afd69b4ab2efbcade1ec15922f`。
候选 Image SHA256：`208b4d40229d107bd1a46f90a606c306ea6fc237cbf6490ae5c07e19223896c9`。

【尚未验证】`7b9e94e37cfa` 的完整提交 SHA、准确 OEM common 源码/manifest 及其与公开 ACK 的提交关系仍未恢复。不能把版本号相同或厂商分支名相同视为来源一致。

## 2. 任务 A：原厂公钥信任

### 2.1 现有证据与最小设计

【已证实】Phase 4 从既有原厂 Image 恢复的 X.509 DER SHA256 为 `1ab85e414a2cdae609f86beb41f172da760df8a72ef486de320bc7c295624505`，公钥 SPKI SHA256 为 `753fb984c5b3678f730f389f29e5ee23601b9ed959e5d37230aa0d876663c0ca`。候选 DER SHA256 为 `4bfd7d54a94838093efb3bb6476de8821ebf7aec70edba08131d77eab654ab5b`，SPKI 为 `0df0aef8e998fcedf1b4ade76824a9fda9cb6a9e0988b533b33620a8cda172e1`。相同证书 CN 不代表同一密钥。

【已证实／源码】候选提交的以下链路已逐项读取并保存文件 Git blob SHA：

1. `certs/Makefile`：`CONFIG_SYSTEM_TRUSTED_KEYS` 经 `extract-cert` 生成 `certs/x509_certificate_list`；候选自己的 `CONFIG_MODULE_SIG_KEY` 单独生成 `signing_key.x509`。
2. `certs/system_certificates.S`：模块签名证书和额外 X.509 列表均嵌入 `system_certificate_list`。
3. `certs/system_keyring.c`：`device_initcall` 初始化可信 keyring，`late_initcall(load_system_certificate_list)` 将证书装入 `.builtin_trusted_keys`。关闭 secondary keyring 时，验证请求仍回退到 builtin keyring。
4. `kernel/module/signing.c`：只有 `verify_pkcs7_signature()` 成功才设置 `info->sig_ok=true`，随后传给 `mod->sig_ok`。

【推测／待集成验证的最小方案】保留候选模块签名密钥及 `CONFIG_MODULE_SIG=y`、`CONFIG_MODULE_SIG_ALL=y`、`CONFIG_MODULE_SIG_PROTECT=y`；沿用原厂 `MODULE_SIG_FORCE=n`，不把它改成 y（PROTECT 的 Kconfig 依赖 `!MODULE_SIG_FORCE`）。只在今后获批的实验分支把 `CONFIG_SYSTEM_TRUSTED_KEYS` 指向经过固定指纹验证的 **OEM 公钥 PEM**。本阶段未实际修改配置。

证据目录的 `oem-public-certificate.pem` 是设计输入；`combined-public-certificates.pem` 仅用于离线模拟“候选签名证书 + OEM 公钥”集合，不需要把候选证书重复写入额外列表。不需要 OEM 私钥，也不重新签署原厂模块。新增信任根是明确的信任范围扩展，应固定来源和指纹；不能按 CN 模糊匹配或信任任意外来证书。

### 2.2 本阶段新离线测试

`offline_checks.py` 重用 Phase 4 CMS 解析/密码学验证器，新增 issuer DER、serial 查找、组合证书集合测试及 PEM 往返验证。使用原始已采集模块，不生成签名身份。

| 输入 | 仅候选证书 | 候选 + 已恢复 OEM 公钥 | 解释 |
|---|---:|---:|---|
| 小米原厂 system_dlkm 变体 60 份 | 0/60 | 60/60 | 新集合能验证实际原厂签名 |
| 已有候选构建模块 60 份 | 60/60 | 60/60 | 增加 OEM 公钥不排斥已有候选签名 |
| 历史 Google system_dlkm 变体 60 份 | 0/60 | 0/60 | 另一 signer 不因增加 OEM 公钥而获得信任 |
| 原厂正向样本翻转首个已签名字节 | 拒绝 | 拒绝 | 内容篡改负向测试 |
| 从集合移除 OEM 证书 | 拒绝原厂样本 | 不适用 | 缺少正确信任根负向测试 |
| 去掉签名尾标识的样本 | 拒绝 | 拒绝 | 无签名不能成为验签成功 |

【已证实】5 项断言通过；逐模块 SHA、集合 PEM SHA、原始与篡改样本 SHA 保存于 `evidence/combined-trust-tests.json`。通过的 60 份小米变体包括 25 份实际导出保护表符号的变体；历史 Google 对应 25 份仍不受信任，合计覆盖 25 个名称的 50 份保护导出变体，详见 `protected-export-coverage.json`。不能把历史 Google 变体的拒绝误报成设备当前小米文件的失败，也不能宣称信任所有 120 份。

【尚未验证】这不是 Linux X.509 解析器、实际 `extract-cert` 构建、内建 keyring 初始化或 module loader 集成测试；尚未证明编译后证书实际存在且能被内核选中，也未做设备加载。未来实验还需检查最终配置、证书列表长度/DER 指纹、内核支持的密码算法、撤销/黑名单及实际验签路径。离线成功不能替代这些验收。

### 2.3 MODULE_SIG_PROTECT 的实际约束

【已证实／源码】`kernel/module/main.c` 有两个独立门槛：

- 模块导出 protected 表中的符号且 `!mod->sig_ok`，返回 `-EACCES`。
- 未验签成功的模块导入不在 unprotected 表中的符号，若提供方是 `sig_ok` 的 GKI 模块，同样拒绝。

`signing.c` 的 PROTECT 分支允许部分未知密钥/无签名情况进入后续处理，并不赋予 `sig_ok`。签名格式错误或坏签名也不能笼统理解为允许加载。原厂 vendor 模块可能本就无签名；将 FORCE 强制打开反而改变原厂策略。最小方案不改变任何分支或保护表。即使 `sig_ok` 成功，重复符号、CRC、依赖、布局和运行语义仍独立检查；不能同时加载原厂与候选同名提供方。

## 3. 任务 B：两项 OEM 功能实现

### 3.1 ARM64_CONTPTE

【已证实】原厂配置为 y，候选无该 Kconfig。上游可固定的真实实现起点是 Linux 提交 [`4602e5757bcceb231c3a13c36c373ad4a750eddb`](https://github.com/torvalds/linux/commit/4602e5757bcceb231c3a13c36c373ad4a750eddb)：新增 Kconfig，依赖 `TRANSPARENT_HUGEPAGE`，Makefile 编入 `contpte.o`，重构 pgtable API、处理 TLB/脏位/访问位并将此前内联 API 所需函数导出。需要前置的 ptep API 重构及后续修复，不能只加入一个选项或复制单个 C 文件。

本次固定的后续公开提交：

| SHA | 内容 |
|---|---|
| `311a6cf29690bb8295327bad0e76e0ad48cadcc4` | wrprotect_ptes 批处理 API |
| `6b1e4efb6f5499ae8f9f5cdda7502285a0edbf51` | get/clear_full_ptes 批处理 API |
| `f0c2264958e18bc7bc35b567d51b99461e4de34f` | 自动 fold；本次读取完整 contpte.c |
| `912609e96cd728766373d84903f12a6d836de518` | contpte 导出限制为 GPL |
| `94c18d5f7e0d612ce3fb9cb4aa8cfb1308d57a0a` | lockless getter 注释修正 |

【已证实／新增 BTF】从原厂 BTF 提取 11 个 contpte 函数及原型。存在 `__contpte_try_fold`，说明不只具备首次引入提交的 unfold 功能。原厂还有 `contpte_clear_ptes(..., unsigned int, int)->pte_t` 和 `contpte_set_wrprotects(..., unsigned int, int)->void`；公开 f0c226 版本则使用 `contpte_clear_full_ptes`、`contpte_get_and_clear_full_ptes` 和四参数 `contpte_wrprotect_ptes`。这至少表明该公开版本不能直接当作 OEM 精确接口版本。

【推测】这是上游系列的某个回移/演变版本，但函数名和原型不能固定准确补丁集合或证明行为一致。该功能影响页表内联代码、TLB、批处理及模块调用接口；具体 KMI/结构影响必须对准确回移版本重新比较。Phase 4 的部分结构相同不是该补丁全部 ABI 不变的证明。

【尚未验证／阻塞】OEM 6.1 回移的完整系列、前置改动、后续修复和构建依赖未取得。本次 MiCode 索引检索没有定位到完整实现；搜索只覆盖服务可索引内容，不证明所有分支/互联网均不存在实现。

### 3.2 XIAOMI_DMABUF_HUGETLB

【已证实】原厂为 y；候选没有完整实现。新增原厂 BTF 恢复 11 个相关函数原型，涵盖 remap、split、zap、move、VMA adjust 和 PMD lock，说明需要 MM 多路径协作，而非空壳 Kconfig。

一个重要的新反证：原厂 BTF type ID 67620 的函数为：

```c
int dmabuf_huge_remap_pfn_range(struct vm_area_struct *,
    unsigned long, unsigned long, unsigned long, pgprot_t, unsigned int);
```

【已证实】公开 GitHub 精确函数检索命中 3 个 peridot 社区仓库的同一类调用文件，没有得到函数实现。已固定读取 `sumithemmadi/kernel_xiaomi_peridot` 提交 `1bf70b191d108a70a06bdb2055f9d21cf8cc92ee` 的 `drivers/dma-buf/heaps/qcom_dma_heap.c`，blob `1784dc722af976ba89c59c2eb546e258997a2431`。它通过 `debug_symbol_lookup_name` 查找名字，声明的函数指针只有 **5 个参数**，缺少上述末尾 unsigned int。MiCode muyu 同路径文件 blob `758f2a68c9a4024c878798b91a5a46e3f50d8225` 无此调用路径。

【推测】社区文件可以帮助定位功能家族，但不能视为当前 muyu OEM 实现，更不能直接移植该函数指针调用。缺失第六参数会使调用契约无法成立；其语义和默认值未知。本轮只分析该查找代码，不采用符号查找作为保护导出绕过方案。

【尚未验证／阻塞】准确 Kconfig、Makefile、完整 MM 实现、VMA/PMD 生命周期挂接、锁协议、错误回退、结构/内联 ABI 差异和配置依赖均未恢复。搜索 `CONFIG_XIAOMI_DMABUF_HUGETLB` 命中 11 个主要为配置转储/引用的结果；精确 Kconfig 定义和 MiCode 组织范围相关实现查询没有命中。BTF 提供接口与类型线索，不能恢复函数体、条件编译、宏、锁顺序或完整来源。需要 OEM 源码或可证明等价的完整实现，当前没有可审核的最小移植方案。

## 4. 任务 C：四个 CRC 的定向调查

### 4.1 基准结果及输入边界

【已证实／沿用 Phase 4】8,142 个导出中仅以下四个 CRC 不同；8,138 个相同不是全兼容结论。只有 cifs 目前实际导入前两个冲突符号。

| 符号 | 原厂 | 候选 | 候选 GENKSYMS 直接参数依赖 |
|---|---|---|---|
| `__page_file_index` | `12d686c5` | `39ba4984` | `struct page *` |
| `add_swap_extent` | `3da4a325` | `2a731aba` | `struct swap_info_struct *`、`sector_t` 等 |
| `page_swap_info` | `138a96b6` | `b7074429` | 返回 swap_info_struct *，参数 page * |
| `unuse_swap_pte` | `2dd1c10f` | `440b776b` | vm_area_struct *、pmd_t *、swp_entry_t、folio * |

Phase 4 exact genksyms 二进制 SHA256：`1b34217b07a1b553bbffd841293bddf4ef7bf6d2f53d7251adb7c2dab516c32b`。候选 `.i` SHA256：`7c216c968296a928fed2a91e286749780bab42602128257d9b18710473de2d67`。

【已证实／证据边界】Phase 4 保存了预处理命令、输入来源/哈希、输出 `.symtypes`、genksyms stdout/stderr 和重建脚本；最终结果 ZIP **没有保存完整原始 `.i` 字节**，也从未取得 OEM `.i`。因此不能声称本轮直接逐字节比较了原厂与候选预处理输入。输入可按已存配方重建，原厂输入不可重建。

### 4.2 新的 symref / 类型保留源码审计

【已证实】候选 `scripts/Makefile.build`（blob `1827bc1db1e98f5d4bfd84ac206f2cce5accefd9`）明确执行：

```make
$(if $(KBUILD_PRESERVE), -p)
-r $(or $(wildcard $(2:.symtypes=.symref)), /dev/null)
```

这意味着匹配路径存在 `.symref` 时会读取参考类型；不存在时读 `/dev/null`，`KBUILD_PRESERVE` 非空会启用 preserve。不能仅凭默认工具输出假定原厂没有参考输入。

【已证实】候选 `genksyms.c`（blob `6b0eb3898e4ec7a8a3925aa400003e77c16ab45a`）的 `read_reference()` 可读取类型定义与 override 标记；`__add_symbol()` 对 override reference 且 preserve 的情况能够保留参考定义并提示忽略 modversion change。其他不允许的类型变化可在 preserve 下报错。该机制处理的是类型表示，不是简单读取外部 CRC 值。`.symref`、`-p`、解析器规则及 `__GENKSYMS__` 条件代码均可使 CRC 输入与最终 BTF 呈现不同。

【已证实／新增清点】已保存的 `kernel-headers.tar.gz` 与 `modules_prepare_outdir.tar.gz` 内 `.symref` 文件数均为 0。完整归档 SHA、目录条目数、四个目标 `.symtypes` 与 Phase 4 stdout 摘录保存于 `genksyms-input-audit.json`。这些是候选产物，不能据此断言 OEM 构建不存在 symref、外部生成步骤或特殊参数。公开精确 `swapfile.symref` 索引检索无命中，同样不是不存在的证明。

【推测】OEM 的 GENKSYMS 特定类型表示、参考输入或预处理宏差异，仍可能解释“BTF 对得上但 CRC 不同”。不过目前没有一个已恢复的 OEM 类型定义/参考文件能自然生成目标 CRC，因此 **symref 是未证实的假设，不是已定位根因**。不能按目标 CRC 反推伪造 `.symref`，也不能以旧参考压住真实布局变化制造通过。

### 4.3 不重复已排除的控制实验

【已证实／沿用】Phase 4 已比较候选/官方 C 与必要旧头文件组合、移除/调整导出、类型标记处理、候选重建工具和完整历史 parser/lexer/header 工具。有效的完整历史工具仍产生候选 CRC；移除 BTF tag 的结果也不是原厂 CRC。旧 C 与新 parser/header 的混合工具结果不能当作历史工具证据。本阶段没有重跑这些实验。

【尚未验证／阻塞】缺少 OEM 的 `mm/swapfile.c` 及包含闭包、原始 GENKSYMS `.i/.symtypes`、可能的 `.symref`、`KBUILD_PRESERVE` 与完整命令、工具二进制/源码。若取回任一组真实 OEM 输入，下一步才是找出最小类型表示差异并自然复现四个 CRC。当前 BTF 的 12 个核心直接布局及可映射类型表示相同，只排除了已比较范围内的布局差异，不排除源级 tag/typedef/匿名类型/条件表示差异，也不证明所有模块运行语义相同。

历史 cifs 的 split BTF 需要其原始 6.1.68 base BTF，不能拿当前 6.1.138 的 type IDs 代替；该历史基准仍缺失。

## 5. 任务 D：兼容性阻塞矩阵

下表“需要未公开源码”表示当前解决路径对准确 OEM 输入的依赖，不声称证明源码永远不会公开。

| 项目 | 已证实事实 | 缺少证据 | 可行解决方法 | 需要未公开 OEM 源码？ | 能否离线验证 | 剩余风险 / 状态 |
|---|---|---|---|---|---|---|
| OEM 公钥信任 | 实际小米签名可由恢复公钥验证；组合集合保留候选签名 | Linux 证书提取、keyring、加载路径集成结果 | 在实验分支用 SYSTEM_TRUSTED_KEYS 嵌入固定 OEM 公钥，保留原验证链 | 否；公钥已取得 | 密码学部分已通过，集成仍待核验 | 信任范围增加；不能代表模块兼容。可设计，未集成 |
| 保护导出/导入 | sig_ok 是两个保护门槛的实际输入 | 最终模块集合与全部符号提供方关系 | 固定保护表，检查提供方唯一性/签名/依赖；不改 main.c 门槛 | 通常不需要，取决于完整集合 | 可做静态关系验收；不等于加载验收 | 历史 Google signer 仍不信任；不能混装同名提供方 |
| 四个 CRC | 四项冲突可靠；已有控制不能复现 OEM | OEM 预处理/参考类型/命令及准确包含闭包 | 取得真实输入，对类型表示做定向差分，自然生成四项 CRC | 当前依赖尚未取得的 OEM 源码或生成输入；未证明必须私有 | 取得输入后可以 | 根因未定位，当前硬阻塞 |
| ARM64_CONTPTE | 原厂 BTF 有实际实现；上游系列可追踪；接口有版本差异 | 准确 OEM 回移系列、前置/修复及依赖 | 恢复完整系列，与 BTF/配置/导出/布局逐项核验 | 当前需要准确 OEM 回移或等价的可证明版本 | 源码/ABI 部分可以；TLB/并发行为不能完全离线证明 | 单补丁移植不可接受，阻塞 |
| XIAOMI_DMABUF_HUGETLB | 11 个函数原型；remap 六参数与公开调用方五参数不符 | 完整实现、Kconfig/Makefile、MM hooks、锁与错误路径 | 获取完整可追溯实现，验证原型和 MM 生命周期 | 是，当前实现未取得；公开调用方不能替代 | 取得后可做部分离线验证 | 语义/布局/锁行为未知，关键硬阻塞 |
| FACTORY_BUILD / GKI_HACKS_FOR_DEBUG_CONFIG | 原厂均 n，候选定义缺失；Phase 4 找到官方定义 | 当前 OEM 版本的完整配置生成链 | 先准确记录 n 与 missing 的区别，审计定义依赖，保持关闭 | 现有公开定义可参考，精确当前版本仍缺 | 可以 | 不能只加空定义来消除配置差异；未证明是四 CRC 原因 |
| 精确 OEM 来源 | 公开 muyu 是 6.1.68，当前为 6.1.138 | 7b9e94 完整 SHA、manifest、补丁/工具链映射 | 获取当前发行版对应发布材料与构建输入 | 当前无法取得，不代表已证明私有 | 来源/哈希可以 | 无法声明 exact OEM rebuild，阻塞 |
| 全模块 ABI/运行语义 | 790 变体已比较；8138/8142 导出 CRC 同；部分核心 BTF 同 | 完整语义、内联差异、模块依赖/信任及运行证据 | 静态门槛闭合后再获批受控实验；运行阶段另行授权 | 关键功能依赖上列实现 | 静态部分可以；完整运行兼容不能 | 没有全兼容证明，维持 NOT_ACCEPTED |

【尚未验证】不能把未启用的两个配置定义差异强行归因于 CRC；同样不能把两个启用功能的存在直接归因于 CRC。需要真实 GENKSYMS 数据链才能建立因果关系。

## 6. 下一阶段决策与解除阻塞条件

**最终结论：BLOCKED，当前不建议新的完整 pristine GKI 实验构建。**

【已证实】Google GKI 6.1.138 仍是一个可固定、可复现的研究基准，签名信任问题已有不绕过保护的最小设计；这不等于已具备可收敛的完整 OEM 兼容路线。小米公开 muyu 6.1.68 也不能直接替换当前 6.1.138 基线。继续保留 Google 基准与小米参考资料，不替换 baseline。

解除阻塞需要以下可复核材料，而不是再一次编译成功：

1. 当前 OEM 版本的完整 MM 功能实现/补丁系列，尤其 Xiaomi dmabuf hugepage；至少有准确 Kconfig、依赖、构建对象和所有 MM hooks，并能解释当前原厂 BTF 的六参数 remap 与其他原型。
2. 能自然复现四个 CRC 的真实 OEM GENKSYMS 输入：准确源码/包含闭包，或 `.i` + `.symtypes` + 参考文件/选项与工具身份。若使用 `.symref`，必须有真实 OEM 来源与布局安全解释。
3. 在独立实验计划中完成原厂公钥嵌入链的 Linux 集成验证，并规定最终证书/保护表/模块集合验收。现有离线验签结果可复用，不需要重做已排除实验。
4. 前三项达到可审核状态后，再申请一次受控 pristine 实验构建；编译、上游 ABI/STG、原厂静态模块验收和运行验收分别记录，不相互替代。namespace/DroidSpaces 功能仍在范围外。

若 OEM 发布了完整材料，可重新评估为 FURTHER_EVIDENCE_REQUIRED 或 READY_FOR_PRISTINE_EXPERIMENT；当前只有未闭合的假设，不能把“仍可能”当作实验准入。

## 7. 证据与复核

本提交的 `evidence/phase5/` 包含源码快照及 Git blob SHA、检索范围/固定命中提交、原厂函数原型、组合信任测试、保护导出覆盖和输入清点；`SHA256SUMS` 固定全部新增证据及脚本/报告。源码分析对象为公开固定提交；社区线索单独标明，未冒充官方发布。

本地复核入口为 `muyu-gki-phase5/offline_checks.py`；仓库保存于 `scripts/phase5_offline_checks.py`。它默认读取该离线项目快照的 Phase 1/3/4 输入目录，依赖 Python cryptography；原始模块/boot 和大型 CI 产物不重新公开上传。复核者需要前阶段受控材料，所有输入身份及派生产物哈希可核对。该脚本只读既有输入并写派生报告，不编译内核，不访问设备。密码学模型未声称代替 Linux 模块加载器。

本阶段结束后停止，等待审核。
