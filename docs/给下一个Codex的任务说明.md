# 给下一个 Codex 的任务说明

你将接手一个全新的 OpenTitan AON Timer 4000+ functional-bin 复现项目：

- 仓库：`opentitan-aon-timer-4525bin-coverage-repro`
- 目标 revision：`9f20940d494a223cc950a5b98f748fb28109d458`
- 参考官方报告：总 group bins 4525，AON Timer 自有 4279；这些数字必须重新核验。
- 旧项目 `opentitan-aon-timer-vcs-official-coverage-repro` 的 379-bin 结果不可复用为本实验数据。

## 必须先做

1. 阅读 `AGENTS.md`、根 `README.md`、`docs/实验设计.md` 和本文件。
2. 阅读 `references/OpenTitan_AON_Timer_复现资料.md` 与 CSV，识别其中哪些是用户提供的参考事实、哪些仍需验证。
3. 检查当前 Git 提交、远端和服务器是否已有本项目目录；不得碰旧项目目录。
4. 从阶段 01 开始，严格按 01–10 顺序推进。

## 每阶段交付标准

每完成一个阶段，必须：

- 写对应阶段 `README.md` 和 `实施记录.md`；
- 记录实际命令、版本、seed、输入、输出、失败和兼容处理；
- 保存公开可审计的清单/哈希/脱敏文本证据；
- 运行必要的验收脚本；
- 更新根 README 状态；
- 提交阶段变更并推送 GitHub；
- 停下等待用户检查，不自动跳到下一阶段。

## 第一个 Codex 窗口的边界

本窗口只负责建立仓库骨架和交接文件，不声称阶段 01–10 已完成。下一个窗口负责现场验证和真实实验。若没有服务器许可证、coverage 工具或作者输入，必须写清阻碍，不能用 379-bin 数据填补。

## 建议的第一步

完成阶段 01：在服务器新建隔离目录，记录 `whoami`、主机、VCS/URG 或 Verisim/Vericov 版本、许可证状态、Python 依赖和最小 UVM/coverage smoke 能力；不要开始正式大规模仿真。
