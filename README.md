# Pony · 体育Bing SEO整站模板工作流需求包 v2.0

**日期：2026-09-18。** 这是供Codex实施的需求包，不是已经开发完成的模板生成器。

## 适配的真实工作

现有项目 `cms-sport-tpl-bing` 使用Python/Jinja，用户本地环境已跑通。每两天制作一套完整体育站模板，一套约十几个页面。主目标为Bing SEO，且必须实现RWD、dark/light、search、goto top、手机导航、逐页视觉和SEO检查。

业务代码只允许改目标模板的 `templates/{id}`、`static/{id}`。现有每日域名工作流维持两步，不扩展TDK、采购、部署或定时任务。

## 使用方法

将整个包放到公司业务仓库之外的独立本地目录，例如 `C:/tyseo/pony-template-workflow/`。让Codex读取 `CODEX_START.md` 中“首次实施提示词”，按PRD实施。

不要把本包AGENTS.md覆盖到公司仓库根目录，也不要把config/rules.json当成已经实现的检查器。

## 文件

| 文件 | 用途 |
|---|---|
| PRD.md | 完整需求总纲：业务、边界、契约、设计、功能、体育专项、Bing SEO、验收和实施阶段。 |
| AGENTS.md | 外部工作流使用的长期Codex指令。 |
| CODEX_START.md | 首次实施、新模板、反馈修复提示词。 |
| docs/ACCEPTANCE.md | 需求追踪、必须检出的失败用例、交付判定。 |
| config/task.example.json | 初建工作流任务示例；没有擅自填写目标编号。 |
| schemas/task.schema.json | 示例任务的机器可校验结构；路径/编号/来源约束仍需程序实现。 |
| config/rules.json | 声明式验收规则目录；不是执行引擎。 |
| PACKAGE_CHECK.md | 本需求包的文件一致性验证范围，不是业务项目测试结果。 |

## 当前事实边界

方案依据用户完整聊天和既有Codex执行记录。GitHub连接器读取目标仓库返回404，公开r62示例站也未取得可用内容。因此具体文件名、Jinja变量、真实搜索接口和页面清单由Codex首先在本地审计，不在本包编造。

此次不访问或更改域名表，不执行采购或上线，不修改公司仓库。旧的通用HTML生成器方案作为历史参考，本版优先适用于已经确认的Python/Jinja项目。

## 本地实施入口（2026-09-18 更新）

本包现已有部分本地实现；完整状态见 `docs/IMPLEMENTATION_STATUS.md`，操作流水线见 `docs/WORKFLOWS.md`。原PRD和PACKAGE_CHECK继续保留为需求来源，不当作执行结果。

运行 `./.venv/Scripts/python.exe pipeline.py list` 查看已实现/部分实现/禁用的任务类型。当前优先级为 z1–z21 只读检查，尚非全套生产验收；报告在 runs/，没有推送。

## 半自动验收与换机

当前有效增量规范：`docs/ACCEPTANCE_INCREMENT.md`；本轮实现/未完成状态：`docs/HARDENING_RESULT.md`。CLI以0.1.20为准，保留原Python Playwright验收入口。未来RS助手机器人接入保持关闭。

跨机器初始化使用 `Initialize.ps1`；敏感配置/运行数据为 `migration/` 中加密分片，解密密钥须单独转移，详情见 `docs/MIGRATION.md`。本库不镜像公司业务仓库；加密数据保留外部草稿及其中的参考模板/资源副本。
