# OpenTitan AON Timer 4525-bin 覆盖驱动复现

这是一个**独立于旧 379-bin 项目**的新复现仓库，目标是基于官方公开 AON Timer 报告对应的 OpenTitan revision `9f20940d494a223cc950a5b98f748fb28109d458`，重新建立 4000+ functional coverage bin 的可审计实验链路。

阶段 04 已基于服务器 run `20261031_08` 的真实 URG/XML 报告冻结静态字典：类型定义去重后 4,507 bins（46 命中），实例计分 4,525 bins（45 命中），其中 AON Timer 4,279、通用 testbench 246；展开记录含 8 个 weight-zero，共 4,533 条。单次 smoke 命中仅是链路验证，不是论文复现结果。

## 重要口径

- 本仓库冻结的 schema 为 `opentitan-aon-timer-functional-4525-v1`。
- 旧项目的 `69d820...`、379-bin manifest、279-bin 初始语料和 87.34% 随机结果不得混入本仓库。
- 类型定义口径为 4,507；启用 `instcov_for_score` 的实例计分分母为 4,525；AON Timer 自有范围是 4,279。CSV/URG total 行是汇总行，不能重复相加。
- 源码、coverage 配置、排除规则或工具版本变化时必须建立新 schema。
- 所有阶段先实际运行、再写 PASS；缺许可证、工具或原始报告时必须记录阻碍，不编造结果。

## 十步计划

| 步骤 | 目标 | 状态 | 交接入口 |
| --- | --- | --- | --- |
| 01 | 验收服务器、VCS/URG 或 Verisim/Vericov、许可证和隔离目录 | 已完成（2026-10-31） | [阶段 01](01_服务器环境与许可证/README.md) |
| 02 | 固定 revision `9f20940...`、DV 配置、依赖和工具版本 | 已完成（2026-10-31；远端 SHA 已核对） | [阶段 02](02_固定源码与依赖/README.md) |
| 03 | 编译并通过官方 AON Timer UVM coverage smoke | 已完成（2026-10-31；1/1 smoke、URG 报告通过） | [阶段 03](03_官方UVM覆盖编译/README.md) |
| 04 | 从真实报告冻结 4525-bin manifest、排除和解析契约 | 已完成（2026-10-31） | [阶段 04](04_4525-bin覆盖字典/README.md) |
| 05 | 盘点全部官方测试，确定作者池和初始语料计划 | 待开始 | [阶段 05](05_官方测试池与初始计划/README.md) |
| 06 | 运行初始语料，生成 4525 列 bin-by-run 矩阵 | 待开始 | [阶段 06](06_初始语料与bin矩阵/README.md) |
| 07 | 按 4000+ bin 规模建立聚类、信息量和 UCB 调度器 | 待开始 | [阶段 07](07_覆盖聚类与UCB调度/README.md) |
| 08 | 接入真实在线仿真，验证异步补位和覆盖反馈 | 待开始 | [阶段 08](08_VCS在线闭环/README.md) |
| 09 | 完成 Random、Full 和消融对照，预算和 seed 预注册 | 待开始 | [阶段 09](09_随机与方法对照/README.md) |
| 10 | 两端复核、最终报告、证据索引和 GitHub 交付 | 待开始 | [阶段 10](10_最终复核与交接/README.md) |

每个阶段必须有 README 和 `实施记录.md`，按“做了什么、为什么、怎么做、文件放哪里、验收、局限”记录。完成一个阶段后再提交和推送，交给用户检查后才进入下一阶段。

阶段 01 已在新的服务器隔离目录完成 VCS/URG P-2019.06-SP1、UVM 1.2、功能覆盖正/负对照和独立 Python 3.11.7 验收；[25 个脱敏证据文件](01_服务器环境与许可证/evidence/public_20261031_02/summary.json)已通过服务器和本机复核。阶段 02 已完成目标源码完整树核验、官方依赖离线安装、`pip check` 和 `dvsim.py --help` 导入探针；[阶段 02 证据](02_固定源码与依赖/evidence/public_20261031_01/dependencies_verified.json)记录了源码和依赖哈希。阶段 03 已完成官方 smoke、VCS coverage build、VDB merge 和 URG 报告；阶段 04 已冻结 [4,533 条 bin 记录](04_4525-bin覆盖字典/evidence/2026-10-31/run_20261031_08/coverage_manifest.v1.json)，分别保存 4,507 个类型定义与 4,525 个实例计分分母。能力探针的 4/4 与 3/4 不属于 AON Timer 的实验结果。

## 资料入口

- [4000-bin 资料说明](references/OpenTitan_AON_Timer_复现资料.md)
- [bin inventory 快照](references/OpenTitan_AON_Timer_bin_inventory.csv)
- [实验设计和不可混用规则](docs/实验设计.md)
- [给下一个 Codex 的交接文档](docs/给下一个Codex的任务说明.md)
- [GitHub 创建与推送](docs/GitHub创建与推送.md)
- [长期接手规则](AGENTS.md)

## 服务器隔离约定

真实 VCS/URG 数据、VDB、simv、许可证和原始大日志只放在学校服务器新建的专用目录，例如 `$HOME/opentitan_aon_timer_4525bin_repro`。GitHub 只提交可公开的脚本、配置、清单、脱敏文本证据和哈希索引；绝不提交私钥、token、许可证配置、商业 VDB 或二进制。


