# z1–z17 逐页功能复查（本地检查结果）

本次临时任务只检查每套已经存在的页面。现行通用门槛见 `TEMPLATE_ACCEPTANCE_STANDARD_V2.md` 的政策2.3；旧的首页交互结果不能代替逐页链接和控件操作。业务修改严格限于 `templates/z1`–`z17`、`static/z1`–`z17`。本地结果不等于线上、主管验收或上线。

## 可重复入口与当前证据

先保持本地 z1–z17 预览在 6301–6317 运行，再从本目录执行：

```powershell
.\.venv\Scripts\python.exe src/z_link_audit.py --output runs/<新HTTP目录>
.\.venv\Scripts\python.exe src/z_page_actions.py --input runs/<新HTTP目录> --output runs/<新浏览器目录>
```

工具版本：Playwright CLI 0.1.20。原始 HTTP 页面、链接、控件清单和失败分别在 `pages.json`、`links.json`、`findings.json`；浏览器逐页 390/1280 CSS px 的点击记录在每套 `zN-results.json`、`zN-findings.json`。这些运行证据存于忽略的 `runs/`，报告引用路径不等于在其他机器已经执行。

当前源码的原始响应复查：`runs/z-functional-links-final-20260919/`；其首次结束时 `source_fresh=true`，后续又修复了z7的操作语义，故当前z7以独立的 `runs/z-functional-links-z7-final-20260919/` 为准，不能将旧全站hash直接称为最终全站fresh。17套共有579个已存在页面类型，其中443个有当前200样例，136个无200样例而保持 blocked；首轮修复后的443个样例有17,832个去重内部链接目标，其中17,687个200、28个301、15个404、100个500、2个请求超时。超时两条重试均200；100条500复查时75条仍500、25条转200，后者标记本地不稳定，不当作稳定PASS。原始 `findings.json` 保留首次结果，复查证据为 `retry-blocked.json` 和 `retry-500.json`。z7最新局部复查28个200页面、1072个目标、1个404与5个500，输入hash新鲜。

**后续当前源码全量HTTP复查**：`runs/z-functional-http-current-20260919/`，`source_fresh=true`；443个200页面样例，17,766个去重内部链接目标，17,617个200、28个301、8个404、97个500、16个请求超时。将500和超时共113个目标复试：75个仍500、36个转200、2个仍超时，证据 `retry-findings.json`。本轮仍有136个已存在页面类型无200样例而 blocked。网络抖动转200不是稳定质量PASS；需结合线上样例及后端确认。

模板内已修正：z1–z17教练姓名指向球员资料页的无效链接（保留姓名文本）；z5–z10资讯页在缺少联赛对象时生成的 `/lanqiu//...` 与 `/jijin/-1.html`；z15–z17资讯面包屑 `/zuqiu/zuqiu`；z7三个在JS中只操作筛选却写成跳转链接的控件。此前全站重测404由47降至15，后经明确的欧联入口迁移降至8。z7在 `/hottag/2330.html` 与 `/zuqiu/news/` 的390/1280宽度逐个点击三个筛选：12次目标面板与可见赛事ID精确匹配、无整页溢出；证据 `runs/z7-filter-id-result.json`，界面截图 `runs/z7-filter-{390,1280}-20260919.png`。逐页点击完整报告在下文，不能据此宣布质量验收通过。

z8–z10 也存在同类被JS截留的假跳转链接，现分别改为按钮。三套×专题详情/足球资讯两页×390/1280宽度×三个筛选共36次，目标面板及可见赛事ID精确匹配、无整页溢出；证据 `runs/z8-10-filter-result.json` 和 `runs/z8-10-filter-output-20260919.txt`，截图在 `runs/z{8,9,10}-filter-{390,1280}-20260919.png`。这些模板当前的局部原始链接重查 `runs/z-functional-links-z8-10-filter-final-20260919/` 有54个200页面、2018个目标、0个404、13个500，`source_fresh=true`。

同一筛选操作语义缺陷还出现在 z11、z12、z14–z17 的实际专题页，已在各自模板目录改为按钮。Playwright CLI 当前在24个页面×宽度状态中，18个有该控件，逐一完成54次目标面板与可见赛事ID的精确比对，全部通过且无整页溢出；另6个状态是 z15–z17 的 `/zuqiu/news/`，原页面没有该控件，按真实页面结构记N/A。证据 `runs/z11-17-filter-result.json`、同目录输出文本及专题筛选区截图。局部当前原始链接重查另存 `runs/z-functional-links-z11-17-filter-final-20260919/`。

浏览器逐页点击额外发现原始HTML不含、JS后注入的坏地址：z11等模板把 `/hottag-1.html` 当联赛根，拼出 `/hottag-1.html/news/`，点击404。已在本轮 z11、z12、z14–z17 私有JS中限制联赛导航只用于实际联赛路径；六套当前 `/hottag-1.html` 都200且JS后坏链接为0，证据 `runs/hottag-nav-result-20260919.txt`。z13没有这份JS，未作推断；修复后的逐页检查已包含在最新合并报告。

