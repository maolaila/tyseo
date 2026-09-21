# Claude Code 交接：Pony 上站工作流与 z1 / z18

## 两个独立仓库

- 工作流：`C:/tyseo/pony-template-workflow`，远程 `maolaila/tyseo`，负责域名、TDK、模板目录、验收工具和本地证据。
- 业务项目：`C:/tyseo/cms-sport-tpl-bing`，远程 `shuoqiudi/cms-sport-tpl-bing`，实际模板代码只按当次授权修改 `templates/<id>/`、`static/<id>/`。
- 两仓库的 `AGENTS.md` 都要读；不要把工作流工具或证据放进业务仓库。

## 今日上站批次

- 默认数量：用户未另说时每天 20 个新域名；词未更新时沿用前一天有效分配词。
- 2026-09-21 的 20 个 `.com` 已写“域名待购买” A160:C179 并回读。证据在本机被 Git 忽略的 `runs/site-launch/2026-09-21-pony-20/`。
- 20 个域名经 Verisign RDAP 初查无记录，Dynadot 当时均显示 available、$10.88 USD；采购前仍实时复核。Gname 有验证限制。
- TDK 草稿已生成并查重，文件 `runs/site-launch/2026-09-21-pony-20/tdk-drafts.json`。用户本批选 `z1`，但域名尚未以 2026-09-21、归属 Pony 出现在 Bing 上站表，所以未写 E:H。
- 购买完成只以上站表对应日期、Pony、域名、分配词唯一匹配为准，不看待购买表是否删除。
- 上站模板不固定 r62。每批从 `bing 指数词汇总` 的 `bing体育品牌词` 页读取 Pony 当前可用模板范围；2026-09-21 快照 M17=`z1~z17`，必须写表前重读。旁边 `z、d、t、k` 是另一分组。
- 填 TDK 前参考指数词表相关体育页签、Leo 历史相近 TDK、当次 Bing 竞品和目标模板实际能力；文案必须本批/历史逐字段唯一。
- 上站表只写本人行 E:H，回读并确认 A:D/I:P 未变。之后用户手动复制上站。机器人尚未接入。
- 未来机器人自动上站前，逐行核对 M 列 `ServerName` 与后台主机；`s213017` 只是候选，不能硬编码。

## z1 上站前复查

- 业务分支：`fix/pony-z1-z17-layout`；草稿 PR：`https://github.com/shuoqiudi/cms-sport-tpl-bing/pull/1664`。
- 已推提交：`31eb1cba8`（手机排行、主题文字、资料卡、H1）和 `f0c3489d4`（首页预留侧栏，解决冷启动 CLS）。远程分支 SHA 已核对；未合并 main、未部署。
- 提交后证据：`runs/z1-prelaunch-grid-pushed-20260921/`。30 个真实 HTTP 200 页面、60 个浏览器状态、71 个已执行断言通过，`source_fresh=true`；原始 SEO 90 pass / 90 needs_review / 0 fail。
- 首页 320/360/390/768/1024/1025/1280/1920 × 明暗主题共 16 状态无溢出，最大本地 CLS 约 0.000033。Firefox/WebKit 和全页无 JS 的补充证据在同日 run 目录。
- 整套仍为 `blocked`：`/tags/1`、`/tags/5327`、`/tag/1-1.html` 在 z1/z2/z16 都 500，需 Rechard 查共享标签数据链路；`hot_tag_detail_pinyin` 无可靠样例。生产 canonical、索引、视频播放、部署和排名未验证。
- 本地并行测试曾使首页短暂返回一次 500，隔离请求和重测恢复；保留为预览环境稳定性观察。

## z18 每周模板开发

- 用户专属开发编号固定为 `z18`；不用其他模板编号。每周在 z18 下交付四个尽量不同的整站设计版本。
- 每版基于刷新后的模板库选择适配组件并加入新布局/样式，逐页验收后独立提交和推送；不能仅换色。一个提交只有一个当前 z18 状态，旧版由 Git 历史追溯。
- 只改 `templates/z18/`、`static/z18/`。已有 `origin/feat/dev-z18` 是 devk 旧分支，不接管；新开发另建 Pony 分支。
- 当前目录已刷新为 944 套、70,608 文件、6,035 个源码候选；这些仍是 `source_only`，复用前核对真实路由、数据和浏览器效果。
- 本轮尚未开始修改 z18 业务代码。

## 关键命令

```powershell
cd C:\tyseo\pony-template-workflow
.\.venv\Scripts\python.exe scripts\scan_template_catalog.py --self-test
.\.venv\Scripts\python.exe src\final_user_journeys.py --ids z1 --contracts runs\z1-prelaunch-contract-20260921 --output runs\<new-run>
.\.venv\Scripts\python.exe src\final_raw_seo_report.py --run runs\<new-run>
.\.venv\Scripts\python.exe src\final_nojs_check.py --run runs\<new-run>
.\.venv\Scripts\python.exe src\final_user_report.py --run runs\<new-run>
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
```

不要把旧截图、工具退出码、fixture 或本地 HTTP 200 说成上线、Bing 收录、排名或公司验收。任何源码、配置、规则或数据变化都会使旧证据失效。
