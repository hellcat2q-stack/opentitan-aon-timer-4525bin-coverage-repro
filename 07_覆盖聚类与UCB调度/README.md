# 阶段 07：覆盖聚类与UCB调度

**状态：已完成（2026-11-01，已修正回放器）。** 阶段 07 使用阶段 04 的 4,525-bin manifest 和阶段 06 的 4,525×17 矩阵，构建 184 个确定性、组件/covergroup/coverpoint 分区的聚类，并计算初始静态信息权重。另生成 32 submission、3 workers 的 replay-only dry-run 事件链；该 dry-run 未启动 VCS。

## 目标

按论文和冻结 schema 建立 bin 特征、聚类、信息权重、双层 UCB、runtime penalty 和可审计事件日志。

## 为什么

所有算法输入必须来自新 schema，禁止混入旧 379-bin clusters。

## 公开产物

- [`evidence/public_20261101_stage07/clusters/`](evidence/public_20261101_stage07/clusters/)：特征、聚类映射和抽样复核记录。
- [`evidence/public_20261101_stage07/scores/`](evidence/public_20261101_stage07/scores/)：184 个 cluster 的静态/动态初始分数和 scheduler 输入。
- [`evidence/public_20261101_stage07/dryrun/`](evidence/public_20261101_stage07/dryrun/)：只回放阶段 06 向量的 UCB 事件链、摘要和链哈希。
- [`evidence/public_20261101_stage07/verification.json`](evidence/public_20261101_stage07/verification.json)：独立离线校验结果。
- [`evidence/public_20261101_stage07/SHA256SUMS`](evidence/public_20261101_stage07/SHA256SUMS)：公开产物哈希索引。

## 复核

从仓库根目录运行：

```powershell
python tools\verify_stage07.py `
  --stage "07_覆盖聚类与UCB调度\evidence\public_20261101_stage07" `
  --manifest "06_初始语料与bin矩阵\evidence\public_20261101_initial\coverage_manifest.v1.json" `
  --matrix "06_初始语料与bin矩阵\evidence\public_20261101_initial\bin_by_run.tsv" `
  --output "07_覆盖聚类与UCB调度\evidence\public_20261101_stage07\verification_rerun.json"
```

校验器不启动仿真，检查 manifest/bin 集合、聚类唯一归属、cluster 分数维度、scheduler 输入以及事件链的逐事件 SHA-256。

## 口径和局限

聚类特征来自冻结 manifest 的 source file、scope、covergroup、coverpoint/cross、bin 文本和数值字面量；先按 component + covergroup base + coverpoint/cross 分区，再执行 Jaccard-token DBSCAN，最大 cluster size 为 32。参数和噪声规则写入 `clusters.json`。

初始覆盖为 376/4,525。UCB dry-run 的 32 次 submission 只是把已完成的 17 个向量作为确定性反馈回放，故最终仍为 376 bins、没有新的 VCS run；当前回放按虚拟完成时间处理异步 worker，直到 32/32 提交均完成，且序列奖励只使用相对当前覆盖状态的新命中。虚拟 elapsed 为 1,553 秒，是阶段 06 墙钟区间的回放代理，不是新的 VCS runtime。该 dry-run 验证调度状态、冷启动、目标 cluster、sequence 选择、runtime penalty 和事件链格式，不构成阶段 08 的在线闭环结果。184 个 cluster 和参数是本项目在新 schema 上的工程选择，不声称等同论文作者未公开的实现。
