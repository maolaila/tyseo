# 临时任务记录

## 2026-09-19 最新范围澄清

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

