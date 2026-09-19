# z16 积分榜标签交互修复与回归（2026-09-20）

用户在 z16 足球入口指出右侧积分榜的英超、西甲、德甲、意甲、法甲标签点击后没有实际内容变化。改动仅涉及业务仓库的 `templates/z16/widgets/football-portal/standings.html`、`static/z16/js/z16-football.js` 和 `static/z16/css/z16-football-portal.css`。其他 z 模板、Python 和共享资源没有因本项修复改变。

## 已核实的数据契约

- 本地 `/zuqiu` 的初始响应提供五个联赛标签及各自的“更多”目标，但五组 `rows` 均为空；`/lanqiu` 的 NBA/CBA 两组也为空。这是当前本地响应的事实，不能用静态假排名声称积分榜有数据。
- `/yingchao` 的联赛专页有真实榜单行；本次修复保留已有数据渲染。
- 足球入口的路由未提供各联赛榜单行。如果要求在入口卡片直接展示排行，需要后端负责人提供该页所需的逐联赛数据；模板不能自行编造或修改 Python。

## 修复与判定

原来的脚本在所有联赛行为空时寻找不存在的 `window.Z16_FP_MOCK`，切换只改变选中样式；页面还保留服务端的“第1名 —”占位行。现在每个标签从服务端配置读取联赛名称、行与目标链接：有行时显示对应行，无行时显示对应联赛的“暂无…积分榜数据”；“更多”链接也随标签切换。无 JS 的首个标签初始 HTML 同样显示明确空态。篮球入口沿用同一行为，显示“排行榜”空态。

复跑命令（先保证本地 z16 预览运行、外部虚拟环境及 Playwright CLI 0.1.20 可用）：

```powershell
cd C:\tyseo\pony-template-workflow
.\.venv\Scripts\python.exe src\z16_football_tabs_regression.py --output runs\z16-football-tabs-<new-run-id>
```

本次真实运行证据在 `runs/z16-football-tabs-final-20260920/`（本机生成，不提交运行缓存）：`summary.json`、`result.json`、`raw-summary.json`、`http/`、`findings.json` 和逐状态截图。原始 HTTP 检查 `/zuqiu`、`/lanqiu`、`/yingchao` 共 3 页；浏览器覆盖 390/768/1280/1920 CSS px × light/dark × 足球 5、篮球 2、英超专页 1 共 64 个标签状态，64/64 通过，失败 0。检查了选中状态、可见内容/空态、对应链接、页面溢出和西甲“更多”实际点击到 `/xijia/jifen`（HTTP 200）。390 与 1280 的明暗截图已生成；本次人工查看了暗色手机与桌面截图，未见卡片内容相互遮挡。

本项只证明 z16 积分榜标签当前本地交互及真实数据缺失时的回退。它不证明榜单数据已由后端提供，也不代替 z1–z17 的政策 2.4 全页回归、公司人工验收或线上验证。后续任一模板、配置或输入变化须重新运行，不能沿用旧 PASS。
