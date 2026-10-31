# 阶段 01：服务器环境与许可证

**状态：已完成（2026-10-31）。** 学校服务器上的 VCS/UVM/功能覆盖/URG 与独立 Python 基础链路已实测通过；这不是官方 AON Timer UVM smoke，也没有确认 4525/4279 分母。

## 验收结果

| 检查 | 实测结果 | 证据 |
| --- | --- | --- |
| SSH、身份与目录 | 登录成功；仅在新 `$HOME/opentitan_aon_timer_4525bin_repro` 下写入 | [实施记录](实施记录.md) |
| 操作系统和资源 | RHEL 7.9、glibc 2.17、80 逻辑 CPU、约 503 GiB 总内存；共享资源，不代表已预留 | [environment.json](evidence/public_20261031_02/environment.json) |
| VCS / URG / UVM | P-2019.06-SP1 / P-2019.06-SP1 / UVM 1.2 | [构建](evidence/public_20261031_02/build.log)、[运行](evidence/public_20261031_02/full.log) |
| 工具与许可证实际可用性 | 编译、两次仿真、测试列表查询和两次报告导出均返回 0 | [return_codes.tsv](evidence/public_20261031_02/return_codes.tsv) |
| 完整采样探针 | 4/4 个自定义能力测试 bins，100%；UVM_ERROR/FATAL 均为 0 | [完整报告](evidence/public_20261031_02/full_dashboard.txt) |
| 少采样负对照 | 3/4 个相同 bins，75%；证明单次报告筛选和未命中识别有效 | [负对照报告](evidence/public_20261031_02/partial_dashboard.txt) |
| Python | 独立 Python 3.11.7 / venv；系统 Python 3.6.8 保持原样 | [环境清单](evidence/public_20261031_02/environment.json) |
| Python 依赖 | 17 个分析/配置处理包已锁定；导入、数值运算、DBSCAN 与 `pip check` 通过 | [依赖锁](requirements-stage01.lock.txt)、[pip check](evidence/public_20261031_02/pip_check.txt) |
| 两端证据复核 | 服务器和本机都验证 25 个证据文件及脚本输入哈希，独立重算 4/4 和 3/4 | [summary.json](evidence/public_20261031_02/summary.json)、[SHA256SUMS](evidence/public_20261031_02/SHA256SUMS) |

最终验收运行 ID：`20261031_02`。单 worker；探针 seed 为 42，仅为本次工具测试选择，不声称是论文作者的 seed。最终验收运行了 2 次仿真；包含保留的首次失败报告尝试，共运行 4 次小型探针仿真。

## 文件登记

| 文件 | 用途 |
| --- | --- |
| [capability_probe.sv](capability_probe.sv) | 最小 UVM 功能覆盖探针及少采样对照，明确排除在正式实验外 |
| [run_capability_probe.sh](run_capability_probe.sh) | 新目录编译、仿真、查询 URG 逻辑测试名和逐次导出报告；有超时和返回码记录 |
| [bootstrap_python.sh](bootstrap_python.sh) | 校验安装包与 wheels，独立 venv 离线安装，不改系统 Python |
| [inspect_environment.py](inspect_environment.py) | 脱敏环境清单、依赖导入及基础功能检查 |
| [verify_stage01.py](verify_stage01.py) | 采集公开证据，核对工具返回码、UVM 错误数、分子/分母和文件哈希 |
| [requirements-stage01.txt](requirements-stage01.txt) | Python 3.11 / glibc 2.17 基础分析环境的直接依赖 |
| [requirements-stage01.lock.txt](requirements-stage01.lock.txt) | 实际安装的完整依赖版本；阶段 02 另行核对 OpenTitan 依赖 |
| [实施记录.md](实施记录.md) | 实际命令、输入、失败处理、证据位置、验收与局限 |

## 快速复核

本机在仓库根目录运行（Python 3.10+）：

```powershell
python "01_服务器环境与许可证/verify_stage01.py" --bundle "01_服务器环境与许可证/evidence/public_20261031_02"
```

预期输出 `verification: PASS`、`files_verified: 25`，完整/负对照分别为 `4/4` 和 `3/4`。验证不连接服务器、不运行仿真，也不改证据。

## 局限与下一步

- 只验证一个并行 worker 的实时许可可用性，没有证明 10 个并行 worker 的许可证容量或排队规则。
- 未编译官方 AON Timer；未下载/固定目标源码；4525/4279 仍是待核验参考值。
- 新探针的 4 个 bins 只是工具能力测试，严禁进入阶段 04/06 的 manifest 或实验矩阵。
- 服务器访问 Python 包索引时 DNS 失败，本次使用本机下载、哈希校验、上传后的离线 wheels。
- VCS 2019 与目标 OpenTitan revision 的兼容性、所需编译器及完整 DV 依赖留待阶段 02–03 现场验证。
- 阶段 01 完成后停在这里，等待用户检查再进入阶段 02。
