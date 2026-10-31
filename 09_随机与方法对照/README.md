# 阶段 09：随机与方法对照

**状态：已完成预注册；正式对照未执行（2026-11-01）。** 本阶段冻结了六种对照方法、预算、seed、失败分母和验收闸门；没有把预注册写成 VCS 结果。

## 目标

预注册 Random、Full、Sequence/Cluster 消融、预算、worker、seed、初始覆盖和统计口径；在 seed handoff 与多 worker 许可验收后运行正式对照实验。

## 为什么

随机基线要明确有放回/无放回和最终覆盖分子分母，不能只报一个百分比。

## 已冻结的实验口径

- 6 个方法：Full、No Incremental Refill、No Runtime Penalty、Random Selection、Sequence UCB Only、Cluster UCB Only。
- 共同预算：1000 次总提交，包含 17 次共同初始语料；之后 983 次自适应提交；100 个逻辑批次，每批 10 次；目标 10 workers；根 seed 42。
- Random 使用 17 个官方候选 job 的有放回均匀抽样。失败尝试保留在 submitted 分母，不能产生 coverage hit；重试关闭。
- 覆盖主分母为 4,525 个 eligible instance bins，同时报告 AON Timer 4,279-bin 子集；阶段 06 的 376 个初始命中只作为共同初始状态，不作为阶段 09 的自适应结果。
- Full 的静态/动态参数按论文表 I 固定；其余方法只移除 README 中列出的单个调度组件。

机器可读预注册见 [`preregistration.v1.json`](preregistration.v1.json)，独立校验见 [`evidence/public_20261101_stage09/verification.json`](evidence/public_20261101_stage09/verification.json)。

## 执行状态

正式 VCS 对照尚未开始。阶段 08 只验证了固定项目 seed 42 的一个在线 smoke，scheduler 派生 seed 尚未传入 VCS wrapper；当前也只验收过单 worker。校验器会在输入 hash、seed handoff、worker 行为和新服务器 run ID 满足前拒绝把任何目录标为正式结果。

## 最低交付物

- README.md：阶段目标、真实状态、复核入口和局限。
- 实施记录.md：按“做了什么、为什么、怎么做、文件放哪里、验收、局限”记录实际过程。
- 机器可读配置/清单/哈希，以及可公开的脱敏证据。

## 不得提前声称

不能把计划命令写成已执行；不能把用户提供的 4525/4279 参考数直接写成现场验收结论；不能引用旧 379-bin 项目的结果替代本阶段产物。

## 复核命令

从仓库根目录运行：

```powershell
python tools\verify_stage09_prereg.py `
  --repo . `
  --prereg "09_随机与方法对照\preregistration.v1.json" `
  --output "09_随机与方法对照\evidence\public_20261101_stage09\verification_rerun.json"
```

该命令只校验预注册和冻结输入哈希，不启动仿真。

## 下一步

先完成 seed handoff smoke 与 10-worker 许可/队列检查，再执行六种方法的正式对照；在此之前不得报告阶段 09 覆盖率或论文曲线。
