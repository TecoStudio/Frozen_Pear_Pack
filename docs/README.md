# 文档索引（FPP 多版本线）

一个材质包要同时跟上多个 Minecraft 大版本（1.16.5 / 1.17.1 / … / 1.21.11 / 26.3）。
这套文档说明本项目采用的方案、日常命令、发布规范，以及"怎么保证不会误推到 main"。

> 给 AI / 自动化 agent 的入口是仓库根目录的 [AGENTS.md](../AGENTS.md)（红线 + 路由）；
> 这里是人读的正文。

**一句话结论：版本维度放在构建产物和 overlay 覆盖层里，不放长期分支。**
一条主干（`master`）+ 每线一个差异目录 + 构建脚本生成 `pack.mcmeta`；
分支只用于短期主题工作，老版本线用 tag / Release 冻结。

## 该读哪篇

| 我想…… | 读 |
| --- | --- |
| 知道方案为什么这么定、目录长什么样 | [01-方案与目录约定](01-方案与目录约定.md) |
| 知道敲什么命令、产物在哪、为什么可校验 | [02-命令与产物](02-命令与产物.md) |
| 查版本线清单 / `pack_format` / `pack.mcmeta` 的两种写法 | [03-版本线与格式号](03-版本线与格式号.md) |
| 知道哪些文件在新版本下其实**不生效**（哪些要补 overlay） | [04-路径兼容性审计](04-路径兼容性审计.md) |
| 加一条新的 MC 版本线 | [05-新增版本线](05-新增版本线.md) |
| 发版 / 打 tag / 命名规范 | [06-发布规范](06-发布规范.md) |
| 改一张贴图该改哪里、要不要 backport、要不要 checkout 旧版本 | [07-改动与-backport](07-改动与-backport.md) |
| 确保自己不会误推到 main | [08-防误推-main](08-防误推-main.md) |

## 真值来源

文档会和代码慢慢漂移，**以这些为准**：

| 内容 | 真值在哪 |
| --- | --- |
| 有哪些版本线、包版本、格式号、冻结状态 | [`FPP/build.json`](../FPP/build.json) |
| 各 MC 版本的原版到底读哪些路径 | 官方 client jar（[`tools/audit.py`](../tools/audit.py) 自动取用） |
| 构建/打包行为 | [`tools/build.py`](../tools/build.py)（`--help`） |
| CI 矩阵与发版 | [`.github/workflows/autobuild.yml`](../.github/workflows/autobuild.yml) |
| 目录内的 overlay 放什么 | [`FPP/overlays/README.md`](../FPP/overlays/README.md) |
