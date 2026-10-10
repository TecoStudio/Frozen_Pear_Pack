# AGENTS.md —— 给 AI / 自动化 agent 的入口

Frozen Pear Pack（冻梨子材质）是一个 Minecraft Java 版资源包仓库。
**版本管理方式：每个 MC 版本一条 git 分支** —— `master` = 最新版（手动跟随），
`<版本号>` = 各老版本线（分支名直接用版本号：`1.16.5`、`1.15.2`）。人读的正文在
[`docs/`](docs/README.md)，动手前先看一眼。

## 红线（违反会造成**静默**错误）

1. **不要直接在 `master` 上提交** —— 服务端 `master` 有分支保护，要求走 PR。
   开 `git switch -c <主题>`，提交后开 PR。
2. **不要在两条版本分支之间 merge / rebase** —— 会把 A 版本的路径带进 B 版本，
   **不报错、不冲突**，只是有人发现贴图不生效。跨分支搬改动用
   `git format-patch -1 --stdout` + `git apply --index`，或 `git checkout <分支> -- <路径>`。
3. **不要用 `git add -A`** —— `.gitignore` 里没有构建产物/临时目录，一把梭会把它们提交。
   用 `git add FPP` 或明确路径。
4. **不要改已发布的 tag**；新 tag 必须带 MC 目标：`v<包版本>-<MC目标>`（例 `v8.8-1.16.5`），
   否则两条线会撞车。
5. **改 `FPP/pack.mcmeta` 时连格式号一起核对**（[docs/05](docs/05-pack.mcmeta-与格式号.md)）：
   格式号与该 MC 版本不符 = 游戏里显示"不兼容"，包不加载。
6. **动文件前先核验路径**（[docs/07](docs/07-核验一条分支.md) 的脚本）：资源包是被动覆盖，
   路径错了不报错、只是不生效。

## 做什么 → 读哪篇

| 我要…… | 读 | 关键命令 |
| --- | --- | --- |
| 改一张贴图（可能要多条线同步） | [docs/03](docs/03-日常流程.md) | `git switch -c fix/x <目标分支>` |
| 给新 MC 版本开分支 | [docs/04](docs/04-开一条新版本分支.md) | `git switch -c 1.21.11 master` |
| 查/改格式号与版本号 | [docs/05](docs/05-pack.mcmeta-与格式号.md) | `git show HEAD:FPP/pack.mcmeta` |
| 处理跨版本路径变化 | [docs/06](docs/06-各版本路径变化对照.md) | 见该页"已知的路径变化" + 逐版实测表 |
| 核验一条分支是否真对得上 | [docs/07](docs/07-核验一条分支.md) | `python <docs/07 里那个脚本> 1.16.5` |
| 搞清为什么是分支制 | [docs/01](docs/01-分支模型与纪律.md)、[docs/08](docs/08-迁移记录.md) | — |

## 目录

| 路径 | 说明 |
| --- | --- |
| `FPP/` | **主包**（冻梨子材质）—— 要改的就是这里 |
| `PPP/` | 炫梨子拓展包（PBR），未纳入版本线 |
| `BRP(deprecated)/` | 血梨扩展包，已废弃，别动 |
| `archived/` | 归档 |
| `docs/` | 这套版本管理文档（从 [docs/README](docs/README.md) 开始） |
| `FPP/pack.mcmeta` | 本分支的版本声明（格式号 + 版本号） |

## 当前状态（2026-10-10）

- `master` / `1.16.5`：内容仍为 1.16.5 时代（`pack_format` 6，`version` 还是 `"test"`）。
  **master 待手动带到最新 MC 版本** —— 到时 `pack_format` 与 `version` 一起改。
- `1.15.2`：内容取自 tag v7.0 的源码树（`pack_format` 5，`version` `"v7.0 for MC1.15"`）。
- 其余版本线（1.17.1 / 1.18.2 / 1.19.4 / 1.20.6 / 1.21.11 / 26.x）**尚未创建**。
- `feat/version-lines`（旧的"单主干 + overlay"方案）与它的 PR **已删除**；其中有价值的内容
  已并入 [docs/05](docs/05-pack.mcmeta-与格式号.md)（格式号表）与 [docs/07](docs/07-核验一条分支.md)（核验脚本）。
