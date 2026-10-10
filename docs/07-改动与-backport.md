# 07 · 改动与 backport

## 判定只看一句话

**这次改动是所有版本都一样，还是只有某个版本不同？**
所有版本一样 → 改主体；只有某个版本不同 → 进那条线的 overlay。

| 改动类型 | 该怎么做 |
| --- | --- |
| 跨版本通用的贴图/模型（绝大多数情况） | 直接改 `FPP/assets/...` —— **所有线自动生效**，无需 backport |
| 只有某个版本不同的文件 | 放进 `FPP/overlays/<line>/...`，只影响那一条线 |
| 某条线专属的结构性变化（如 1.21.4 的物品模型迁移） | 在对应 overlay 里放替换文件；主体保持通用 |
| 已冻结的老线（`mc1.16`） | 只接受"重新打包"，内容不再改 |

## 三种典型改动

### ① 通用改动（日常绝大多数：画贴图、改贴图、改 credits/splashes 文本）

```sh
git switch -c tex/lantern-fix          # 从最新 master 开分支
# 直接改 FPP/assets/minecraft/textures/...（全仓库只有这一份文件）
python tools/build.py --dev            # 组装默认线，拖进游戏看效果
python tools/build.py --all --zip      # 9 条线全部重新打包，一条都不会漏
git commit && git push -u origin HEAD  # 然后开 PR
```

### ② 只有某个 MC 版本不同的改动

```sh
mkdir -p FPP/overlays/mc26.3/assets/minecraft/items
# 把只给 26.3 用的文件放进去：路径与资源包根目录一致，同名会覆盖主体
```

**什么时候需要这一层？** 当原版改了路径或格式时。别靠猜 —— 跑审计：

```sh
python tools/audit.py --line mc26.3     # 列出"你改过、但该版本原版已不读"的文件
```

判读方法与已确认的原因见 [04-路径兼容性审计](04-路径兼容性审计.md)。

### ③ Minecraft 出了新版本

1. 核实版本号与格式号（方法见 [03-版本线与格式号](03-版本线与格式号.md)），
   并确认它是否已经是当前线的最终补丁；
2. 在 `FPP/build.json` 的 `lines` 里加一项：`line` / `mc` / `packFormat` /
   `packFormatSource: "verified"` / `formatShape: "range"`（格式号 ≥65 时）/ `packVersion` /
   `notes`（**写清核实来源**）；
3. 跑 `python tools/audit.py --line <新线>`，照结果给这条线建 overlay 补上
   （一个失效文件都没有就不用建）；
4. `python tools/build.py --line <新线> --dev` 测过 → `--all --zip` → 提交 PR。

完整清单见 [05-新增版本线](05-新增版本线.md)。

## 旧线不需要做任何事

既不用"切回去"，也不用 backport —— 主体没动，重新构建出来的内容和上次发布的完全一致。

## 那 `git checkout` 到底什么时候用？

**只有一种**：复现某个**已发布**的包来对比或取文件，例如
`git checkout v8.7-mc1.16.5`（tag），看完切回来。

日常工作**不需要**它 —— 想要"某条线的包"不是 checkout，而是直接构建：

```sh
python tools/build.py --line mc1.16 --zip   # 产出 dist/FPP-mc1.16.5-v8.7.zip
```

> 换句话说：**"旧版本"不是一份需要切换的工作区，而是一个构建参数。**

## 什么情况下才值得开一条长期分支？

当某条线要有人长期独立维护（几个月只动它）、且与主体的共享比例已经很低（< 50%）时，
做法是从主干切维护分支（如 `mc/1.20-legacy`），并接受"共享修复要手动 backport"的代价。

目前（各线内容 100% 相同）远没到这个程度 —— 也正是因为当年走过这条路才废弃的（见
[01-方案与目录约定](01-方案与目录约定.md)）。
