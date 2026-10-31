# OpenTitan AON Timer 4525-bin 覆盖驱动复现

这是一个**独立于旧 379-bin 项目**的新复现仓库，目标是基于官方公开 AON Timer 报告对应的 OpenTitan revision `9f20940d494a223cc950a5b98f748fb28109d458`，重新建立 4000+ functional coverage bin 的可审计实验链路。

当前已知的用户提供资料显示：AON Timer 自有 4 个 covergroup 共 4,279 个预期 bins，通用 testbench 覆盖 246 个，官方报告总计 4,525 个 group bins，报告状态为 2,153/4,525。上述数字是**待阶段 01–04 重新现场核验的参考事实**，不把用户文件当作已完成的本地实验结果。

## 重要口径

- 本仓库的目标 schema 暂定为 `opentitan-aon-timer-functional-4525-v1`。
- 旧项目的 `69d820...`、379-bin manifest、279-bin 初始语料和 87.34% 随机结果不得混入本仓库。
- 4525 是公开报告的 group-bin 总数；AON Timer 自有范围是 4279。CSV 中的 total 行是汇总行，不能重复相加。
- 只有在重新获得同一源码 revision、coverage 配置、排除规则、工具版本和报告后，才能确认最终分母。
- 所有阶段先实际运行、再写 PASS；缺许可证、工具或原始报告时必须记录阻碍，不编造结果。

## 十步计划

| 步骤 | 目标 | 状态 | 交接入口 |
| --- | --- | --- | --- |
| 01 | 验收服务器、VCS/URG 或 Verisim/Vericov、许可证和隔离目录 | 待开始 | [阶段 01](01_服务器环境与许可证/README.md) |
| 02 | 固定 revision `9f20940...`、DV 配置、依赖和工具版本 | 待开始 | [阶段 02](02_固定源码与依赖/README.md) |
| 03 | 编译并通过官方 AON Timer UVM coverage smoke | 待开始 | [阶段 03](03_官方UVM覆盖编译/README.md) |
| 04 | 从真实报告冻结 4525-bin manifest、排除和解析契约 | 待开始 | [阶段 04](04_4525-bin覆盖字典/README.md) |
| 05 | 盘点全部官方测试，确定作者池和初始语料计划 | 待开始 | [阶段 05](05_官方测试池与初始计划/README.md) |
| 06 | 运行初始语料，生成 4525 列 bin-by-run 矩阵 | 待开始 | [阶段 06](06_初始语料与bin矩阵/README.md) |
| 07 | 按 4000+ bin 规模建立聚类、信息量和 UCB 调度器 | 待开始 | [阶段 07](07_覆盖聚类与UCB调度/README.md) |
| 08 | 接入真实在线仿真，验证异步补位和覆盖反馈 | 待开始 | [阶段 08](08_VCS在线闭环/README.md) |
| 09 | 完成 Random、Full 和消融对照，预算和 seed 预注册 | 待开始 | [阶段 09](09_随机与方法对照/README.md) |
| 10 | 两端复核、最终报告、证据索引和 GitHub 交付 | 待开始 | [阶段 10](10_最终复核与交接/README.md) |

每个阶段必须有 README 和 `实施记录.md`，按“做了什么、为什么、怎么做、文件放哪里、验收、局限”记录。完成一个阶段后再提交和推送，交给用户检查后才进入下一阶段。

## 资料入口

- [4000-bin 资料说明](references/OpenTitan_AON_Timer_复现资料.md)
- [bin inventory 快照](references/OpenTitan_AON_Timer_bin_inventory.csv)
- [实验设计和不可混用规则](docs/实验设计.md)
- [给下一个 Codex 的交接文档](docs/给下一个Codex的任务说明.md)`n- [GitHub 创建与推送](docs/GitHub创建与推送.md)
- [长期接手规则](AGENTS.md)

## 服务器隔离约定

真实 VCS/URG 数据、VDB、simv、许可证和原始大日志只放在学校服务器新建的专用目录，例如 `$HOME/opentitan_aon_timer_4525bin_repro`。GitHub 只提交可公开的脚本、配置、清单、脱敏文本证据和哈希索引；绝不提交私钥、token、许可证配置、商业 VDB 或二进制。


