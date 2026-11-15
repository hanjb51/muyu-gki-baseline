from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[1]
lock=json.loads((ROOT/'source-lock/LOCK.json').read_text('utf-8'))
stats=json.loads((ROOT/'evidence/input-summary.json').read_text('utf-8'))
table='\n'.join('| '+p['path']+' | `'+p['commit']+'` | 待 CI 从主站同步后计算 |' for p in lock['sources'])
report=f'''# BASELINE_REPORT.md

日期：2026-11-15（北京时间）  
阶段：第三阶段 A/B 已完成可执行准备；C 基线编译尚未启动；D 不予验收通过。  
结论：**目前不允许进入 Droidspaces 功能编译。没有编译成功或设备兼容性的结论。**

## 1. 源码是否精确匹配

未精确匹配小米原厂提交 `7b9e94e37cfa`。已查询公开提交、AOSP 两套镜像和 MiCode muyu 分支线索；MiCode 当前搜索只返回 muyu-v-oss，公开头提交为 681e88870888dec258dd48b0ab8c908b303eb159，源码仍为旧 6.1.68，不将其作为当前运行内核的精确源码。没有找到不等于证明源码不存在。

本轮新找到设备 system_dlkm 中 Google 配套 GKI 模块对应的完整源码提交：

`0c3d559bcd85c64dae9c9c9687abbe5347fff3ad`

该源码 Makefile 为 6.1.138，KMI_GENERATION=11；它位于历史 common-android14-6.1-2025-06 superproject 中。选择它作为 **June / 6.1.138 的原厂配套候选**，而不是选择今天浮动分支的最新 HEAD。它与设备上保留的一套 Google GKI 模块源码身份匹配，**不等于**与小米运行的 `g7b9e94e37cfa-mi` 完全相同。

本轮不使用 2025-07 / 6.1.141，不引入第三方内核、调度器、温控、GPU、Root 或隐藏补丁。

来源：
- https://github.com/aosp-mirror-neo/kernel_common/commit/0c3d559bcd85c64dae9c9c9687abbe5347fff3ad
- https://github.com/aosp-mirror-neo/kernel_superproject/tree/c5fd854d46f3fe29b89a80e5f2cf3bc643c64f20
- https://github.com/aosp-mirror-neo/kernel_manifest/blob/848f8dbd7fc7c40a884b614ad29f5d89199ddaff/default.xml
- https://github.com/MiCode/Xiaomi_Kernel_OpenSource/tree/muyu-v-oss

## 2. 完整 manifest、Kleaf、Bazel 与 Clang 锁定

历史 manifest 提交：`{lock['manifest_origin_commit']}`。  
历史 superproject 提交：`{lock['superproject_commit']}`。  
本地冻结 manifest SHA256：`{lock['manifest_sha256']}`。

原 manifest 和 superproject 的 .gitmodules/.supermanifest/gitlink 逐项对应，共 20 个项目，无遗漏或未解释 gitlink。生成 source-lock/manifest.xml，为每个 project 写入完整提交；保留原有 linkfile，remote 改为明确的 `https://android.googlesource.com/`。CI 从主站按这些对象同步，任何对象不可取得就失败，不自动回退到 main、HEAD、更新工具链或其他内核版本。

| 项目路径 | 固定 Git commit | 源码归档 SHA256 |
|---|---|---|
{table}

Kleaf/build 已固定为 06f7c2ac33c6d9927613bafd95def11d18924f5e。Clang 明确使用 r487747c，由其 prebuilts 项目提交固定；不能替换为宿主 clang。Bazel 使用固定 prebuilts 仓库中的二进制，而非下载最新版。

**重要边界：**本地执行环境无法连接 Git 主站，尚未完成 20 个项目的完整 checkout，因此它们的实际源码归档 SHA256、Clang/LLD/Bazel 二进制 SHA256 和 Bazel 运行版本仍未验证。Git commit 锁定不冒充 SHA256 已测量。`verify_sources.py` 将在 CI 同步后逐项目校验 HEAD、无 tracked 改动、Git tree 和 `git archive HEAD` 的 SHA256，并计算三种实际工具二进制的 SHA256。锁定的历史 Clang 对象暂未能通过当前 GitHub 镜像读取；必须在 CI 用主站验证可取得性。

Repo 工具固定提交 `{lock['repo_tool_commit']}`，随包 launcher SHA256 `{lock['repo_launcher_sha256']}`。Actions checkout/upload-artifact 均固定完整提交，runner 固定 ubuntu-22.04。

## 3. 官方 SYSVIPC kABI 补丁验证

仍使用官方 below-6.12 的 6/7/8 补丁，SHA256：`{lock['sysvipc_patch_sha256']}`。

已对本轮候选 `0c3d559...` 的 include/linux/sched.h 快照执行 git apply --check，通过；hunk 分别位于 1096 和 1551。日志保存 evidence/sysvipc-check-only.log。

当前本地仅具备补丁涉及文件的快照，不能把它称为完整源码树检查。CI 将在完整且已验证为原始提交的 common 上再执行一次 git apply --check。**本次基线不应用补丁、不添加容器配置。**

## 4. 独立工作流修复情况

工作目录：muyu-gki-phase3；准备的远程分支：`baseline/muyu-gki`；准备的专用 Fork 名称：`muyu-gki-baseline`。没有修改 Xieansecn、Droidspaces、MiCode 或 AOSP 上游仓库，也没有借用账号中无关仓库承载此项目。

| 要求 | 实现与验证 |
|---|---|
| 保留 protected exports | 固定并校验原列表、protected_modules 和 BUILD.bazel；没有删除分支动作 |
| 保留 MODVERSIONS、ThinLTO、CFI、4KB 页 | 最终配置强制检查，ThinLTO 通过 --lto=thin 指定 |
| 保留 kABI 预留、签名保护和符号裁剪 | 最终配置要求 ANDROID_KABI_RESERVE、MODULE_SIG/ALL/PROTECT、TRIM_UNUSED_KSYMS 为 y |
| 保留上游 ABI 检查 | 使用 pinned Kleaf 的 kernel_aarch64_abi_dist；该目标复制产物后执行 enforced STG diff 并返回其退出码 |
| 不更改 ABI 参考以掩盖失败 | 不运行 ABI update/update_definition/update_symbol_list/update_protected_exports 目标 |
| 正确 GKI defconfig | 基线使用候选原始 arch/arm64/configs/gki_defconfig，不引入 fragment，不复制整份旧设备 config 替换它 |
| 检查真正 .config | 从产物 Image 用该源码的 extract-ikconfig 提取；逐项比较原厂完整 config |
| 保留失败证据 | pipefail、原始 Bazel 退出码、完整主构建日志、always 归档与报告生成 |
| 模块检查范围 | 全部 790 份变体，汇总全部 508 个名称，标出 504 个已加载名称 |
| 禁止自动进入功能编译 | allow_droidspaces_features 始终 false，须用户审核及未解门槛处理 |

静态输入预检查：候选 defconfig 的 **775 个显式配置项全部与原厂最终 config 对应值相同**。这只是 defconfig 文本与原厂配置的比较，不是候选编译后 .config 已相同；Kconfig 默认/依赖及编译器影响仍须实测。

没有添加 CONFIG_CFS_BANDWIDTH、CONFIG_CGROUP_PIDS 或其他 Droidspaces 增量，也没有为了通过编译改调度、温控或 GPU。

## 5. 原厂模块分类和离线检查

输入直接复用已有采集文件，没有访问设备或重复采集。保留所有路径与 SHA256，不将同名模块当成相同二进制。

| 类别 | 文件变体 | 候选源码名单含义 |
|---|---:|---|
| Vendor 来源（vendor_dlkm + vendor_boot） | 670 | 450 个去重名称；与 GKI 有 2 个同名项 |
| GKI、在 protected module 名单中 | 114 | 57 个名称 × Google/小米两套；只是源策略分类 |
| GKI、不在 protected 名单中 | 6 | kheaders、zram、zsmalloc 的两套文件 |
| 全部 | 790 | 508 个唯一名称；504 已加载，4 未加载 |

实际的 Protected GKI 签名信任仍未验证。签名存在、目录属于 system_dlkm、命中源名单，都不能单独证明新内核会信任原厂签名。

新增离线证据：从所有模块 ELF 解出 6300 个导出记录，CRC 均成功解码；依赖引用未发现未采集名称。对 5181 个有已采集模块提供者的导入引用进行 CRC 对照，没有冲突；Vendor 导出没有撞上本轮候选的 protected exports 名单。

这些是**原厂模块的离线一致性**，不是与已构建候选内核的兼容性验证。完整 790 份 CRC/导出账本在 inputs/stock-modules.json；508 名称分类在 inputs/module-classification-508.json。当前 candidate_crc_status 为 NOT_BUILT，没有伪造 Module.symvers 或把原厂模块之间的 CRC 一致当作验收通过。

编译后检查器会对每个变体比较实际 Module.symvers，区分内核/GKI 提供的导出和原厂 Vendor 提供的导出；校验 CRC、缺失符号、namespace、GPL-only 限制和 protected export 冲突。无法解析的要求或未证实信任不默认为通过。输出逐变体和逐名称结果。

## 6. 第一轮编译是否成功

**尚未启动，因此没有编译成功、失败的内核构建结论，也没有 Image/vmlinux/System.map/Module.symvers/最终 .config/STG 构建产物。**本地 Python 测试和 YAML 检查不是内核编译。

实际阻塞：

1. 当前 GitHub 连接身份为 hanjb51，但未发现本任务的专用 Fork；连接没有暴露创建仓库/Fork 或启动新 workflow run 的操作。
2. 本执行环境 gh auth status 返回未登录；Git 访问 android.googlesource.com 失败，报 getaddrinfo() thread failed to start。
3. 已检查浏览器回退能力；当前没有可用的关联 Browser 执行入口，不能假装已通过浏览器建立 Fork。

没有为了绕过这些限制向账号无关仓库写入工作流，也没有声称有 Actions run ID 或编译日志。使用现有用户终端完成 GitHub 登录/创建专用 Fork 并推送独立分支后，工作流才会真正启动。

所有必要文件已准备好：在正常 Windows PowerShell 执行：

```powershell
powershell -NoProfile -File "E:\\CodexData\\.chatgpt-projects\\g-p-6acee86eea808191b453a50c0698d3be\\muyu-gki-phase3\\Start-Baseline.ps1"
```

该脚本不是设备采集脚本。它只进行 GitHub 登录（如需要）、创建/核对本人专用 Fork、启用该 Fork 的 Actions、上传已准备的代码/配置/模块元数据并推送 baseline/muyu-gki，push 事件触发基线编译。没有 ADB、刷机、重启或分区写入。若账号缺少 workflow 写入权限，会保留错误，不使用其他仓库或凭据。

CI 完成后应归档：完整 source-verification.json 和 manifest、工具版本/哈希、Image、vmlinux、System.map、Module.symvers、最终 .config、config diff、ABI/STG diff、790/508 项核查结果、SHA256SUMS、主构建日志和自动生成的 BASELINE_REPORT.md。失败同样保留原退出码和已有日志。

## 7. 本地验证与未验证项

已通过：20 个 manifest project 完整固定及 manifest SHA256、YAML/分支隔离/只读 workflow 权限检查、PowerShell 语法检查、Python 语法检查、6 项 CRC/namespace/protected collision/外部模块提供者/配置缺失边界回归检查、775 个显式配置匹配、候选 sched.h 补丁上下文检查、原厂模块提供者/依赖核查。

未完成：Linux Bash/真实 GitHub Actions 端到端执行。尝试在本地 Git Bash 做 bash -n 时，MSYS 在 NtCreateDirectoryObject 报 0xC0000022，故不声称 shell 语法已在此环境检查通过。Clang/Bazel 实际运行、完整源码 checkout、源码归档哈希、最终 config、ABI/STG 和候选导出 CRC 均待真正 CI。

## 8. 基线验收与后续决策

| 验收项 | 当前结果 |
|---|---|
| 源码精确对应原厂 | 否，仅锁定配套 Google 候选 |
| 依赖版本锁定 | 20 个 Git 提交已固定，实际同步与源码 SHA256 待 CI |
| 第一轮编译成功 | 未执行 |
| 最终配置符合原厂 | 未验证 |
| ABI/KMI、结构体和候选符号 CRC | 未验证 |
| 全部 Vendor 模块兼容 | 未验证 |
| 原厂 GKI 模块签名信任 | 未验证 |
| 允许进入 Droidspaces 功能编译 | **不允许** |

必须取得真实编译产物及核查结果后，更新本报告供用户审核。即便编译成功、AOSP STG 和导入 CRC 全部通过，仍需解释配置差异、OEM 私有源码缺口和原厂 Protected GKI 的可信证书关系；不能删除保护或更换模块来冒充“保持原厂兼容”。

本轮没有执行设备访问、刷写、重启、切槽或 boot/init_boot/vendor_boot/vbmeta 修改。没有触发 Droidspaces 功能编译。
'''
(ROOT/'BASELINE_REPORT.md').write_text(report,encoding='utf-8')
print('BASELINE_REPORT.md written; compilation status remains NOT_STARTED.')
