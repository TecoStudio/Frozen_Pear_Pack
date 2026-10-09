# 版本线管理（VERSIONS.md）

一个材质包要同时跟上多个 Minecraft 大版本（1.16.5 / 1.17.1 / … / 26.1）。
本文说明本项目采用的方案、日常命令、发布规范，以及"怎么保证不会误推到 main"。

---

## 0. 一句话结论

**版本维度放在构建产物和 overlay 覆盖层里，不放长期分支。**
一条主干（`master`）+ 每线一个差异目录 + 构建脚本生成 `pack.mcmeta`；
分支只用于短期主题工作，老版本线用 tag / Release 冻结。

### 为什么不是"每个大版本一条分支"

不是分支不好，而是**本项目的数据已经证明这条线不值得走**：

| 时间 | 当时的做法 | 结果 |
| --- | --- | --- |
| ≤ v8.6（2023） | 只有一个包目录，MC 版本写在 `pack.mcmeta` 的 `version` 字段里 | 被弃用 |
| 2023-09 | 分支 `v8.5-or-v8.6` | 死分支：0 领先于 master，两年无人问津 |
| 2025-03 | 按 MC 版本分目录：`1.16.5/FPP`、`1.17.1/FPP` | 一个月后删除 |
| 2025-04-12 起 | 按包名分目录：`FPP/`、`PPP/`、`BRP(deprecated)/` | 当前方案 |

关键事实（`4bc015d^` 时的实测）：

```
1.16.5/FPP   2723 个文件
1.17.1/FPP   2723 个文件
只在其中一边出现的文件：0 个
```

两个版本目录的**文件名集合完全相同**，唯一差别是 `pack.mcmeta` 里的
`pack_format`（6 与 7）和 `version` 文本 —— 为了一个 134 字节的 JSON，
复制了整棵 12MB 资源树。这正是当时把它们合并掉的原因。

分支方案会把同一个代价再付一次，而且额外带来一个**无法用分支保护堵住**的风险：
共享贴图在 1.21 线上修好了，忘了 backport 到 1.20 线 —— 不报错、不冲突，
两边只是慢慢不一致。单主干 + overlay 让共享改动**自动**进入所有线，从结构上消灭这个问题。

---

## 1. 目录与文件约定

```
FPP/                     主体：跨版本共享的文件（assets/、pack.png …）
FPP/build.json           本包的版本线定义（唯一真值来源）
FPP/overlays/            差异层根目录（见 FPP/overlays/README.md）
FPP/overlays/mc1.21/     只放与主体不同的文件，路径同资源包根目录；可以为空/不存在
tools/build.py           构建脚本（只用 Python 标准库）
tools/setup-guards.sh    一键安装本地防误推防护
.githooks/               本地防护钩子（pre-commit / pre-push）
dist/                    构建产物（已 gitignore）
```

- **`pack.mcmeta` 不再手写、不再提交**：`pack_format` / `version` / `description`
  全部由 `FPP/build.json` 生成，避免版本号和实际内容漂移。
- `overlays/<line>/` 里 id 必须与 `build.json` 的 `lines[].line` 一致。
- 构建 = 复制主体 → 覆盖 overlay → 写入生成的 `pack.mcmeta` → （可选）打包 zip。

---

## 2. 日常命令

| 目的 | 命令 |
| --- | --- |
| 看所有版本线 | `python tools/build.py --list` |
| 日常开发（默认线 mc1.21 解包到 dist/） | `python tools/build.py --dev` |
| 指定线组装（拖进游戏测试） | `python tools/build.py --line mc1.16 --dev` |
| 组装 + 打包 zip | `python tools/build.py --line mc1.21 --zip` |
| 全部线组装 + 打包 | `python tools/build.py --all --zip` |
| 发布前严格检查 | `python tools/build.py --all --zip --release` |
| 看哪条线 pack_format 还未知 | `python tools/build.py --unknown-lines` |

