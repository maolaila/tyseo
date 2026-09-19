# 临时任务记录

## 2026-09-19 最新范围澄清

最新分支状态：用户要求将 `fix/pony-z1-z21-layout` 更名为 `fix/pony-z1-z17-layout`。业务远端新分支仍指向 `4a8c72ac8`，旧分支已删除；新的草稿 [PR #1664](https://github.com/shuoqiudi/cms-sport-tpl-bing/pull/1664) 指向 main，旧 [PR #1657](https://github.com/shuoqiudi/cms-sport-tpl-bing/pull/1657) 标注被替代并关闭，均未合并。以下旧分支/PR叙述仅记录更名前的历史状态。

用户在政策2.1复查运行中进一步明确：先完成 z1–z17 本地工具复查和修复，交付预览入口、证据及遗留问题供本人逐页人工验收；只有用户完成验收并再次通知后，才提交/推送本轮业务代码和更新 PR。现有草稿 PR #1657 不等于本轮已交付，验收前不得合并 main。该顺序优先于此前“完成后立即推送”的一般流程。

用户随后表示人工查看没有其他问题，明确授权提交并推送。业务修复已分别提交 `d1dd66f5f`（z1–z17 手机布局）和 `4a8c72ac8`（z10 录像标题换行），现由 `origin/fix/pony-z1-z17-layout` 指向同一 `HEAD`。实际本轮改动仅涉及 z1–z17；PR #1664 用于 code review，未经 review 不合并 main。用户认可人工排版不等于剩余自动 CLS/blocked 已消失。

本轮政策2.1的工具采集已完成：17/17 套、10,624 个计划场景且测试时源码文件哈希全部匹配；用户补充 z10 录像标题修复并重跑后，自动状态为 432 fail、2,449 blocked、7,743 needs_review，因此仍未通过全部自动门槛。修复前同计划的自动 fail 为1,847。Playwright CLI 0.1.20 的17套首页功能链路和工具单元测试86项通过；独立手机APP条聚焦检查34/34通过。完整本地证据、已知阻断及人工优先查看顺序见 `runs/z-policy21-final-report-20260919/REVIEW.md`，截图索引见同目录 `matrix/matrix-screenshots.html`。人工入口 `http://127.0.0.1:8771/`；人工查看确认后已提交推送，PR #1664 保持草稿等待 code review。

本轮v2复查中，用户针对“本地17套 `/tags/1` HTTP 500”明确要求“本地的先不管”。仅该本地问题暂缓，不修后端、不计作当前样式任务的待处理阻断；原始观察保留且不标pass。其他z1–z17已有页面布局检查范围保留。具体运行记录见 `runs/z-v2-recheck-20260919/scope-steering.json`。

随后用户明确只需日常样式＋轻微压力，刻意放大不用管。已停止旧政策2.0的三个采集批次，保存 `runs/z-v2-recheck-20260919/matrix-current` 原始证据，不删除旧发现，不改写为PASS。政策2.1由现有规划器与执行器共同读取，关闭200%字号及强制字距/行距。此次中断的z1–z17全量复查尚未完成；下一次执行使用新run目录，不将旧hash结果冒充新政策验收。正常场景发现（如APP条遮挡、布局跳动）仍有效待处理，只有人工放大/间距引发的发现退出当前放行门槛。

用户最终明确只允许 z1–z17，其他模板的本次修改全部撤回。业务提交 `c223e6925` 已撤回z18–z21的131文件改动；PR剩346文件，范围外0。外部z检查入口和断言范围已改为z1–z17，断言内容未放宽；76项工具测试通过。历史z1–z21证据保留，检查工具输入已变更，不将旧矩阵自动升级为当前PASS。

用户明确：只修各套自己已有的页面。随后转发 Leo 10:11–10:12 的上下文，重点为 z1–z17 各页面的跑版等样式问题。不存在的候选入口不要求补页；已有页面的严重布局问题、不可用链接、缺数据/后端异常仍单独记录。原 54 类候选入口不是每套必交页面。

草稿 PR #1657 已撤回 z18–z21；z1–z17 仍保留前阶段功能、SEO和数据绑定修改，尚不能描述为纯样式补丁。用户要求先启动本地模板逐页人工复查：执行 `./Start-Z-Preview.ps1`，入口 `http://127.0.0.1:8771/`，z1–z17 使用 6301–6317 端口和原业务项目，只在进程环境中选择模板，不修改 `.env`。该入口展示当前修复分支，尚未经过人工验收。

Rechard 10:09–10:10 建议按上站表模板编号找到线上域名，先核对真实页面。8月表 gid=408602878；9月表 gid=2066853497。历史模板记录可能已变更，必须核对实际 `/static/{id}/` 资源再作对比。真实线上结果与本地观察分开，AI候选路由与真实页面链接分开。

z1–z21 检查与修复是团队临时插入任务，不属于每日固定工作流，也不是上站后的必做步骤。
临时任务按用户/团队当次明确安排执行；没有自动触发器。修复仍未完成，不能因移出流程而写成取消或完成。

2026-09-19 当前代码、可重复验收入口与阻断项见 [Z_SERIES_REPAIR_20260919.md](Z_SERIES_REPAIR_20260919.md)。新版命令可选择已审计页面类型与视口，输出仍留在外部 `runs/`：

```powershell
.\.venv\Scripts\python.exe src\z_review.py --output runs/z-review-next
.\.venv\Scripts\python.exe src\z_acceptance.py --contract-run runs/z-review-next --page-types index --output runs/z-home-next
.\.venv\Scripts\python.exe src\z_acceptance.py --contract-run runs/z-review-next --output runs/z-full-next
.\.venv\Scripts\python.exe src\z_raw_home.py --output runs/z-raw-home-next
.\.venv\Scripts\python.exe src\z_report.py --run runs/z-review-next
.\.venv\Scripts\python.exe src\z_matrix_report.py --run runs/z-full-next --contract-run runs/z-review-next
```

这些步骤只是本地检查。源码变更后使用新的 run 目录，不在原目录覆盖旧 `summary.json`；`needs_review`、`blocked`、公司验收和上线分别记录。若只改了个别模板，可仅重采集这些模板，再用 `z_matrix_report.py --reuse-run <旧完整矩阵> --reuse-commit <旧提交 SHA>` 汇总；多轮证据可重复传入成对的 `--reuse-run`、`--reuse-commit`。工具会对每套旧结果以旧提交参数和**当前输入文件**重算哈希；不匹配的模板保持未完成，不能借复用跳过测试。共享输入、配置或浏览器检查脚本变化时，需要重跑所有受影响模板。

## A. z 系列已有模板检查（历史首轮采集）

依据：Leo 11:56 要先修 z 系列，11:58 明确 z1–z21 全部看一轮，不确定的再沟通。

| 阶段 | 具体操作 | 产物与完成条件 |
|---|---|---|
| 盘点 | 静态模板/资源/必保留注入点检查 | `runs/z-inventory/`；仅静态线索，不当作已复现缺陷 |
| 预览 | 原业务 Python 启动独立本地进程，环境覆盖 DEV_MasterID/FLASK_PORT；不写 .env | 真实响应中的目标资源作为切换证据；进程退出后回收自己的进程树 |
| 页面发现 | 真实 run.py AST 路由+Jinja依赖+有界链接发现 | 每套 page-contract、raw-responses；缺样例保持 blocked |
| 第一轮页面检查 | Chromium，390/1280、light，截图/脚本错误/页面溢出/比分出界 | 每页 visual-results、全页图和视口图；无自动断言错误也仅 needs_review |
| 复核与分级 | AI看图、区分静态疑点/实际复现/后端错误 | 复现 URL、截图、预期/实际、责任层；不确定项交用户 |
| 后续修复 | 仅明确目标的 templates/zN 与 static/zN；先复现再最小修改 | 修复前后证据、组件全量回归；这一步不是当前只读入口自动执行的动作 |

```powershell
.\.venv\Scripts\python.exe pipeline.py task z-review
```

这是第一轮检查入口，不是完整主题、无JS、功能和上线验收入口。保留各套的 blocked 页面分母。恢复前必须检查源码未变；已有记录不能跨源码版本沿用。

### 重新跑检查

首次 z-review 的早期记录产生于源码哈希恢复门禁补强前。新版入口遇到没有匹配 input_hash 的旧记录会拒绝复用，这是正常保护，不应手填哈希绕过。需要新一轮时保留旧目录，并运行：

```powershell
.\.venv\Scripts\python.exe src/z_review.py --output runs/z-review-next
```

后续正式任务应使用独立run目录和目标范围配置，不把旧PASS跨版本继承。

