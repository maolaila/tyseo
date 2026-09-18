# 临时任务记录

z1–z21 检查与修复是团队临时插入任务，不属于每日固定工作流，也不是上站后的必做步骤。
临时任务按用户/团队当次明确安排执行；没有自动触发器。修复仍未完成，不能因移出流程而写成取消或完成。

2026-09-19 当前代码、可重复验收入口与阻断项见 [Z_SERIES_REPAIR_20260919.md](Z_SERIES_REPAIR_20260919.md)。新版命令可选择已审计页面类型与视口，输出仍留在外部 `runs/`：

```powershell
.\.venv\Scripts\python.exe src\z_review.py --output runs/z-review-next
.\.venv\Scripts\python.exe src\z_acceptance.py --contract-run runs/z-review-next --page-types index --output runs/z-home-next
.\.venv\Scripts\python.exe src\z_raw_home.py --output runs/z-raw-home-next
.\.venv\Scripts\python.exe src\z_report.py --run runs/z-review-next
```

这些步骤只是本地检查。源码变更后使用新的 run 目录，不复用旧 `summary.json`；`needs_review`、`blocked`、公司验收和上线分别记录。

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