- 产物：`dist/FPP-mc<MC目标>-v<包版本>/`（解包目录）与同名 `.zip`。
- 打包是**可复现**的：条目排序 + 固定时间戳，相同输入产出字节一致的 zip（已实测）。
- `--release` 下若某条线的 `pack_format` 还是 `null`，脚本直接报错退出（exit 1），
  不会生成一个格式号错误的包。`packFormatSource: assumed` 的线只在日志里告警。

---

## 3. 版本线清单（真值在 `FPP/build.json`）

| 线 id | MC 目标 | pack_format | 来源 | 包版本 | 冻结 | overlay |
| --- | --- | --- | --- | --- | --- | --- |
| `mc1.16` | 1.16.5 | 6 | ✅ 仓库历史证实 | v8.7 | 是 | 无（= 主体） |
| `mc1.17` | 1.17.1 | 7 | ✅ 仓库历史证实 | v9.0 | 否 | 无（= 主体） |
| `mc1.18` | 1.18.2 | 8 | ⚠️ 待核对 | v9.0 | 否 | 无（= 主体） |
| `mc1.19` | 1.19.4 | 13 | ⚠️ 待核对 | v9.0 | 否 | 无（= 主体） |
| `mc1.20` | 1.20.6 | 32 | ⚠️ 待核对 | v9.0 | 否 | 无（= 主体） |
| `mc1.21` | 1.21.8 | 64 | ⚠️ 待核对 | v9.0 | 否 | 无（= 主体） |
| `mc26.1` | 26.1 | ？ | ❌ 未知 | v9.0 | 否 | 无（= 主体） |

"MC 目标"填该大版本的**最后一个补丁版本**（玩家实际会停留的版本），
所以差异层也只需针对这个版本做。

> ⚠️ **需要你核对的两件事**
> 1. **pack_format 数字**：`1.16.5=6`、`1.17.1=7` 已由本仓库历史提交证实；
>    其余是凭已知版本表填入的，请在 Minecraft Wiki 的 "Pack format" 页面（或
>    misode 的 pack format 列表）核对后，把 `build.json` 里的
>    `packFormatSource` 从 `assumed` 改成 `verified`。改错了不会崩，但游戏里会提示
>    "不兼容"。
> 2. **`mc26.1` 的 pack_format**：新版版本号体系，我不知道对应数字，
>    所以留成 `null` —— 在你填上之前，这条线不会被构建（`--release` 会直接报错）。
> 3. 若 `mc1.21` 大版本的最终补丁**不是** 1.21.8，请同时改 `mc` 与 `packFormat`。

---

## 4. 新增一条版本线

```sh
# 1) 在 FPP/build.json 的 lines 里加一项（line / mc / packFormat / packVersion / notes）
# 2) 如果这条线与主体有差异，把差异文件放进差异层：
mkdir -p FPP/overlays/mc1.22/assets/minecraft/...
# 3) 验证
python tools/build.py --line mc1.22 --dev
diff -rq FPP/assets dist/FPP-mc1.22-v9.0/assets   # 看差异范围
```

CI 会自动跟上：矩阵由 `build.json` 生成，不需要改 workflow。

---

## 5. 发布规范

- **版本号是每条线独立的**：`mc1.16` 停在 `v8.7`；新线都从 `v9.0` 起各自递增。
  所以"v9.0"在不同线下内容不同 —— 看文件名/标题里的 MC 目标即可区分。
- **tag**：`v<包版本>-mc<MC目标>`，例如 `v9.0-mc1.21.8`。
  推 tag 会触发 CI：构建**全部**线并把这些 zip 传进该 tag 的 Release。
- **zip 名**：`FPP-mc<MC目标>-v<包版本>.zip`（由脚本生成，别手改）。
- **`pack.mcmeta`**：`version` 字段为 `v<包版本> for MC<MC目标>`，如 `v9.0 for MC1.21.8`；
  由 `build.json` 生成，不要手写。
- 历史 tag `v7.0` … `v8.7` 全部属于 `mc1.16` 线，保持原样不动。

