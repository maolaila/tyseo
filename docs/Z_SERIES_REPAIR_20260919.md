# z1–z21 临时修复与验收记录（2026-09-19）

> 最新范围（用户及 Leo 2026-09-19 10:11–10:13）：当前重点调整为 **z1–z17 各自已有页面的跑版/样式修复**。本文件下方保留前一阶段 z1–z21 的真实执行记录；其中 54 类候选入口和旧 blocked 总数不再等同于新范围内的必交项。不存在的页面不要求新增，已有页面的故障继续跟踪。草稿 PR 含先前功能/SEO及z18–z21改动，尚非纯样式交付，未合并。

这次是 Leo 指定的 **z1–z21 全部检查与修复**，不进入每日域名或模板生产流水线。公司仓库工作分支为 `fix/pony-z1-z21-layout`；业务改动限于 `templates/z1`–`templates/z21` 和 `static/z1`–`static/z21`。没有改 Python、`.env`、共享模板、其他模板或上站表。

业务分支已合并当时最新 `origin/main`（合并提交 `60a43fbe3`），后续修复提交截至 `bd7a69d0f`。相对 `origin/main` 的 PR 差异为 477 个目标 z 文件、范围外 0 个，本地工作树干净。远端 `fix/pony-z1-z21-layout` 已核对为 `bd7a69d0f`，公司仓库 [草稿 PR #1657](https://github.com/shuoqiudi/cms-sport-tpl-bing/pull/1657) 已建立，等待 code review；尚未合并或部署。初始全量证据来自 `9415e4893`；此后只有 z1、z4、z11 的输入文件改变，按下述文件哈希重测/复用，其他历史证据不自动继承。

## 已修复

- 保留 HeaderJS/FooterJS、jQuery、ajs.js 动态注入；补齐缺失的模板引用。z1–z21 手机导航、主题、搜索和返回顶部按各自现有结构修复或补齐。新增菜单的链接仍在服务端 HTML 中，无 JS 时保留原导航。
- 修正合法 0 分被真假判断吞掉、直播显示固定 `VS`、z16 手机赛程用 CSS 伪元素覆盖真实比分；区分缺分、未开赛与实际 0 分。z16 的 320px 赛程截图见 `runs/z16-score-320-wrap-20260919/`。
- 删除已定位的虚构比赛、主播热度和占位统计，空数据显示明确空态。z14 首页焦点无数据时不再虚构利物浦对曼城比赛。
- z7 焦点轮播不再对进行中的比赛写“即将上演”，队名用 DOM 文本节点更新，避免把数据拼进 `innerHTML`；切换到第二场的实际页面截图在 `runs/z7-hero-current-20260919/z7-hero-next.png`。
- 修正球员详情和轮播的重复 H1、球队数据及部分首页/足球频道缺 H1、z4 主内容语义结构、伪链接等；每套首页在真实原始响应中有正文、有效入口、title/description/keywords 和一个 H1。
- 球队转会页从复制的球队介绍 TDK 改为对应转会主题的动态字段；联赛积分榜与排行榜的 URL/canonical 关系留待业务确认。
- 修正已复现的 z4、z5、z6、z7、z14、z18、z19、z20 移动端比分、队名、头部与组件布局问题。
- 逐张明暗截图又修正 z11 亮色横幅标题、z17/z20 暗色比分对比、z17 PC 焦点按钮与轮播点重叠、z18 PC 首个导航项被裁掉、z21 PC 导航被旧位移挤掉。当前修复后的局部复测分别见 `runs/z11-contrast-20260919/`、`runs/z17-dark-score-20260919/`、`runs/z17-pc-dots-20260919/`、`runs/z20-dark-score-20260919/`、`runs/z18-pc-nav2-20260919/` 和 `runs/z21-desktop-nav-20260919/`。
- 21 套 `detail_zb.html` 已改为明确判断比分字段是否存在，避免数值 `0` 被 Jinja 真值判断吞掉；z1、z4、z5 亮色比分横幅恢复队名/时间对比，z1 手机横幅改为对称三列。局部证据见 `runs/z-detail-contrast-zero-20260919/`、`runs/z1-detail-layout-20260919/`、`runs/z4-detail-time-contrast-20260919/`；z11 非首页菜单/搜索与 z19 暗色面包屑的复测分别见 `runs/z11-inner-nav-20260919/`、`runs/z19-dark-crumb-20260919/`。
- 本轮首屏看图又修正 z11 亮色首页横幅的标签/队名对比，以及 z4 暗色直播详情“本场密报”正文与标签的深字残留。z1、z4 详情的旧倒计时会将格式化字符串与 0 比较；现仅在开赛时间有效且仍在未来时显示，已开赛的真实页面不再显示空倒计时。局部复测见 `runs/z11-home-contrast-final2-20260919/`、`runs/z4-detail-qb-final2-20260919/`、`runs/z-detail-countdown-final2-20260919/`。
- z4 首页在 320px 时主推卡按钮被截断；窄屏让更新时间与按钮换行。主推卡原先有嵌套 `<a>`，现拆为独立比赛/联赛链接；合法数值 `0` 的主推比分不再回退成 `VS`。真实 320/390/1280 截图见 `runs/z4-hero-320-final2-20260919/`，0 分夹具见 `tests/test_z_score_contract.py`。

## 证据等级

| 项目 | 已有证据 | 状态边界 |
|---|---|---|
| 工具与静态检查 | Playwright CLI `0.1.20`；当前源码外部 `unittest` 75 项通过；2,238 个 z Jinja 文件解析通过；PR 差异空白检查通过 | 工具可运行、夹具通过 |
| 原始首页 | `runs/z-raw-home-final-9415e-20260919/`：21/21 个真实首页 HTTP 200，head 字段非空，main 和 H1 存在；本轮 z1/z4/z11 见 `runs/z-raw-home-final-d6cb2-20260919/`，最终 z4 再见 `runs/z-raw-home-final-bd7a6-20260919/` | 只验证一套本地站点配置；不证明生产 TDK 或收录 |
| 可达页面首轮 | `runs/z-review-final-9415e-20260919/`：基线 21 套、1,693 条记录，自动几何 fail 0，blocked 617，needs_review 1,076；当时 21 套输入哈希均匹配 | Chromium 390/1280、真实 light；后续变更页以当前完整矩阵为准 |
| 原始 HTML 规则 | `runs/z-review-final-9415e-20260919/overview.json`：基线 z 模板可达页面确定性规则发现 0；共享 `/play` 单列 blocked；4 组联赛页同标题/双 canonical 待政策复核。21 套首页无误 noindex，21 套搜索页均有 noindex | 后续变更未改 head/索引策略，但仍需正式站点配置与 SEO 复核 |
| 球队转会 TDK | `runs/z-transfer-tdk-20260919/` 与 `runs/z-transfer-extra-20260919/`：21 套真实转会页 HTTP 200，Title/Description/Keywords 均与转会主题一致，Title 不再等于球队介绍；z8–z10 复用了其他模板真实响应里已验证的球队 URL | 21 套当前本地站点配置通过；仍需生产配置复核 |
| 首页功能 | `runs/z-functional-final-9415e-20260919/`：21 套手机菜单、主题刷新与跨搜索页保持、返回顶部、按钮提交 `nba`、Enter 中文和特殊字符提交均实测无异常；变更过的 z1/z4/z11 在 `runs/z-functional-final-d6cb2-20260919/` 重测，最终 z4 又见 `runs/z-functional-final-bd7a6-20260919/` | 任意词搜索仍受后端白名单限制；各内页功能仍需逐页回归 |
| 320px 补充 | 基线 `runs/z-key320-final-9415e-20260919/` 等覆盖 z4/z7/z14/z18/z21 首页、z1 直播详情、z16 足球赛程；本轮 z1/z11 的首页与直播详情见 `runs/z-key320-final-d6cb2-20260919/`，最终 z4 见 `runs/z4-key320-final-bd7a6-20260919/` 与详情独立复测 `runs/z4-detail320-retry-bd7a6-20260919/` | z4 首轮详情亮色一次 `TimeoutError` 保留 blocked 原记录，独立复测 7 项均 needs_review；仍非真机或人工验收 |
| 完整自动矩阵 | `runs/z-full-final-bd7a6-20260919/`：21/21 套、13,944 条记录、逐套输入文件哈希匹配 21/21、规则 fail 0、needs_review 6,792、blocked 7,152。z4 按当前提交重采集，z1/z11 复用 `runs/z-full-final-d6cb2-20260919/`，其余 18 套复用 `runs/z-full-final-9415e-20260919/`；均以证据提交参数及当前输入文件重算哈希。blocked 中 6,900 为无真实文档/样例、252 为共享 `/play`；6,792 个原图链接均存在 | 完整覆盖的自动矩阵汇总，不是 21 套都重新采集；`needs_review`、`blocked` 均不算 PASS |

自动规则的 `needs_review` 不写成 PASS。旧截图/结果在模板、工具或数据改变后必须按输入哈希失效。Firefox/WebKit 的 z2、z3 超长整页截图曾受 32,767px 浏览器限制阻断；工具现按 12,000px 分片保存，独立复测已有 `needs_review` 记录，仍须人工看图。

全量矩阵第一次运行中 z3 的 Windows JSON 原子替换曾遇短暂文件锁；中断前证据保存在 `runs/z3-interrupted-20260919/`。`src/core.py` 现对该锁做有界重试，并有单测；本次完整矩阵仅复用该故障修复后正式完成的旧运行，不借用中断文件。矩阵失败记录已包含规则、页面/视口/主题、预期/实际、严重度、责任层和截图路径。

首屏图像粗复核已逐一查看 21 套首页的手机/PC、明/暗主题及 21 套直播详情的手机明/暗主题，拼图索引在 `runs/z-visual-contact-20260919/`；发现 z4、z11 对比问题后又打开原图、修复并局部重测。拼图是定位工具，不能替代所有内页原图和逐页最终视觉/SEO 复核。

## 待 Leo / Rechard 确认

1. `run.py` 的 `/search` 只对 `list_search_allow` 中的词返回数据。请确认全站搜索正式范围；任意球队、球员或联赛词若需可搜索，由 Rechard 调整后端，模板不伪造接口。
2. `/tags/1` 以及从真实详情页提取的 `/tags/5145`、`/tags/5831`、`/tags/5327` 都返回 HTTP 500；调试页标题为 `TypeError: '<=' not supported between instances of 'str' and 'int'`。`run.py` 的 `tag_list` 在 `recovery_id_offset(id) <= 0` 比较前没有保证整数；当前无偏移配置下该函数返回原字符串。请 Rechard 修复类型处理，并确认无效 ID 应返回 404 还是空态。业务仓库 Python 未改。
3. 已由用户明确：只修各套自己已有页面，不新增缺失的候选页。既有 54 类是路由扫描候选，不是必交数量。已有文件但暂无真实数据/成功样例的页面仍待验证；已有页面指向不存在页面的失效链接仍需处理，不能借范围澄清隐藏故障。
4. `/play/...` 是共享播放路由，返回页缺少 z 模板所需 H1、可读入口及 jQuery/ajs.js。它不能在本次允许目录内修复，请确认归属和页面要求。
5. `/yingchao/jifen` 与 `/yingchao/paihangbang` 在真实响应中标题相同，均为 `index, follow` 且各自 self-canonical。请确认是否同一内容的两个地址及主 URL；暂不自行改 canonical/路由。球队转会页与球队介绍页的重复 TDK 已在模板内拆开。
6. z5 首页显示的重复关键词段落来自 `website_config.Description`，同一动态字段也用于站点描述。应由站点文案/TDK 配置负责人修订源文案；模板未隐藏或替换它来制造通过。
7. z9、z10 首页整屏“进入直播大厅”会遮住主站直到点击。原始 HTML 有主内容，无 JS 会回退显示，但当前交互式首屏只见入口；需 Leo 确认保留该设计还是改为不遮挡主内容的提示。
8. 本地 `robots.txt` 和 `sitemap.xml` HTTP 200（`runs/z-shared-signals-20260919/`），但 URL 均按 `website_config.current_scheme=http` 输出，而 z 模板 canonical 当前写 `https`。先核对正式站点的 scheme/canonical 政策，再决定改站点配置还是模板；不把 localhost 的协议当作生产结论。`robots.txt` 响应头目前为 `text/html`，需 Rechard 确认是否改为 `text/plain`。

## 仍不能宣称完成

五视口 × 双主题、无 JS 及关键 WebKit/Firefox 链路已按当前源码完整运行；搜索之外的筛选/分页、逐页 AI 视觉与 SEO 复核仍未完成。缺少真实路由样例的页面不能标通过。草稿 PR 已建立，但公司人工 code review、合并、上站、Bing 抓取或排名均未发生。本轮未触发域名表、TDK 上站、采购或部署。
