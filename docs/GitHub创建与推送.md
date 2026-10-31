# GitHub 创建与推送

当前窗口已完成本地仓库骨架和首个提交，但 GitHub 新仓库创建页面未获得浏览器操作权限，因此需要仓库所有者先在 GitHub 创建一个空仓库：

- Owner：`hellcat2q-stack`
- Repository：`opentitan-aon-timer-4525bin-coverage-repro`
- Visibility：按项目需要选择；建议 Public，便于交接
- 不要勾选 README、.gitignore 或 License，保持空仓库

创建后，在本地仓库执行：

```powershell
git -C "C:\Users\Admin\Documents\ChatGPT\论文复现\opentitan-aon-timer-4525bin-coverage-repro" remote add origin https://github.com/hellcat2q-stack/opentitan-aon-timer-4525bin-coverage-repro.git
git -C "C:\Users\Admin\Documents\ChatGPT\论文复现\opentitan-aon-timer-4525bin-coverage-repro" push -u origin main
```

推送后核对：

```powershell
git -C "C:\Users\Admin\Documents\ChatGPT\论文复现\opentitan-aon-timer-4525bin-coverage-repro" ls-remote origin refs/heads/main
git -C "C:\Users\Admin\Documents\ChatGPT\论文复现\opentitan-aon-timer-4525bin-coverage-repro" rev-parse HEAD
```

两个 SHA 应相同后，才把仓库链接交给另一个 Codex 窗口。