---

## 6. 共享改动与 backport 规则

| 改动类型 | 该怎么做 |
| --- | --- |
| 跨版本通用的贴图/模型（绝大多数情况） | 直接改 `FPP/assets/...` —— **所有线自动生效**，无需 backport |
| 只有某个版本不同的文件 | 放进 `FPP/overlays/<line>/...`，只影响那一条线 |
| 某条线专属的结构性变化（如 1.21.4 的物品模型迁移） | 在对应 overlay 里放替换文件；主体保持通用 |
| 已冻结的老线（`mc1.16`） | 只接受"重新打包"，内容不再改 |

**什么情况下才值得开一条长期分支？** 当某条线要有人长期独立维护（几个月只动它）、
且与主体的共享比例已经很低（< 50%）。那时的做法是从主干切维护分支
（`mc/1.20-legacy`），并接受"共享修复要手动 backport"的代价。
目前（各线内容 100% 相同）远没到这个程度。

---

## 7. 防误推 main —— 三层防护

目标：**手滑的时候直接在本地就被挡住**，而不是靠事后回滚。

### 第 1 层：GitHub 分支保护（服务端，最硬）

Web：仓库 → Settings → Rules（或 Branches）→ 针对 `master`：

- ✅ Require a pull request before merging（Approvals 可设 0，允许自己合并）
- ✅ Block force pushes
- ✅ Restrict deletions

> 你有两个远端：`origin`（LIPiston 自己的仓库）和 `upstream`（TecoStudio 组织仓库）。
> `origin` 必须开（你有权限）；`upstream` 需要组织管理员开。
>
> CLI 等价做法（把仓库名换成你要保护的）：
> ```sh
> gh api -X PUT repos/LIPiston/Frozen_Pear_Pack/branches/master/protection \
>   -F 'required_pull_request_reviews[required_approving_review_count]=0' \
>   -F allow_force_pushes=false -F allow_deletions=false
> ```

### 第 2 层：仓库自带的本地钩子

```sh
sh tools/setup-guards.sh      # clone 之后执行一次（团队每个人都跑一次）
```

它做两件事：`git config core.hooksPath .githooks` +
`git config branch.master.pushRemote __no_push__`。

| 场景 | 结果 |
| --- | --- |
| 在 `master` 上 `git commit` | ❌ 被拒绝，提示先开分支 |
| 推送 `refs/heads/master` | ❌ 被拒绝，提示走 PR |
| 推送自己的工作分支 / tag | ✅ 正常 |
| `ALLOW_MAIN=1 git commit/push …` | ✅ 单次放行（逃生口） |

（钩子内容见 `.githooks/`，已实测：master 被拦、feature 与 tag 放行、`ALLOW_MAIN=1` 放行。）

### 第 3 层：git 自身兜底

`branch.master.pushRemote = __no_push__` 让"在 master 上直接敲 `git push`"失败：

```
error: failed to push some refs to '__no_push__'
```

要真想推必须写全 `git push origin master`（所以不会"手滑"，但也不会被彻底锁死）。

### 日常流程（照这个做就不会出事）

```sh
git switch -c mc1.21/fix-lantern-animation   # 按 线/主题 开分支
# …改文件…
python tools/build.py --line mc1.21 --dev     # 本地验证
git commit -m "fix: ..."
git push -u origin HEAD                       # 永远不写 master 字样
# 然后开 PR → 合并
```

### 撤销这些防护

```sh
git config --unset core.hooksPath
git config --unset branch.master.pushRemote
```

---

## 8. 还没接入的包

`PPP/`（Pbr Pear Pack）与 `BRP(deprecated)/` 仍是老结构（手写 `pack.mcmeta`，无 `build.json`）。
要让它们也走多版本线，只需加一个 `build.json`（照抄 `FPP/build.json` 的结构），
CI 矩阵会自动包含它们。建议顺序：PPP 独立成扩展包时再接入；BRP 已废弃，不动。
