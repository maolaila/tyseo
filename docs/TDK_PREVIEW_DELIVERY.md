# 上站资料预览交付记录（2026-09-18）

范围：仅外部工作流；业务仓库未修改。用户预览后手动回填后台，正式提交等待 Leo 审核。

## 实际完成

- 20 份 TDK 本地草稿与版本标识，按本人分配词和 r62 能力生成；可展开查看。
- 定时扫描只读表格、准备本地草稿。上站表回填与后台文本框回填分别需要用户手动按钮确认。
- Google 写入前核对行、归属、旧值；写后回读。人工不同内容拒绝覆盖。
- 后台预填核对上站脚本，代码不点击提交。没有正式提交 API。
- 持续使用普通持久化浏览器；没有清除登录配置。

## 证据与限制

| 项目 | 状态 | 证据 |
| --- | --- | --- |
| 本地测试 | pass | `runs/workbench-qa/tests-tdk-preview.log`，62 项通过 |
| CLI 版本/help | pass | `runs/workbench-qa/cli/cli-doctor.json`，0.1.20 |
| 工作台 390/1280 px | pass | `runs/workbench-qa/tdk-ui-checks.json`；20 个预览、展开后刷新保留、无页面横向溢出、无 JS 错误 |
| PC/移动视觉复核 | pass | `runs/workbench-qa/tdk-preview-1280.png`、`tdk-mobile-detail.png`，已实际查看 |
| 实际上站表读取 | pass | 本批 20 行已购买移表；`runs/site-launch/2026-09-18-pony-20/tdk-before.json` |
| 未进行外部回填 | pass | `tdk-preview-verification.json`：E:H 未变、后台未提交；UI 检查未点击外部写按钮 |
| 实际写表/后台预填 | blocked | 尚待用户预览确认；本地测试不能替代首次实写回读 |
| 后台入口 | blocked | 表格分配 s213017，已知入口 s213016；已禁用后台回填 |
| Leo 审核/正式上站 | needs_review | 尚未审核、未提交、未部署、未观测 Bing 抓取 |

复现：`.venv/Scripts/python.exe -m unittest discover -s tests`；`./Start-Workbench.ps1` 后访问 http://127.0.0.1:8766/。

这些是工作台验收证据，不是业务模板全矩阵验收。参考词表同时承载分组信息，但当前有效轮换尚未核验，今天保持 r62。TDK 为 AI 撰写的本地策略草稿，不冒充逐词竞品研究完成或在线模型自动调用。
