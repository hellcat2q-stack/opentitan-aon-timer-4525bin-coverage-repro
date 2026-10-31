# 阶段 03：官方UVM覆盖编译

**状态：已完成（2026-10-31）。** 官方 AON Timer UVM smoke 已在学校服务器上完成 coverage build、VCS 仿真、coverage merge 和 URG 报告导出。最终运行 ID 为 `20261031_08`。

## 目标

用官方 AON Timer UVM testbench、sequence、scoreboard 编译 coverage build，完成单条 smoke 和重复回放。

## 为什么

确认覆盖采样真正打开，PASS 不等于 coverage 有效。

## 实测结果

| 检查 | 结果 | 公开证据 |
| --- | --- | --- |
| 源码副本 | revision `9f20940...`；Git tree `4229b5d...`；10,514 文件 | [source_copy_verification.json](evidence/public_20261031_02/source_copy_verification.json) |
| Build / run / merge / report | 四个 DVSim 阶段均 `1 passed / 0 failed / 1 total` | [phase_status.tsv](evidence/public_20261031_02/phase_status.tsv) |
| 官方 smoke | `aon_timer_smoke`，sequence `aon_timer_smoke_vseq`，fixed seed 42；1/1 通过 | [run_summary.json](evidence/public_20261031_02/run_summary.json) |
| UVM 严重度 | `UVM_ERROR=0`，`UVM_FATAL=0` | [uvm_status.tsv](evidence/public_20261031_02/uvm_status.tsv) |
| URG | 1 个测试；报告共 16 个 group 条目、4,525 个 group bins；识别到 4 个 AON Timer covergroups | [groups.txt](evidence/public_20261031_02/groups.txt)、[aon_timer_covergroups.txt](evidence/public_20261031_02/aon_timer_covergroups.txt) |
| smoke coverage | 45/4,525 group bins，group score 0.99%；这是单次 smoke 结果，不是最终实验结论 | [urg_report_summary.txt](evidence/public_20261031_02/urg_report_summary.txt) |

本阶段只确认官方模型能够编译、运行并写出 coverage 数据库和 URG 报告；没有冻结阶段 04 的 bin manifest、排除规则或最终分母。

## 最低交付物

- README.md：阶段目标、真实状态、复核入口和局限。
- 实施记录.md：按“做了什么、为什么、怎么做、文件放哪里、验收、局限”记录实际过程。
- 机器可读配置/清单/哈希，以及可公开的脱敏证据。

## 不得提前声称

不能把计划命令写成已执行；不能把用户提供的 4525/4279 参考数直接写成现场验收结论；不能引用旧 379-bin 项目的结果替代本阶段产物。

## 实际运行

服务器 wrapper 为 [`run_official_smoke.sh`](run_official_smoke.sh)。它为每个 run 复制锁定源码，验证完整 Git tree，加入阶段 02 的 FuseSoC venv，执行 `dvsim.py` 的官方 `aon_timer_smoke`，并把原始 VDB/simv/HTML 报告留在服务器专用目录。GitHub 只保存脱敏文本、哈希和摘要。

VCS P-2019.06-SP1 不接受目标 revision 的三个较新配置写法。wrapper 只在每次运行的临时源码副本中做兼容处理：去掉不支持的 `-cm_common_hier`，去掉性能优化用的 `-xprop=mmsopt`，并把两个层次覆盖配置按旧版 VCS 要求合并为一个文件。补丁前后 SHA-256 和原因见 [compatibility_patch.txt](evidence/public_20261031_02/compatibility_patch.txt)；锁定归档没有修改。

本机可复核公开证据（Python 3.10+）：

```powershell
python "03_官方UVM覆盖编译/verify_stage03.py" `
  --bundle "03_官方UVM覆盖编译/evidence/public_20261031_02"
```

证据 SHA-256 按 LF 行尾计算；校验器会在 Windows checkout 上先把 CRLF 归一化，避免 Git 行尾转换导致校验差异。`groups.txt` 保留 URG 的覆盖结果与条目，只去掉对解析无影响的行尾填充空格。

## 下一步

阶段 04：在真实 URG 报告基础上冻结 4525-bin manifest、AON Timer 4279-bin 子集、排除规则和解析契约；完成后提交并停止等待检查。
