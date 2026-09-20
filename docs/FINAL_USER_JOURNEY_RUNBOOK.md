# 模板最终用户操作测试

本入口复用现有页面契约、Playwright CLI 0.1.20 和 `scripts/layout-audit.js`。测试配置在 `config/final-user-cases.json`，公共用例由 `src/final_user_journeys.py` 与 `scripts/cli-final-user-journeys.js` 执行。z1–z17 只是当前分配；下次换模板编号时先确认新的 TaskSpec 与页面样例，再给该编号登记专用控件契约，不沿用 z 范围授权。Claude Code 可以执行同一命令和读取同一证据，无须猜测每个按钮的预期。

执行前确认原业务项目各模板预览已在 `6301–6317` 运行且选中的确是相应模板；不得改 `.env`、Python 或他人的模板。现有 `runs/z-v2-recheck-20260919/contracts/` 提供页面类型和历史样例，工具会重新请求每个样例，不把历史 HTTP 200 当作当前结果。原始成功 HTML 存在本地运行目录，失败状态单列。共享 `/play` 超出本次模板写入范围，明确排除。首页以外无真实样例的已存在页面保留 `missing_page_samples`，不能算通过。

公共用例以用户能直接感知的行为为主：每个有样例的页面取原始 HTTP 与主要文字/链接，再于 390/1280 CSS px 用浏览器检查主体、页面横向溢出和硬性布局问题；首页补明暗主题、移动菜单开关、主题按钮与刷新持久化、搜索 Enter 与按钮、回顶、实际导航点击。截图保留主页两宽度两主题。颜色、链接或按钮“存在”不能单独判功能通过。

每套另有一项明确的组件契约：z1 更多赛事展开；z2–z6、z8–z11 赛程标签与对应列表；z7/z14 直播中心标签与面板；z12 联赛排行标签；z13 日期筛选与可见赛事日期；z15 赛事筛选与真实行集合；z16 足球积分榜标签、可见内容和对应“更多”地址；z17 热门球队分类与面板。所有可用选项逐个点击。组件不存在、数据无法判断或脚本能力不足必须写 blocked/needs_review，不靠高亮变化冒充通过。z16 首页局部滚动表头另复用 `src/z16_portal_header_regression.py`，球队筛选与详情关联赛程另复用 `src/z16_leo_regression.py`。

```powershell
cd C:\tyseo\pony-template-workflow
.\.venv\Scripts\python.exe src\final_user_journeys.py --output runs\final-user-<new-id>
.\.venv\Scripts\python.exe src\final_raw_seo_report.py --run runs\final-user-<new-id>
.\.venv\Scripts\python.exe src\final_nojs_check.py --run runs\final-user-<new-id>
.\.venv\Scripts\python.exe src\final_user_report.py --run runs\final-user-<new-id>
```

单套试跑可加 `--ids z16`。下次换编号时须先由团队确认并在配置中登记专用用例、提供新页面契约；预览端口不符合当前规则时传 `--base-url-pattern`。命令参数不能越过当次业务目录授权。每次使用新运行目录。`summary.json` 按模板列出页面数、公共/专用状态、失败和缺样例。`{id}/browser.json`、`{id}/http-pages.json`、`{id}/findings.json`、原始 HTML 和截图是细节证据。`source_fresh=false` 的结果作废。`automated_pass` 只表示此入口执行的断言通过，不表示完整 SEO、无 JS、全部浏览器引擎、线上或公司人工验收通过。

第二条命令复用已有 `checks.html_checks`，只读取首条命令保存的原始响应 HTML，输出每套 `raw-seo.json` 与全局 `raw-seo-summary.json`。其中 canonical、索引策略和 TDK 多配置变化没有确定输入时只能 `needs_review`；结果不会被当作 Bing 收录或排名证明。

第三条补首页和该套专用入口在390/1280宽度下关闭 JavaScript 的正文与导航检查，结果在 `nojs-results.json`。这是现有 Python Playwright 的补充；主要交互和逐页浏览器检查仍由 CLI 0.1.20 执行。这里不测试无 JS 下的主题切换，也不把两个入口的通过冒充全部页面的无 JS 通过。

最后一条汇总成 `report.md`，逐套保留缺样例和待复核的操作。先运行前三条再生成报告；缺少任一证据时报告写“未运行”，不能补写通过。

本入口是用户操作回归，不替代现有完整验收：原始 SEO 及动态 TDK/索引策略、无 JS、比分边界、Firefox/WebKit、复杂布局疑点和逐页视觉复核仍按 `TEMPLATE_ACCEPTANCE_STANDARD_V2.md` 与 `docs/ACCEPTANCE.md` 的独立证据门槛执行。发现失效时先修工具或模板根因，之后重新运行受影响用例；不能删断言或把旧运行结果改成 PASS。用户已明确本轮不处理无关 404，HTTP 异常仍留证但不借此修改后端或其他模板。
