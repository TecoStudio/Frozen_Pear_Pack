# AGENTS.md —— 版本管理的路由入口

**这个仓库的版本管理只有一个真值来源：[VERSIONS.md](VERSIONS.md)。**
任何与"Minecraft 版本"相关的工作，先读它；本文件只负责路由和红线提醒，不重复其内容。

> 文件名用大写 `AGENTS.md`（Codex / DSH / 多数编码 agent 的约定名），内容与用户口中
> 的 "agents.md" 一致。

---

## 30 秒理解这个仓库

- Minecraft Java 版 16x 材质包，按**每个 MC 大版本的最终补丁**维护多条**版本线**：
  `1.16.5` / `1.17.1` / `1.18.2` / `1.19.4` / `1.20.6` / `1.21.11` / `26.1.2` / `26.2` / `26.3`
  （格式号与核实来源见 [FPP/build.json](FPP/build.json) 每条线的 `notes`）
- 版本维度**不在 git 分支里**，而在：`FPP/build.json`（线定义）+ `FPP/overlays/<线>/`（差异层）
  + 构建产物。跨版本共享的贴图放主体 `FPP/`，只有该版本确实不同的文件才进对应 overlay。
- `FPP/overlays/<线>/` **可以为空**。空 = 该线与主体完全相同 —— 这是常态，不是遗漏：
  历史上 `1.16.5/FPP` 与 `1.17.1/FPP` 的 2723 个文件曾 100% 相同，唯一差别是 pack.mcmeta 的
  `pack_format`(6/7)。正因如此才放弃"每版本一分支/一目录"。
- 三个包：`FPP`（主包，已接入版本线系统）、`PPP`（PBR 扩展，**未接入**）、
  `BRP(deprecated)`（已废弃，不要动）。

---

## 红线（违反会破坏发布一致性）

1. **不要提交或推送到 `master`。** 一律 `git switch -c <线>/<主题>` 后工作，再走 PR。
   本地有 `.githooks/` 拦截，服务端两个仓库都有分支保护（管理员同样受限）；
   需要单次放行时才用 `ALLOW_MAIN=1`。
2. **不要手写、不要提交 `pack.mcmeta`。** `pack_format`（1.21.9 起还要 `min_format` /
   `max_format`）/ `version` / `description` 全部由 `FPP/build.json` 生成。
   要额外字段就用 build.json 的 `mcmetaOverrides`。
3. **不要猜 `pack_format`。** 不确定就留 `null`（构建会跳过并提示，`--release` 会报错），
   不要为了让构建跑通编一个数字 —— 那会发布一个游戏里报"不兼容"的包。
   核实渠道：Mojang 官方 `version_manifest_v2.json`（有哪些版本、哪个是最终补丁）+
   两份独立格式表 / 真实资源包的 `pack.mcmeta`（格式号是多少）。**核对结果写进该线的
   `notes`**，别只改数字。`minecraft.wiki/w/Pack_format` 是权威页但对本机直连返回 403。
4. **不要提交 `dist/`**（构建产物，已 gitignore）。
5. **不要重走"每版本一条长期分支/一个版本目录"的老路**（原因见 VERSIONS.md §0 的实测证据）。
   要加版本线就加 `build.json` 的一条 + 一个 overlay 目录。
6. **文本资源保持 LF**（`.json` / `.mcmeta` / `.txt`）。构建会强制归一化，产物校验发现残留
   CRLF 会直接判失败 —— 这是为了"本地构建 == CI 构建"，别绕过它。
7. **别搞混 `pack.mcmeta` 的两种写法**：格式号 ≥ 65（1.21.9 起，含 26.x）用
   `formatShape: "range"`，生成 `pack_format` + `min_format` + `max_format`；
   ≤ 64 用 `legacy`（只写 `pack_format`）。写反了正是游戏里"不兼容"提示的常见来源。

---

## 常用命令（都在仓库根执行）

```sh
python tools/build.py --list                      # 版本线清单 / pack_format / 包版本
python tools/build.py --dev                       # 组装默认线(mc1.21)到 dist/，可直接拖进游戏
python tools/build.py --line mc1.16 --dev         # 指定线
python tools/build.py --all --zip                 # 全部线打包（未知 pack_format 的线会跳过并警告）
python tools/build.py --line mc1.21 --zip --release   # 发布模式：pack_format 未知直接报错
python tools/build.py --unknown-lines             # 哪条线还没填 pack_format
python tools/audit.py --line mc26.3               # 该线有哪些文件在新版本下其实不生效（见 §3.3）
```
构建只需要 Python 3（纯标准库、无第三方依赖），**不需要 `zip` 命令**。
已实测环境：本机 Python 3.14 与 CI 的 `python3`（未在更老的 3.x 上实测过）。

---

## 改动的标准流程

