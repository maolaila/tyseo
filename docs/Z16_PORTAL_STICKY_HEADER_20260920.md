# z16 门户积分榜滚动表头修复

来源：2026-09-20 用户截图，z16 首页数据中心“积分榜（英超）”局部滚动时，数据行从表头透出，且“排名”“积分”被挤成竖排。截图为需求/缺陷来源，不自动证明其他页面通过。

根因：`static/z16/css/z16.css` 的全局 `body.z16-body table th` 重要声明覆盖了门户表格的原有样式；实际表头背景为 `rgba(255,255,255,.06)`，字号约14.72px、左右内边距各8.8px，首尾列宽仅约37/44px。sticky 表头仍可命中，但滚动行透过半透明背景，首尾标题异常换行。

修复仅在 `static/z16/css/z16-portal-home.css` 给 `body.z16-body.is-portal-home .sl-data__table thead th` 增加更明确的局部规则：沿用明暗主题已有的实色 `--sl-card`，使表头在滚动行之上；设置合适的字号与间距保持标题一行。未改后端、共享表格或其他模板。

政策2.4通过 `scripts/layout-audit.js` 在可见且确实可滚动的 sticky 表格上暂时改变并恢复局部滚动位置；若行与表头相交时背景透明或表头命中层级被盖住，判P1，异常换行标待复核。`tests/test_layout_audit.py` 的透明负例失败、实色正例通过；`scroll_table_header_integrity` 已纳入必需证据键，旧政策2.3结果不自动沿用。

真实应用专项入口：

```powershell
.\.venv\Scripts\python.exe src/z16_portal_header_regression.py --output runs/<新的z16表头目录>
```

本轮 `runs/z16-portal-sticky-final-20260920/summary.json`：Chromium、390/768/1280/1920 CSS px × light/dark × 局部滚动顶/24px/56px/底，共32个状态通过；每个宽度/主题还点击第二个联赛标签，核对标题、行集合及滚动复位，共8次通过。表头背景分别为实色白/深色，32个状态均能由表头接收命中、文字单行、无整页或组件横向溢出。输入源码指纹新鲜，截图在同目录的 `z16-table-{390,1280}-{light,dark}-scrolled.png`。修复前证据 `runs/z16-table-precheck-result.json` 与 `z16-table-before-1280-dark-24.png`；修复后详细结果为专项目录 `result.json` 和 `findings.json`（空）。

这只是 z16 本地组件与交互专项通过；此前 z1–z17 的政策2.3功能报告是历史证据，尚未按2.4做全量重测。未人工主管验收，未提交或推送公司业务代码，未验证线上。
