# 阶段 02：固定源码与依赖

**状态：已完成（2026-10-31）。** 目标 OpenTitan revision、完整 Git tree、AON Timer DV 配置、上游 Python 依赖和服务器工具版本均已锁定并在学校服务器复核；阶段 02 提交已推送并核对远端 SHA。阶段 03 的官方 UVM 编译、仿真和真实 coverage smoke 现已在下一阶段完成。

## 验收结果

| 项目 | 现场结果 | 证据 |
| --- | --- | --- |
| OpenTitan revision | `9f20940d494a223cc950a5b98f748fb28109d458` | [source_lock.json](source_lock.json) |
| 完整源码 Git tree | `4229b5d334cf7c02996856ddbdf625989b5a6b58`；10,514 文件 | [服务器解包复核](evidence/public_20261031_01/source_lock_verified.json)、[本机归档复核](evidence/public_20261031_01/local_archive_tree_verification.json) |
| AON Timer 源码 | 45 个文件逐字节复核；关键文件共 48 个 | [源码核验](evidence/public_20261031_01/source_lock_verified.json) |
| DV 配置 | 锁定官方 HJSON、core、测试/sequence、reseed 和 run options | [source_lock.json](source_lock.json) |
| DV 工具 | VCS/URG `P-2019.06-SP1`，CovDB 13.1；UVM 1.2 沿用阶段 01 实测 | [工具版本](evidence/public_20261031_01/tool_versions.json) |
| Python 依赖 | 上游 83 项锁定依赖安装到独立 `.venv-opentitan`；87 个发行包清单中额外列出 venv 的 pip/setuptools 和构建辅助包 | [依赖核验](evidence/public_20261031_01/dependencies_verified.json)、[安装清单](evidence/public_20261031_01/python-requirements-installed.txt) |
| 依赖一致性 | `pip check`：No broken requirements found | [pip_check.txt](evidence/public_20261031_01/pip_check.txt) |
| 官方工具导入探针 | revision 内 `util/dvsim/dvsim.py --help` 返回 0 | [探针摘要](evidence/public_20261031_01/dvsim_help_summary.json) |
| 离线依赖包 | 83 个上游锁定发行包逐一校验；归档 SHA-256 `3cbb013320dfd000057659d33cee33676009b2c912e863f16a0c9d1552d346c8` | [依赖核验](evidence/public_20261031_01/dependencies_verified.json)、[包哈希](evidence/public_20261031_01/wheels_SHA256SUMS.txt) |

本阶段没有修改 OpenTitan 源码，也没有应用兼容补丁。源码完整树核验脚本会按 Git 的文件/符号链接模式重建 tree object；服务器上的本地验证器和本机独立验证器都确认同一 tree SHA-1 与文件数。证据目录的 [SHA256SUMS](evidence/public_20261031_01/SHA256SUMS) 可用于离线复核公开文件。

## 复核入口

在仓库根目录用 Python 3.10+ 复核公开源码与依赖证据：

```powershell
python "02_固定源码与依赖/stage02_lock.py" verify-archive `
  --lock "02_固定源码与依赖/source_lock.json" `
  --archive ".stage_review/opentitan-9f20940d494a223cc950a5b98f748fb28109d458-gitblob.tar.gz" `
  --output "$env:TEMP/stage02-source-verification.json"
python "02_固定源码与依赖/verify_dependencies.py" `
  --source-lock "02_固定源码与依赖/source_lock.json" `
  --requirements "02_固定源码与依赖/upstream_python_requirements.lock.txt" `
  --installed-freeze "02_固定源码与依赖/evidence/public_20261031_01/python-requirements-installed.txt" `
  --pip-check "02_固定源码与依赖/evidence/public_20261031_01/pip_check.txt" `
  --build-tools-lock "02_固定源码与依赖/build_tools_lock.json" `
  --build-tools-dir ".stage_review/build-tools" `
  --bundle-lock "02_固定源码与依赖/dependency_bundle_lock.json" `
  --bundle-file ".stage_review/opentitan-wheels.tar" `
  --wheels-manifest "02_固定源码与依赖/evidence/public_20261031_01/wheels_SHA256SUMS.txt" `
  --source-verification "02_固定源码与依赖/evidence/public_20261031_01/source_lock_verified.json" `
  --output "$env:TEMP/stage02-verification.json"
```

`--bundle-file` 与 `--build-tools-dir` 指向下载/传输用的本地缓存；公开归档及两个辅助 wheels 的 SHA-256 固定在 `dependency_bundle_lock.json` 和 `build_tools_lock.json`。服务器操作命令和失败处理见 [实施记录.md](实施记录.md)。

## 局限和下一步

- `dvsim.py --help` 只验证 Python 依赖可导入及命令行可启动，不等于 FuseSoC 构建、VCS 编译、仿真或 coverage 成功。
- VCS/URG 版本来自阶段 01 的真实工具探针；阶段 02 没有重新启动许可证功能测试。
- `source_lock.json` 记录官方配置与覆盖源码，但没有用 URG 报告枚举 bin，因此 4,525/4,279 仍是待阶段 03–04 核验的参考值。
- 服务器索引 DNS 不可用，依赖经本机按上游 `--require-hashes` 锁下载，再离线传输；源码发行包的构建辅助 `wheel==0.45.1` 与 `setuptools-scm==8.2.0` 另行锁哈希。
- 阶段 03 应使用冻结的 `aon_timer_sim_cfg.hjson` 和 `lowrisc:dv:aon_timer_sim:0.1` 在该 revision 上运行最小官方 UVM coverage smoke。

完成本阶段后应提交阶段变更并停下，等待用户检查，再进入阶段 03。

## Git 交付状态

阶段变更提交为 `2eb861b967e7f16a98189fd5cda36ed33fb34e9f`，提交信息为 `02: lock OpenTitan source and DV dependencies`。已执行 `git push origin main`，并用 `git fetch origin main` 核对 `HEAD` 与 `origin/main` 均为该 SHA。
