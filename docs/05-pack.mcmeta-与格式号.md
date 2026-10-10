# 05 · pack.mcmeta 与格式号

## 现在各分支的值

| 分支 | 目标 MC | `pack_format` | `version` |
| --- | --- | --- | --- |
| `master` | 最新（内容仍是 1.16.5 时代） | 6 | `"test"` |
| `1.16.5` | 1.16.5 | 6 | `"test"` |
| `1.15.2` | 1.15.2 | 5 | `"v7.0 for MC1.15"` |

`FPP/pack.mcmeta` 是**手写并提交**的（本方案没有构建脚本，这份文件就是该分支的版本声明）。

## 格式号对照表

**每个大版本填它的最后一个补丁版本**（玩家实际停留的版本）：

| MC | 格式号 | MC | 格式号 |
| --- | --- | --- | --- |
| 1.15.2 | 5 | 1.21.11 | **75** |
| 1.16.5 | 6 | 26.1.2 | **84** |
| 1.17.1 | 7 | 26.2 | 88 |
| 1.18.2 | 8 | 26.3 | 97.1 |
| 1.19.4 | 13 | | |
| 1.20.6 | 32 | | |

**核实来源（2026-10-09）** —— 换格式号时照这个方法做，别凭记忆：

- **版本清单**：Mojang 官方 `version_manifest_v2.json`（一手来源）。1.16→1.16.5、1.17→1.17.1、
  1.18→1.18.2、1.19→1.19.4、1.20→1.20.6、**1.21→1.21.11**（不是 1.21.8）、26.1→26.1.2。
- **格式号**：权威页 `minecraft.wiki/w/Pack_format` 直连被 Cloudflare 403 挡住，改用交叉验证 ——
  两份互相独立的格式表（MineVinyl、HTG George）在 1.15–26.3 上完全一致，并与两类**实物**吻合：
  真实资源包（Plastix/Plast-Pack、Godlander/objmc 声明 1.21.11=75；ItzOratotITA/OratotPVP
  声明 26.2=88；SummerFields 声明 max 97.1）与 MCreator 的 26.1.x / 26.3.x 生成器模板（84.0 / 97.1）。
- 曾纠正两处：`1.21` 由"1.21.8 / 64" → **1.21.11 / 75**；`26.1` 由未知 → **26.1.2 / 84**。
- ⚠️ **26.3 是"当前最新"而非"最终版"**：Mojang 还会出 26.3.x。出新补丁时更新 `pack_format`
  （已出现小数位，别当成笔误）。

## 两种写法

**老写法（格式号 ≤ 64，即 1.21.8 及以前）** —— 只写 `pack_format`：

```json
{
  "pack": {
    "pack_format": 6,
    "version": "v8.8 for MC1.16.5",
    "description": "§l§6FPP \n§l§7Only for Java Edition"
  }
}
```

**区间写法（1.21.9 起，含 26.x）** —— 还要 `min_format` / `max_format`：

```json
{
  "pack": {
    "pack_format": 75,
    "min_format": 75,
    "max_format": 75,
    "version": "v9.0 for MC1.21.11",
    "description": "§l§6FPP \n§l§7Only for Java Edition"
  }
}
```

- `min_format` / `max_format` 的含义是"这个包为哪些格式号制作"。填成同一个数字＝只给这一个版本用。
- **26.2 起 `min_format` / `max_format` 变成必需**，`supported_formats` 被移除。
- ⚠️ 别写反：把区间写法塞进 1.20 的包（或反过来）正是游戏里"不兼容"提示的常见来源。

## 两条容易搞错的

1. **格式号对 ≠ 游戏里对**：格式号只决定游戏肯不肯加载这个包；包里的**文件路径**对不对，
   才决定内容有没有生效。路径见 [06-各版本路径变化对照](06-各版本路径变化对照.md)。
2. **`version` 字段是给人看的**：格式是 `v<包版本> for MC<MC目标>`，例 `v8.8 for MC1.16.5`。
   它可以随便写（`"test"` 也能加载），但发版前一定要改成真版本号，否则玩家分不清装的是哪版。

## 自查

```sh
git show HEAD:FPP/pack.mcmeta     # 当前分支的声明
python -c "import json,pathlib; d=json.loads(pathlib.Path('FPP/pack.mcmeta').read_text(encoding='utf-8'))['pack']; print(d)"
```
