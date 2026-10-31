# 阶段 05：官方测试池与初始计划

**状态：已完成（2026-11-01）。** 已在目标 revision 的干净源码归档上盘点官方 AON Timer/CIP 测试模板、sequence、coverage mode、build mode 和 run options，生成 17 个候选 job 及固定 17-run 初始语料计划。阶段 06 尚未执行。

## 目标

盘点全部官方 test job、sequence、plusargs、build mode、reseed 和 coverage gate，标记作者候选池并注册初始语料方案。

## 为什么

测试池影响命中概率；不能把旧项目 8 个测试直接当作新实验池。

## 最低交付物

- README.md：阶段目标、真实状态、复核入口和局限。
- 实施记录.md：按“做了什么、为什么、怎么做、文件放哪里、验收、局限”记录实际过程。
- 机器可读配置/清单/哈希，以及可公开的脱敏证据。

## 验收结果

- 候选 job：17 个；AON Timer native 3 个、CIP CSR 6 个、memory 2 个、TL/error 2 个、interrupt 1 个、security countermeasure 1 个、stress 2 个。
- build mode：`default` 6 个、`cover_reg_top` 11 个；所有 job 均保持 `simulation_mode=cov` 和 `+en_cov=1` 契约。
- 注册 sequence：6 个；初始语料计划为每个候选 1 次、固定 simulation seed 42、单并发，共 17 次。
- 输入契约：目标 revision `9f20940d494a223cc950a5b98f748fb28109d458`、tree `4229b5d334cf7c02996856ddbdf625989b5a6b58`，33 个源码/配置输入逐文件 SHA-256 验证通过。
- 论文参数只记录为待复核预算：logical batch 10、100 batches、1000 submissions、10 workers；PDF 没有披露可复用的 numeric seed，因此清单明确保留为未披露。

公开证据入口：[source_9f20940d_hashcomplete](evidence/2026-10-31/source_9f20940d_hashcomplete/)。

## 不得提前声称

本阶段只完成测试池盘点和计划注册；17 次初始仿真、bin-by-run 矩阵、覆盖并集和论文曲线仍未执行。不能把用户提供的 4525/4279 参考数直接写成新的运行结果，也不能引用旧 379-bin 项目的结果替代本阶段产物。

## 下一步

阶段 06：在服务器新建独立 run 根目录，按本计划逐项运行 coverage-enabled initial corpus，记录失败/seed/运行时，并提取阶段 04 冻结 manifest 的 bin-by-run 矩阵。在比较 default 与 `cover_reg_top` 的 coverage-definition signature 前，不合并不同 build mode 的列。
