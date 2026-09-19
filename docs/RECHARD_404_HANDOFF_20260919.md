# z1–z17 本地404待确认清单

来源：2026-09-19 本轮当前源码的原始 HTTP 链接复查，`runs/z-functional-http-current-20260919/findings.json`；z11–z17 筛选修改后的局部复查 `runs/z-functional-links-z11-17-filter-final-20260919/findings.json`。所有条目在本地 HEAD 重试仍为404。模板编号只指实际输出此链接的预览，不意味着源数据或后端归该模板负责。线上未核验。最新浏览器合并报告 `runs/z-functional-v23-final-current-20260919/summary.json` 覆盖886/886个当前可访问样例的两档宽度状态，动态导航**没有新增404**；旧过期证据不计入。

|模板|来源页|点击目标|本地状态|
|---|---|---|---|
|z12|`/dejia`|`/dejia/jijin/765620.html`|404|
|z12|`/dejia`|`/dejia/jijin/765619.html`|404|
|z12|`/dejia`|`/dejia/jijin/765618.html`|404|
|z12|`/dejia`|`/dejia/jijin/765617.html`|404|
|z12|`/dejia`|`/dejia/jijin/765616.html`|404|
|z17|`/`|`/ouguanbei/teams/teaminfo-11343.html`|404|
|z17|`/`|`/ouguanbei/teams/teaminfo-10217.html`|404|
|z17|`/`|`/ouguanbei/teams/teaminfo-10692.html`|404|

请 Rechard 分别确认这两组数据的实际页面路由与记录是否有效；若数据已失效，请给出应隐藏的字段条件；若路由已迁移，请给对应的正式地址规则。未确认前不猜路径、不改后端、不批量套用某个替换。此前 `/oulianbei`→`/oulian` 是19:14明确确认的改名特例，z5–z11本地已回读新链接200；19:15 Rechard已说明改名情况少，不能外推到本表。

另需后端核对但不属于404清单：本地 `/tags/{id}` 的500（用户先前说本地先不处理）；z7阿森纳转会页点击“签约”实际请求 `/yingchao/teams/transfer-10215/2026-2027/1_7.html` 返回500；共享 `/play` 有加载及控件阻断。其余波动500/超时见 `runs/z-functional-http-current-20260919/retry-findings.json`。本地异常不能自动当成线上异常。
