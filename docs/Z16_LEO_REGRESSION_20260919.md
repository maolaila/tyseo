# z16 球队筛选及赛程跑版回归（2026-09-19）

## 来源与范围

Leo 16:48 报告 z16 球队筛选点击无反应、相关赛程队徽错位；Pony 要求修复并把漏检补成验收硬门槛。Pony 随后明确：对齐方式取决于具体布局，硬门槛是内容被挤占后的非预期跑版，不是所有 Logo/队名/比分必须一线对齐。

业务只改 `templates/z16/team_info.html`、`templates/z16/team_match_list.html`、`static/z16/css/z16-layout.css`、`static/z16/css/z16-league-hub.css`。没有修改 Python、共享文件、其他模板或环境配置。

业务提交 `b48fd04e2` 已推送 `fix/pony-z1-z17-layout`，沿用草稿 PR #1664；未合并main。测试时四个业务文件的SHA-256保存在本地 `runs/z16-leo-regression-20260919/tested-files.json`，提交后核对文件内容不变。

## 复现与修复

- 球队资料的“比赛”标签选择英超＋主场：期望17行，修复前实际41行。JS设置普通 `display:none` 被 `display:grid !important` 覆盖，按钮高亮却没有过滤数据。改为真正生效的隐藏/恢复，查询限制在本筛选区域，补充空结果提示。独立赛程页同步修复，避免日期分组遮掩单行隐藏失效。
- 详情关联赛程桌面五列采用 `display:contents`，主队Logo先于队名出现在DOM；只有列号没有行号，自动网格产生了非预期第二行。按该组件原设计补齐槽位，长队名限制在自己槽位内。
- 手机端本来是队徽在队名上方、主客队位于比分两侧。补齐这三个布局槽位，并把联赛皮肤里覆盖手机的桌面五列规则限定到961px及以上。没有把桌面横排强加给手机。

Leo 提供的 `http://127.0.0.1:5500/aoweichao/4653594.html` 在本机5500端口无服务；6316同一路径返回404。证据不声称这条原始地址已成功打开。真实复测使用已有页面契约中的 `/yingchao/teams/teaminfo-10012.html`、`/yingchao/teams/10012.html`、`/ajia/4539770.html`，复现同一模板组件。

## 可执行验收

政策升为2.2：`filter_results`、`layout_integrity` 都是验收器必需证据键；缺项、fail、blocked或旧政策均不能放行。首页控件测试不能替代内页。不存在该模块才允许有证据地N/A。布局规则须服从组件设计和实际断点，禁止不加区分的通用“Logo对齐”断言。

复跑入口（外部工作区）：

```powershell
.\.venv\Scripts\python.exe src/z16_leo_regression.py --browser chrome --output runs/<新的目录>
.\.venv\Scripts\python.exe src/z16_leo_regression.py --browser firefox --output runs/<另一个新目录>
.\.venv\Scripts\python.exe src/z16_leo_regression.py --browser webkit --output runs/<再一个新目录>
```

使用 Playwright CLI 0.1.20。真实筛选比对可见ID集合，不只比条数/颜色/inline style；覆盖赛事×主客组合、恢复全部、空结果、日期分组。逐行检查组件槽位、容器边界、非预期重叠与跑版。宽度320/360/390/768/959/960/961/1280/1920，light/dark；长队名、三位数比分、零比分、缺图及坏图仅作外部夹具，不写业务数据。

## 实际结果

- CLI Chrome、Firefox、WebKit：每个引擎144个状态通过（54 real_app、90 fixture），各432次筛选组合、36次空结果、36次恢复、2,106次可见赛程行布局检查。三个引擎均能拦住旧筛选写法、桌面自动掉行、手机槽位覆盖三个负向对照。`source_fresh=true`。
- 87项工具测试通过，包含新证据键缺失/失败时拒绝放行的测试。
- z16全页矩阵：36个实际页面类型，656条计划记录；463 needs_review、128 blocked、65 fail（均为 `LAYOUT-LAB-CLS`）。这不是z16全部验收通过，更不是其他16套已经通过2.2。中途源码变化的旧矩阵不复用。
- 关键截图已查看，手机/桌面均按各自结构呈现；源截图问题的专项检查通过。剩余样例缺失和加载跳动保留，不用本次功能修复抹掉。

本地证据：`runs/z16-leo-cli-{chrome,firefox,webkit}-20260919/result.json`、`findings.json`、截图及原始HTTP；`runs/z16-leo-regression-20260919/diagnose-info.log`记录41对17的修复前结果；`runs/z16-leo-final-matrix-20260919/`为当前完整矩阵。

## CLI浏览器安装

用户明确要求补齐CLI浏览器。已安装CLI Firefox 155.0（build1544）及WebKit 26.6（build2361），并由上述完整CLI回归验证能实际启动与操作页面。CLI保持0.1.20；现有Python Playwright的Chromium/Firefox/WebKit也再次实际启动成功。

`Initialize.ps1`补上CLI独立浏览器包安装和空白页启动检查，防止只安装Python浏览器而误报CLI就绪。初始化脚本语法检查通过；本次没有重跑整个依赖安装/私有数据恢复流程。浏览器安装包保存在用户缓存，不提交到Git；安装方式见 `docs/MIGRATION.md`。