```sh
git switch -c mc1.21/<主题>                       # 1. 按 线/主题 开分支
# 2. 改主体（共享）或 FPP/overlays/mc1.21/...（该线专属）
python tools/build.py --line mc1.16 --line mc1.21 --dev   # 3. 组装两条线：1.16 当基线
diff -rq dist/FPP-mc1.16.5-v8.7 dist/FPP-mc1.21.11-v9.0   #    期望：只有 pack.mcmeta
#                                     （外加你本次有意放进 mc1.21 overlay 的文件）不同
python tools/build.py --all --zip                 # 4. 全量构建，确认 exit 0
git commit -m "..."                               # 5. 提交
git push -u origin HEAD                           #    永远不写 master 字样
```

> 别用 `diff -rq FPP/assets dist/...` 来对比：主体在 Windows 工作区里是 CRLF、构建产物是
> 归一化后的 LF，会刷出几百行假差异（本仓库实测 441 行）。要比就比两个**构建产物**
> （两侧都已归一化），或用 GNU diff 的 `--strip-trailing-cr`。

---

## 想知道什么，读哪个文件

| 想知道 | 读 |
| --- | --- |
| 有哪些版本线、包版本、pack_format、冻结状态 | [FPP/build.json](FPP/build.json) |
| 方案为什么这么定、发布规范、backport 规则、防误推 main | [VERSIONS.md](VERSIONS.md) |
| overlay 该放什么、怎么放、差异来源备忘 | [FPP/overlays/README.md](FPP/overlays/README.md) |
| 构建脚本的全部参数 | [tools/build.py](tools/build.py) 顶部 docstring 或 `--help` |
| 主体里的文件在新版本下还生效吗（哪些要补 overlay） | [tools/audit.py](tools/audit.py)：`python tools/audit.py --line <线>` |
| CI 行为（矩阵、发版） | [.github/workflows/autobuild.yml](.github/workflows/autobuild.yml) |
| 防护钩子 | [.githooks/README.md](.githooks/README.md) |

---

## 汇报"完成"之前必须给的证据

- **实际运行过的命令 + 退出码**（不是"应该可以"）
- 构建产物：`--list` 输出，或 `dist/<zip>` 的条目数/文件数/体积
- 若动了版本线或 `pack_format`：给出依据来源（官方 Pack format 表），不要只写"已更新"
- 若某条线没构建成功：明说，并说明是跳过（pack_format 未知）还是失败

---

## 当前状态与遗留

**格式号已全部核实（2026-10-09）**：`build.json` 里 `packFormatSource` 全为 `verified`，
核对依据写在各线 `notes` 里；`--unknown-lines` 现在输出为空。要点：

- `mc1.21` 的目标是 **1.21.11**（1.21 线的最终补丁，不是 1.21.8），格式 **75**。
- `mc26.1` 是 **26.1.2**，格式 **84**；另加了 26.2（88）与 26.3（97.1）。
- **`mc26.3` 是"当前最新"而非"最终版"**：Mojang 仍会出 26.3.x。出新补丁后更新 `mc` 与
  `packFormat` 两个字段（格式号已出现小数位，别当成笔误）。
- **主体里有版本相关的文件，但还没补 overlay**（详见 VERSIONS.md §3.3；已用官方客户端 jar 逐版核实，
  用 `python tools/audit.py --line <线>` 可复现）：`mc1.16` 为 0 个，`mc1.17`/`mc1.18` 各 8、
  `mc1.19` 11、`mc1.20` 14、**`mc1.21` 71、`mc26.1` 130、`mc26.2`/`mc26.3` 各 156**。
  原因是原版改路径：`texts/credits.txt`→`credits.json`（**1.17** 起，你自定义的 credits 从此没生效过）、
  实体/盔甲/环境贴图在 **1.21.2** 拆进子目录（`entity/projectiles/`、`entity/equipment/humanoid/`、
  `environment/celestial/` …）、物品模型在 **1.21.4** 移到 `items/`。这些**不影响构建**，只影响游戏内表现，
  且**尚未游戏内实测**。
- `minecraft.wiki/w/Pack_format` 是权威页，但本机直连与 Wayback 快照都取不到（403）；
  以后换格式号请照 VERSIONS.md §3.1 做交叉验证，并把来源写进该线的 `notes`。
- `PPP` / `BRP` 仍是老结构（手写 pack.mcmeta，无 build.json）。要让它们接入版本线，
  照 `FPP/build.json` 加一个 build.json 即可，CI 矩阵会自动包含。
- release job（推 tag 自动发 Release）只在 tag 上运行，PR 里验证不到；第一次发版前留意。
- `defaultLine` 仍是 `mc1.21`（只影响 `--dev` 不带 `--line` 时的默认线）。若日常测试的是
  当前版本，可改成 `mc26.3`。
