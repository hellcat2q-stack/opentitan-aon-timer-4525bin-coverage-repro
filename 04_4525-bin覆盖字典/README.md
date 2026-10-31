# 阶段 04：4525-bin 覆盖字典

**状态：已完成（2026-10-31）。** 本阶段从阶段 03 的真实 URG 报告、展开 bin 报告和 VCS coverage XML 冻结了公开 manifest。原始 VDB、simv、许可证和学校服务器路径仍在服务器专用目录，未提交到 GitHub。

## 目标与结果

阶段 04 固定 covergroup、coverpoint/cross、bin 名称、实例展开、来源位置、权重和分母口径。验证结果如下：

| 口径 | 结果 |
| --- | ---: |
| URG 类型定义去重后的 bins | 4,507（命中 46） |
| URG 实例计分分母 | 4,525（命中 45，0.994475%） |
| 展开记录（含 8 个 weight-zero） | 4,533 |
| AON Timer 自有 score bins | 4,279 |
| 通用 testbench score bins | 246 |
| covergroups | 16 |

URG 总计行在启用 `instcov_for_score` 时显示的是实例计分口径 4,525；16 个明细行相加得到类型定义口径 4,507。两者都保存在 manifest，不能混写成单一分母。`weight=0` 的 8 个 bin 保留在静态字典中，但不进入实例计分分母。类型汇总的 46/4,507 与实例计分的 45/4,525 都由同一份报告独立复核。

## 公开产物

- [`coverage_manifest.v1.json`](evidence/2026-10-31/run_20261031_08/coverage_manifest.v1.json)：4,533 条稳定 ID 记录，含 type aggregate、per-instance、coverpoint/cross、weight、来源和排除字段。
- [`smoke_validation.json`](evidence/2026-10-31/run_20261031_08/smoke_validation.json)：运行 ID、源码 revision、两种 URG 分母、原始报告哈希和 manifest 哈希。
- [`group_scope_summary.tsv`](evidence/2026-10-31/run_20261031_08/group_scope_summary.tsv)：16 个 covergroup 的类型和实例计分摘要。
- [`SHA256SUMS`](evidence/2026-10-31/run_20261031_08/SHA256SUMS)：公开产物哈希。
- [`freeze_manifest.py`](freeze_manifest.py)：读取脱敏 URG/XML 输入并生成 manifest；拒绝覆盖已有输出目录。
- [`verify_stage04.py`](verify_stage04.py)：不依赖服务器输入，检查产物计数、两种分母、哈希和私有路径脱敏。

## 复核命令

在仓库根目录执行（Python 3.10+，仅使用标准库）：

```powershell
python "04_4525-bin覆盖字典/verify_stage04.py" `
  --bundle "04_4525-bin覆盖字典/evidence/2026-10-31/run_20261031_08"
```

预期输出为 `verification: PASS`，并报告 4,533 / 4,525 / 8 / 4,279 / 246 / 4,507 这些计数。

## 输入和局限

冻结输入来自学校服务器阶段 03 run `20261031_08`：VCS/URG P-2019.06-SP1、OpenTitan revision `9f20940d494a223cc950a5b98f748fb28109d458`、完整 URG report、`-group expand_bins` 展开报告以及 cumulative/instance coverage XML。输入文件名和 SHA-256 写入 `smoke_validation.json`，原始输入不进 GitHub。

本阶段只冻结静态字典和单次 smoke 的报告命中，不代表论文的 1000 submissions、随机基线、聚类或 UCB 结果；下一阶段先盘点官方测试池，再建立初始语料计划。

## 下一步

阶段 05：盘点全部官方 AON Timer/CIP 测试、sequence、build mode、plusargs 和 seed 规则，形成可审计的作者测试池与初始语料计划。