通用点击脚本会先处理 z9/z10 的整屏入口、z8 的关闭抽屉、真实命中区域，并对 z13 多搜索引擎先选择“本地”，回顶等待平滑滚动完成。此前 z8–z10 的屏外链接点击超时及 z13 搜索/回顶的无效结论是测试脚本误判，不能当作真实模板故障。z13 直接CLI复验在390/1280宽度均显示搜索结果200、回顶从2032/888px至1px，证据 `runs/z13-search-top-result-20260919.txt`。合并报告只接受当前源码指纹的结果。

脚本还会将 `role=tab` 的链接按操作而非导航核对，识别 `target=_blank` 打开的目标标签页（z7视频入口实测通过，见 `runs/z7-popup-check-20260919/`），搜索时明确选择所在表单的本地引擎。z14首页搜索在两种宽度下按“本站”选项点击，结果页200，证据 `runs/z14-site-search-result-20260919.txt`。大型模板按5个页面分片；共享 `/play` 逐页记blocked而非反复操作或默认PASS。早期用固定CLI session造成一次z13分片相互干扰，旧批次已丢弃；新的运行目录使用独立session。

待 Rechard / 数据源核对的本地样例：`/tags/{id}` 在17套的相同数据条件下返回500（用户先前说本地此项暂不处理）；z12德甲多个 `/dejia/jijin/{id}.html` 返回404；z17首页指向 `/ouguanbei/teams/teaminfo-{id}.html` 的三条链接返回404。z7的阿森纳转会页 `/yingchao/teams/transfer-10215.html` 点击“签约”实际请求 `/yingchao/teams/transfer-10215/2026-2027/1_7.html`，390及1280宽度均返回500（OSError Invalid argument）；前端触发了请求，需核对后端筛选参数或数据。另有NBA球队详情、足球积分/录像等本地500及部分重试转200的波动；具体 URL、来源页面和状态以 `findings.json` 为准。共享 `/play` 的浏览器控件及加载超时不能归咎于某套模板。上述问题尚未核对线上，不能擅自修改后端、数据或路由。

`/oulianbei` 的七条原始404来自z5–z11动态热门联赛数据。TG回复链：19:05 Rechard建议先去掉，19:14 又明确可改为 `/oulian`，用户接受。按较新的具体方案保留名称，仅在这七套模板映射该条 href。本地七套 `/oulian` 均为200；Rechard给的线上示例当前网页工具不可访问，未声称线上通过。旧404保留在原 `findings.json` 作为修复前证据，新局部回归另存。

按最新回复修正后，z5–z11 `/zuqiu` 各出现1个 `/oulian` href、0个 `/oulianbei` href，目标均为200；回读证据 `runs/oulian-link-recheck-20260919.json`。初次全站扫描的15条404中，此7条已经修复；其余8条再次HEAD仍404，见 `runs/remaining-404-20260919.json`。此为本地结果，浏览器JS触发的动态URL还须结合逐页操作记录。

19:15 Pony问其余404是否都按这种方式换地址，Rechard明确“不，改名这种情况很少”。本次映射仅限已确认的欧联入口，其余404必须逐项请示，不自动猜路径。七套修正的回读与HTTP证据：`runs/oulian-link-recheck-20260919.json`。

## 最终本地证据与交接状态

合并入口 `src/z_functional_report.py`，本次结果 `runs/z-functional-v23-final-current-20260919/report.md` 与 `summary.json`。443个可访问页面样例×390/1280宽度，共886/886状态有当前输入指纹证据；40个历史过期文件被排除。原始链接仍有8个404，浏览器实际导航没有新增404。分类为13套 blocked、4套 fail；**没有模板被宣布已验收通过**。所有17套都含两档宽度的共享 `/play` 阻断；另有136个实际存在的页面类型缺200样例，工具未把它们当作已访问。许多默认激活或业务契约不明的控件保留needs_review。具体每套链接/动作/阻断/待复核数见机器报告；带来源的404可转给Rechard，见 `RECHARD_404_HANDOFF_20260919.md`。

修复重点回归：z7–z10及z11、z12、z14–z17筛选选项的合计102次精确可见ID/面板比对通过（后六套的六个无模块状态有N/A依据）；z15原先超时分片经单页拆分后58/58状态新鲜、动作与链接无失败，见 `runs/z15-combined-status-20260919.json`；z16球队筛选与关联比分布局专项144个状态PASS，负例确实被检出、source_fresh=true，见 `runs/z16-leo-policy22-current-20260919/summary.json`。z16积分页手机回顶可用，桌面该页仅可滚317px而按钮在480px后出现，证据 `runs/z16-jifen-top-result-20260919.txt`。z6首页比赛链接、z7视频弹窗/联赛面包屑、z17排行榜赛季入口的批量误报均经精确浏览器操作复核，证据分别为 `runs/z6-link-smoke-result-20260919.txt`、`runs/z7-link-triage-result.json`、`runs/z17-season-triage-result-20260919.txt`。外部工具完整90项单测通过。

仍需 Rechard/数据源处理上述8条404、稳定500及共享页；仍需补已有页面缺样例和复杂控件的人审，修改页面的完整设计复查以及线上联调。`ready_for_human_review=false`；公司代码仍在本地工作树，未提交/推送、未合并、未部署、未验证 Bing 抓取或收录。外部工具和文档的Git交付状态另行记录。
