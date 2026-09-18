# 半自动验收增量规范

来源：用户本轮增量提示，2026-09-18。补充现有 PRD v2.0 与公司规范，不替代强约束。

## 有效性与范围

- 已核对现存 PRD.md、CODEX_START.md、两处 AGENTS.md、docs/ACCEPTANCE.md、最新 SESSION_NOTES 和现有页面契约。未发现另一个 Pony_Bing_SEO_Workflow_PRD_v2.md 或后续版；不按mtime推断替代关系。
- 公司明确目标目前为 z1–z21 检查。本轮优化外部工具，没有单一业务写入目标，不改公司源代码或根配置，不扩大到采购/发布/TDK/表格。
- 现有环境复用；进程环境选择模板，禁止改 .env；r62 参考默认只读。HeaderJS/FooterJS、jQuery、ajs.js 的业务保留要求继续有效。
- 日常任务由人选择、确认契约与处理待定项；工具批量执行已实现的采集/检查。RS机器人仅留输入/输出契约，config/integrations.json 中关闭，不连接 C:/RS。

## 执行契约

1. 页面×数据状态×规则建立完整计划，保留缺样例页面。比分适用性或状态映射未知时标待定，不把它省略或当N/A。
2. 分别保存原始HTTP响应（状态/响应头/正文）、执行后DOM、无JS DOM。page.content()仅作DOM，不能伪称原始HTTP。调试500正文有秘密风险时省略正文并明确阻断。
3. 公司关键词仅从有效规则/现有TDK字段得出；没有批准的密度、字数、HTML比率则不设阈值。仅检查绑定、转义、页面一致性，不自动写生产文案。
4. canonical、分页、indexing从契约确认；原始meta与X-Robots-Tag独立保存。robots.txt/Sitemap只读检查；不提交IndexNow。unknown策略保持needs_review，不一律改成self-canonical/index。
5. 真实链接、语义、JSON-LD语法和可见事实、缺失alt及测试数据残留分别检查；装饰图空alt可以合法。自动检查不能替代语义判断。
6. 保留完整默认矩阵：每页 Chromium 360/390/768/1280/1920×light/dark，无JS 390/1280；关键页补320、200%文字、899/900两侧，以及WebKit/Firefox。断点899/900是工程默认，页面有明确断点时补对应两侧，不当作公司唯一断点。
7. 功能测试独立于截图：搜索全链、主题跨页/刷新/存储失败、导航焦点/关闭滚动、回顶遮挡、已有分页筛选。主题模拟仅表示请求了颜色方案，必须证实应用实际主题。未知选择器或能力不能标pass。
8. 比分0与空值分离，验证主客绑定、长队名、三位数、logo失败与真实状态；合成数据仅在外部fixture环境。
9. 失败记录含rule_id、页面、视口、主题、数据状态、选择器/证据、预期/实际、严重度及责任层。无证据不能pass；N/A必须有依据。
10. 源码、CSS/JS、共享脚本、契约、规则、配置、夹具或私有环境配置变化均使相关旧结果失效。文件证据有hash，逐页AI复核也绑定输入版本。
11. 截图成功、自动检查、AI视觉/SEO、公司验收、发布、抓取分开记录；只看首页不能完成整套复核。
12. 修复只在授权目录，按组件根因回归所有使用页；最多三轮，禁止删测试/放宽阈值。最终完整矩阵未完则不可交付。

## 现有命令的增量

```powershell
.\.venv\Scripts\python.exe workflow.py plan-acceptance --task tasks/bootstrap.json --contract runs/bootstrap/page-contract.json --run runs/acceptance-new
.\.venv\Scripts\python.exe workflow.py assess-acceptance --task tasks/bootstrap.json --contract runs/bootstrap/page-contract.json --run runs/acceptance-new
```

计划包含全部页面与必测组合，未执行记录不会被删掉。`review-ledger.json` 是待填写的实际复核记录，不是预填通过。

CLI固定为 @playwright/cli 0.1.20；Python Playwright版本单独在requirements-lock.txt中。CLI session=tyseo-acceptance，cwd与日志/快照在外部runs目录。优先CLI批量脚本；已有Python Playwright矩阵入口保留复用。完整HTML不返回终端，只输出摘要。

旧z-review是首轮light采集，不能作为本规范的完整验收。现有46条规则尚非全部实现；新增门禁会明确阻断未完成的契约、功能与逐页复核，不用“工具可运行”掩盖缺口。
