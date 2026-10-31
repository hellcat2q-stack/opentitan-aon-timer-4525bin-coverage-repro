# 接手规则

请先读根目录 `README.md`、`docs/实验设计.md` 和 `docs/给下一个Codex的任务说明.md`。本仓库是基于 4000+ official functional bins 的全新实验，不能复用旧 379-bin 项目的实验结果。

## 每阶段流程

1. 按 01–10 顺序推进；先核对上一阶段的真实证据和服务器状态。
2. 每个新脚本登记在对应阶段 README 和 `实施记录.md`；通用工具放 `tools/`。
3. 阶段记录必须说明：做了什么、为什么、完整命令/输入/版本/seed/失败处理、文件位置、验收和局限。
4. 只有实际运行和复核通过后才写“完成”，并更新根 README。
5. 每完成一个阶段提交一次，提交信息包含阶段编号；中途失败也记录原因。

## 口径与安全

- 使用官方 OpenTitan UVM testbench、sequence、scoreboard 和 coverage；不得使用旧项目自定义 48-bin 或 379-bin 结果冒充本实验。
- 在阶段 04 冻结的新 manifest、采样条件、排除规则、实例展开和 schema 之前，不做正式覆盖比较。
- 任何源码、工具、build mode、coverage report 或 exclusion 变化都要提升 schema 或建立新实验 ID；不同 schema 的矩阵不混算。
- 原始 VDB、simv、许可证、SSH 密钥、token 和私有路径不得提交。
- 缺工具或许可时记录为阻碍，不编造 PASS、覆盖率或论文结论。
- 不删除或覆盖服务器既有项目；只在新的 `$HOME/opentitan_aon_timer_4525bin_repro` 下工作。
