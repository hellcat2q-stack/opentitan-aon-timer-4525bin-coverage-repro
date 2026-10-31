# OpenTitan AON Timer 论文复现资料

核对日期：2026-10-31

## 结论

OpenTitan 官方 AON Timer DV 覆盖报告确实超过 4,000 个预期 functional group bins。报告汇总为 4,525 个 group bins；其中 AON Timer 自身的四个 covergroup 合计 4,279 个：

| Covergroup | 预期 bins |
|---|---:|
| `timer_cfg_cg` | 173 |
| `wake_up_timer_thold_hit_cg` | 2,050 |
| `watchdog_timer_bark_thold_hit_cg` | 1,028 |
| `watchdog_timer_bite_thold_hit_cg` | 1,028 |
| **AON Timer 自有覆盖合计** | **4,279** |
| testbench 通用 coverage groups | 246 |
| **官方报告总数** | **4,525** |

这些是验证平台中的 covergroup bins，包含计数/阈值区间和 cross bins；不是 RTL 中 4,000 多个硬件寄存器或计数器。报告的当前覆盖状态为 2,153/4,525（47.58%），这是官方标准回归的合并结果，不能等同于论文的 75.33%。

## OpenTitan 对应源码

以下链接固定到官方覆盖报告记录的 OpenTitan revision `9f20940d494a223cc950a5b98f748fb28109d458`，便于对应报告中统计到的 bin 结构：

- [AON Timer RTL 顶层](https://github.com/lowRISC/opentitan/blob/9f20940d494a223cc950a5b98f748fb28109d458/hw/ip/aon_timer/rtl/aon_timer.sv)
- [功能覆盖定义（四个 covergroup）](https://github.com/lowRISC/opentitan/blob/9f20940d494a223cc950a5b98f748fb28109d458/hw/ip/aon_timer/dv/env/aon_timer_env_cov.sv)
- [测试计划与测试点](https://github.com/lowRISC/opentitan/blob/9f20940d494a223cc950a5b98f748fb28109d458/hw/ip/aon_timer/data/aon_timer_testplan.hjson)
- [DV 测试平台 README：序列说明和启动方法](https://github.com/lowRISC/opentitan/blob/9f20940d494a223cc950a5b98f748fb28109d458/hw/ip/aon_timer/dv/README.md)
- [仿真配置](https://github.com/lowRISC/opentitan/blob/9f20940d494a223cc950a5b98f748fb28109d458/hw/ip/aon_timer/dv/aon_timer_sim_cfg.hjson)
- [AON Timer 寄存器规格](https://github.com/lowRISC/opentitan/blob/9f20940d494a223cc950a5b98f748fb28109d458/hw/ip/aon_timer/data/aon_timer.hjson)
- [OpenTitan 主仓库](https://github.com/lowRISC/opentitan)

## 官方覆盖结果与 bin 列表

- [AON Timer 仿真结果页](https://reports.opentitan.org/hw/ip/aon_timer/dv/latest/report.html)：显示报告日期、源码 revision、仿真器、测试结果和覆盖摘要。
- [覆盖 Dashboard](https://reports.opentitan.org/hw/ip/aon_timer/dv/latest/cov_report/dashboard.html)：确认 group 总数为 4,525，覆盖 2,153，覆盖率 47.58%。
- [Group 汇总表](https://reports.opentitan.org/hw/ip/aon_timer/dv/latest/cov_report/groups.html)：逐项列出 covergroup 名称、covered / expected 数。
- [timer_cfg_cg bins](https://reports.opentitan.org/hw/ip/aon_timer/dv/latest/cov_report/grp1.html)（173）
- [wake_up_timer_thold_hit_cg bins](https://reports.opentitan.org/hw/ip/aon_timer/dv/latest/cov_report/grp2.html)（2,050）
- [watchdog_timer_bark_thold_hit_cg bins](https://reports.opentitan.org/hw/ip/aon_timer/dv/latest/cov_report/grp3.html)（1,028）
- [watchdog_timer_bite_thold_hit_cg bins](https://reports.opentitan.org/hw/ip/aon_timer/dv/latest/cov_report/grp4.html)（1,028）

该结果页记录的生成日期为 2025-02-08，源码 revision 为 `9f20940d49`，仿真器为 VCS。网页路径中的 `latest` 是 OpenTitan 报告站点提供的入口；页面实际数据日期如上。

## 复现入口

OpenTitan AON Timer 测试序列主要覆盖 smoke、prescaler、jump、stress、min/max threshold、wake-up counter 高位 CDC、custom interrupt、alternating enable 等场景。测试计划在 `aon_timer_testplan.hjson`，功能 bins 在 `aon_timer_env_cov.sv`。

OpenTitan DV README 给出的单项 smoke 测试命令是：

```sh
dvsim hw/ip/aon_timer/dv/aon_timer_sim_cfg.hjson -i aon_timer_smoke
```

要复现论文中的调度实验，需要在兼容的 DV 仿真环境上运行并保存每次仿真的 bin hit 向量、测试序列和运行时数据，再由论文方法做聚类及 UCB 调度。官方公开报告是标准回归的合并覆盖结果，并非论文使用的初始 corpus 或逐次仿真的原始 CSV。论文附件没有公开该 corpus、bin 清单、脚本或随机种子，因此源码能重建同一 DUT 与覆盖模型，但仅凭公开仓库不能逐数复现论文曲线。论文报告的 AON Timer 实验设置为 1,000 次提交、10 个并行 worker。

## 工作区源码副本

已在工作区克隆 OpenTitan 主仓库，路径：`C:\Users\Admin\Documents\ChatGPT\论文复现\opentitan_src`。克隆时 HEAD 为 `41049e9deb40e0602cd5272c40398be380ae2637`；公开覆盖报告统计所对应的旧 revision 已在上方固定链接中列出。
