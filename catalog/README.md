# Pony 模板参考库

用于后续每周四套整站模板制作的本地检索入口。当前是**全量源码索引与组件候选库**，不是已经验证可任意拼装的成品组件库。

首次扫描完成：**943套 / 18系列 / 70,491文件 / 6,008组件候选文件**。[范围及验证结果](SCAN_RESULT.md)。

- [全量模板目录](source-inventory/TEMPLATES.md)：所有本地编号模板，逐套计数与功能线索。
- [机器可读清单](source-inventory/templates.json)：页面/组件文件、依赖、证据行号、文件 SHA256、Git 基线。
- [x66–x80 参考](source-inventory/X66-X80.md)：Sit 指定参考范围的首页结构、网格与组件路径。
- [制作与组件入库规则](../docs/PONY_TEMPLATE_LIBRARY.md)：四套差异化、SEO/代码边界、验收和后续交付。

在本工作区执行刷新（只读业务源码；默认输出到本目录下）：

```powershell
.\.venv\Scripts\python.exe scripts/scan_template_catalog.py --self-test
.\.venv\Scripts\python.exe scripts/scan_template_catalog.py
```

每次开工刷新目录。只扫描当前 checkout，不自动 pull/切分支；未提交修改会进入快照。目录中静态线索不存在，不足以认定功能缺失；存在也不证明功能可用。共享依赖、动态 include、继承关系与后端数据需要目标模板专项审计。并行编辑期间的扫描非原子，正式开发前重验所用文件哈希。
