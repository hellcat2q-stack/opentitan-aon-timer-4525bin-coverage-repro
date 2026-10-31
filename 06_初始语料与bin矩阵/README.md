# 阶段 06：初始语料与bin矩阵

**状态：已完成（2026-11-01）。** 17 个预注册官方候选均在学校服务器以 seed 42、coverage-enabled VCS 仿真通过，并从各自独立 VDB 导出 4,525 列 hit vector。初始语料并集命中 376 个 eligible bins（8.3094%）；这只是后续聚类和在线调度的冷启动数据，不是论文规模结论。

## 目标

运行预注册的初始测试和 seed，逐次提取最终冻结列的 hit vector，生成初始并集、频率和哈希。

## 为什么

为聚类和后续方法提供共同起点；不把 merged report 当作单次向量。

## 公开产物

- [`evidence/public_20261101_initial/matrix_summary.json`](evidence/public_20261101_initial/matrix_summary.json)：schema、运行顺序、成功/失败计数和每列向量哈希。
- [`evidence/public_20261101_initial/status.tsv`](evidence/public_20261101_initial/status.tsv)：17 个候选的最终 run、UTC 时间和返回码。
- [`evidence/public_20261101_initial/bin_by_run.tsv`](evidence/public_20261101_initial/bin_by_run.tsv)：4,525 行、17 个候选列；值为 0/1。
- [`evidence/public_20261101_initial/initial_union_and_frequency.tsv`](evidence/public_20261101_initial/initial_union_and_frequency.tsv)：每个 bin 的初始命中次数、并集标记和频率。
- [`evidence/public_20261101_initial/vectors/`](evidence/public_20261101_initial/vectors/)：每个候选的 URG/XML 派生向量、摘要和输入哈希。
- [`evidence/public_20261101_initial/initial_failures.tsv`](evidence/public_20261101_initial/initial_failures.tsv)：首次批处理暴露的旧版 VCS 配置兼容失败及修复记录。
- [`evidence/public_20261101_initial/verification.json`](evidence/public_20261101_initial/verification.json)：独立校验结果。

## 复核

从仓库根目录运行：

```powershell
python tools\verify_stage06_matrix.py `
  --stage "06_初始语料与bin矩阵\evidence\public_20261101_initial" `
  --output "06_初始语料与bin矩阵\evidence\public_20261101_initial\verification_rerun.json"
```

校验器不启动 VCS，只检查冻结 manifest 的 4,533 条记录、4,525 条 eligible bins、17 列、向量 bin 集合、矩阵与并集/频率的一致性以及向量哈希。

## 口径和局限

冻结 schema 是 `opentitan-aon-timer-functional-4525-v1`；4,533 条展开记录中 4,525 条参与实例计分，8 条 weight-zero 不进入矩阵分母。每个候选在独立源码副本中运行，保留 default 与 `cover_reg_top` 的原始 coverage-definition 分区；本阶段没有把不同分区的 merged VDB 当作单次向量。

论文中的 1,000 submissions、10 workers 和未披露的数值随机种子不由本阶段推断。这里的 seed 42 是本项目为可重复性固定的执行 seed；测试池来自锁定 revision 的官方 DV 配置，论文没有公开精确 job 名单。商业 VDB、simv、许可证和完整服务器日志仍只保留在服务器隔离目录，GitHub 只提交公开文本、XML 派生摘要、向量和哈希。
