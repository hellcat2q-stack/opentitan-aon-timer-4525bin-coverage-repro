# 阶段 08：VCS在线闭环

**状态：已完成（2026-11-01，小预算真实链路 smoke）。** 阶段 07 首个策略选择 `aon_timer_sec_cm`，阶段 08 已在两个新服务器 run（`20261101_online_01_aon_timer_sec_cm`、`20261101_online_02_aon_timer_sec_cm`）中真实执行 VCS build/run/coverage merge/URG，并导出 4,525 列反馈向量；两次返回码均为 0，各命中 11 bins。第二次 run 与修正后的阶段 07 调度器严格对应。该 smoke 验证真实反馈落盘和 schema 对齐，不是论文规模在线实验。

## 目标

把调度器接到真实官方仿真，验证 seed/test 传递、异步完成、覆盖反馈、失败隔离和补位。

## 为什么

先做小预算真实链路，再扩大预算；每次任务独立保存原始证据。

## 公开产物

- [`online_job.v1.json`](online_job.v1.json) 和 [`online_job_02.v1.json`](online_job_02.v1.json)：两次 scheduler job 到真实 VCS run 的映射。
- [`evidence/public_20261101_online_01/`](evidence/public_20261101_online_01/) 和 [`evidence/public_20261101_online_02/`](evidence/public_20261101_online_02/)：两次 run 的返回码、状态、4,525 列公开反馈向量、摘要、校验和及独立验证结果。
- [`run_online_smoke.sh`](run_online_smoke.sh)：服务器在线 smoke 入口，复用阶段 06 的 per-run 源码副本和提取器。

## 复核

从仓库根目录运行（第二次真实 run）：

```powershell
python tools\verify_stage08.py `
  --stage "08_VCS在线闭环\evidence\public_20261101_online_02" `
  --output "08_VCS在线闭环\evidence\public_20261101_online_02\verification_rerun.json"
```

校验器不启动仿真，检查真实 run 返回码、job/test/seed 元数据、manifest schema、4,525 列向量和哈希。

## 口径和局限

真实服务器 run 使用 VCS/URG P-2019.06-SP1、coverage mode、单 worker、项目固定 seed 42 和阶段 06 的 VCS 2019 compatibility patch。scheduler 派生的 `341807780` 被保留在 job 元数据中，但本次 compatibility smoke 没有把它替换项目固定 seed；校验结果明确记录 `scheduler_stimulus_seed_applied=false`。

本阶段只执行两个单 worker 真实在线 smoke，不宣称异步多 worker、失败补位、预算曲线或论文 1,000 submissions 已复现。两次 run 都使用固定项目 seed 42，因此第二次向量与第一次相同；scheduler 派生 seed 仍只保存在元数据中。商业 VDB、simv、许可证和完整日志仍只在服务器隔离目录；公开目录只保存 URG/XML 派生向量和脱敏元数据。
