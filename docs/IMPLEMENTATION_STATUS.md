# 当前实施与交接状态

2026-09-18：用户在实施过程中将优先级改为“先不要新模板，z1–z21 全部看一轮”。已停止新模板扩展，保留外部草稿及已执行的矩阵；当前继续 z 系列只读实机检查。

| 阶段 | 已实际完成 | 证据/文件 | 未完成或阻断 |
|---|---|---|---|
| M0 | 阅读完整PRD/入口/规则；r62源码与HTTP审计；全仓库受保护指纹 | runs/bootstrap/project-audit.md、page-contract.json、business-before.json、changed-files.json | 54是静态候选入口，19个r62文件缺失，26类真实HTTP成功；其余不能编造样例 |
| M1 | 任务schema、精确目录门禁、junction防护、哈希与增量检查、局部续跑机制 | src/core.py、workflow.py、tests；31测试通过，pip check通过 | 门禁不是OS沙箱；完整阶段自动恢复尚需加强 |
| M2 | 两种外部Jinja草稿与设计schema | drafts/editorial、drafts/rail；config/design-*.json | 无正式编号；不写业务目录；其余页面结构尚未全面重设计 |
| M3 | 草稿主题/非模态手机导航/返回顶部/搜索表单；26类真实路由上下文外部渲染 | src/generate.py、src/render_probe.py、runs/rendered | 完整站点功能未验收；搜索白名单/缺失模板问题保留；不是实际目标模板联调 |
| M4 | 浏览器矩阵与原始HTML检查、证据索引、部分规则执行器 | runs/bootstrap/review-index.html、report.json、rule-coverage.json | 矩阵因任务转向中止；外部草稿有溢出失败；AI只查看部分截图；没有全套PASS |
| M5 | 第二个设计可由同一生成入口产生，产物独立 | rail/design-spec.json、各自matrix-results | 差异化/完整质量验收未通过；未交付可上线整站 |
| 当前z检查 | z1–z21静态盘点、只读真实模板选择与逐页采集工具 | runs/z-inventory、src/z_review.py、runs/z-review | 首轮是390/1280 light采集；暗色/无JS/全部交互不能由此替代 |

工具工作区本地origin为 https://github.com/maolaila/tyseo.git 。本轮没有任何commit/push/PR/merge，业务仓库、域名工作流不改；未TDK/采购/部署/爬虫提交。此前其他轮的r62一行修复属于本轮基线，不重推。

后续操作从 docs/WORKFLOWS.md 开始。最新任务和转发上下文在 docs/SESSION_NOTES.md。不要从旧需求段落推导本轮已完成状态。

当前z1–z21首轮采集已完成。真实HTTP样本552个（模板×页面类型），结果记录1686：fail30、blocked587、needs_review1069。详细索引 runs/z-review/review-index.html；AI实际复核范围及问题见 ai-first-review.md。未进行业务修复或全套验收。
