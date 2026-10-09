# overlays —— 每版本线的差异层

这个目录承载"某个 Minecraft 大版本线相对主体（`FPP/`）到底改了什么"。

## 规则

- 一个版本线一个子目录：`overlays/mc1.21/`、`overlays/mc1.16/` …… id 必须与 `FPP/build.json`
  里 `lines[].line` 一致。
- 子目录里**只放与主体不同的文件**，路径与资源包根目录相同。构建时按同名覆盖主体。
  例如主体是 `assets/minecraft/models/item/lantern.json`，那么
  `overlays/mc1.21/assets/minecraft/models/item/lantern.json` 就是 1.21 线的替换版本。
- **允许为空或不存在**：这表示该线与主体完全相同（历史事实：1.16.5 与 1.17.1 的 2723 个
  文件曾 100% 相同，唯一差别就是 pack.mcmeta 里的 pack_format）。
- 子目录里名为 `README.md` 或以 `_` 开头的条目不会被打包（留给说明性文件）。
- **不要**在这里放 `pack.mcmeta`：它由 `FPP/build.json` 生成，手写会和实际内容漂移。
  需要额外字段（如 `supported_formats`）时，在本目录放同名覆盖文件也可以，但构建脚本会在
  最后用 build.json 生成的内容覆盖它 —— 所以请在 `build.json` 的 `supportedFormats` /
  `mcmetaOverrides` 字段里配置。

## 常见差异来源（备忘）

| 情况 | 例子 |
| --- | --- |
| `pack_format` 不同 | 每条线都有，但由 build.json 生成，不需要 overlay |
| 物品模型定义迁移 | 1.21.4 起 `assets/minecraft/items/*.json` 取代部分 `models/item` |
| 贴图路径改名/分层 | 版本更新中的贴图重命名、`_n`/`_s` 之类分层文件的增删 |
| 方块状态/模型格式变化 | `blockstates/*.json`、`models/block/*.json` 结构变化 |

## 检查某条线到底差异多大

```sh
python tools/build.py --list                            # 看每线 overlay 文件数
python tools/build.py --line mc1.16 --line mc1.21 --dev # 组装基线线 + 目标线
diff -rq dist/FPP-mc1.16.5-v8.7 dist/FPP-mc1.21.11-v9.0  # 差异应只有 pack.mcmeta
```

> 注意别拿主体目录直接跟产物对比（`diff -rq FPP/assets dist/...`）：主体在 Windows 工作区里是
> CRLF、产物是归一化后的 LF，会刷出几百行假差异。比两个**构建产物**最可靠，
> 或用 GNU diff 的 `--strip-trailing-cr`。
