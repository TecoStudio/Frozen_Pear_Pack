#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Frozen Pear Pack —— 多版本线构建脚本（只用 Python 标准库，无第三方依赖）

设计目标
--------
一个材质包要同时维护多个 Minecraft 大版本线（1.16.5 / 1.17.1 / ... / 26.1）。
各线之间 **绝大多数文件是相同的**（贴图 PNG 跨版本通用），只有少数随版本变化的
文件（pack.mcmeta、物品模型 JSON、改名的贴图路径）不同。

所以采用「单一主体 + 每线 overlay」而不是「每线一条分支」：

    FPP/                        主体：所有跨版本共享的文件（assets/、pack.png ...）
    FPP/build.json              本包的版本线定义
    FPP/overlays/<line>/        只放与该线不同的文件（同名覆盖主体）；可以为空
    dist/                       构建产物（已 gitignore）
        FPP-mc1.21.8-v9.0/      解包目录，可直接拖进游戏测试
        FPP-mc1.21.8-v9.0.zip   分发包，pack.mcmeta 在压缩包根目录

pack.mcmeta 是 **生成** 的：pack_format / version / description 都来自 build.json，
不再手写，避免版本号和实际内容漂移。

文本类资源（.json / .mcmeta / .txt）在打包时统一按 LF 写入：它们不该随协作方
Windows 上的 core.autocrlf 设置而变，否则本地构建与 CI 构建出的包内容不一致
（同样的贴图，只有行尾不同），发布包也就无法校验。

用法
----
    python tools/build.py --list                      # 列出所有版本线
    python tools/build.py --line mc1.21 --dev         # 只组装解包目录（日常开发）
    python tools/build.py --all --zip                 # 全部线组装 + 打包
    python tools/build.py --pack FPP --line mc1.16 --zip
    python tools/build.py --matrix                    # GitHub Actions matrix JSON
    python tools/build.py --github-output             # 写入 $GITHUB_OUTPUT 的一行
    python tools/build.py --unknown-lines             # pack_format 未知（会被跳过）的版本线
    python tools/build.py --all --zip --release       # 发布模式：pack_format 未知则报错

退出码：0 成功；1 出现错误（配置非法、pack_format 未知、组装校验失败）。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Windows 控制台默认编码是 cp936/GBK，中文日志会乱码；统一按 UTF-8 输出
# （git-bash / VSCode 终端 / GitHub Actions 都是 UTF-8）。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

# 主体目录里这些条目不进入资源包（它们属于构建系统本身）
SKIP_IN_PACK = {"overlays", "build.json"}
# overlay 目录里这些条目不进入资源包（说明性文件，避免污染 zip）
SKIP_IN_OVERLAY_NAMES = {"README.md", "readme.md"}
SKIP_SUFFIXES = (".bak",)
# 文本类资源在打包时统一按 LF 写入：资源包内容不应随协作方 Windows 上的
# core.autocrlf 设置而变，否则「本地构建」和「CI 构建」出的包字节不同
# （同样的贴图，只有行尾不一样），发布包就无法校验了。
TEXT_SUFFIXES = (".json", ".mcmeta", ".txt", ".properties", ".lang", ".csv")
# 固定时间戳 + 条目排序 => 构建可复现：
#   同一台机器/同一 zlib 版本下，相同输入产出字节一致的 zip；
#   不同机器之间每个条目的内容与 CRC 一致，只有"压缩后的字节"可能因 zlib 版本不同而略有差异。
ZIP_DATE_TIME = (2020, 1, 1, 0, 0, 0)

LINE_RE = re.compile(r"^mc[0-9][0-9A-Za-z._-]*$")
VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+")
VALID_SOURCES = ("verified", "assumed", "unknown")

WARN = []
ERR = []


def warn(msg: str) -> None:
    WARN.append(msg)


def err(msg: str) -> None:
    ERR.append(msg)


# --------------------------------------------------------------------------- #
# 配置
# --------------------------------------------------------------------------- #

def iter_pack_dirs() -> list[Path]:
    """仓库根目录下所有含 build.json 的目录 = 一个材质包工程。"""
    return sorted(
        p for p in REPO_ROOT.iterdir()
        if p.is_dir() and not p.name.startswith(".") and (p / "build.json").is_file()
    )


def load_config(pack_dir: Path) -> dict:
    cfg_path = pack_dir / "build.json"
    try:
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"[错误] {cfg_path} 不是合法 JSON：{exc}") from exc

    for key in ("id", "name", "description", "lines"):
        if key not in cfg:
            raise SystemExit(f"[错误] {cfg_path} 缺少字段：{key}")
    if not isinstance(cfg["lines"], list) or not cfg["lines"]:
        raise SystemExit(f"[错误] {cfg_path} 的 lines 必须是非空数组")

    seen = set()
    for line in cfg["lines"]:
        lid = line.get("line", "?")
        if not LINE_RE.match(str(lid)):
            raise SystemExit(f"[错误] 版本线 id 不合法：{lid!r}（应形如 mc1.21 / mc26.1）")
        if lid in seen:
            raise SystemExit(f"[错误] 版本线 id 重复：{lid}")
        seen.add(lid)

        pf = line.get("packFormat")
        if pf is not None and (not isinstance(pf, int) or pf <= 0):
            raise SystemExit(f"[错误] {lid} 的 packFormat 必须是正整数或 null，实际：{pf!r}")

        src = line.get("packFormatSource", "assumed")
        if src not in VALID_SOURCES:
            raise SystemExit(f"[错误] {lid} 的 packFormatSource 非法：{src!r}（可选 {VALID_SOURCES}）")

        ver = str(line.get("packVersion", ""))
        if not VERSION_RE.match(ver):
            raise SystemExit(f"[错误] {lid} 的 packVersion 非法：{ver!r}（应形如 9.0）")

    if cfg.get("defaultLine") and cfg["defaultLine"] not in seen:
        raise SystemExit(f"[错误] defaultLine={cfg['defaultLine']!r} 不在 lines 里")

    return cfg


def select_packs(wanted: list[str]) -> list[tuple[Path, dict]]:
    packs = iter_pack_dirs()
    if not packs:
        raise SystemExit("[错误] 仓库根目录下没有找到任何含 build.json 的材质包工程")
    if wanted:
        chosen = [(p, load_config(p)) for p in packs if p.name in wanted or load_config(p)["id"] in wanted]
        missing = set(wanted) - {p.name for p, _ in chosen} - {c["id"] for _, c in chosen}
        if missing:
            raise SystemExit(f"[错误] 找不到材质包工程：{', '.join(sorted(missing))}")
        return chosen
    return [(p, load_config(p)) for p in packs]


def select_lines(cfg: dict, wanted: list[str], all_lines: bool) -> list[dict]:
    lines = cfg["lines"]
    if not wanted or all_lines:
        return lines
    by_id = {l["line"]: l for l in lines}
    out = []
    for w in wanted:
        if w not in by_id:
            known = ", ".join(by_id)
            raise SystemExit(f"[错误] 材质包 {cfg['id']} 没有版本线 {w!r}；可用：{known}")
        out.append(by_id[w])
    return out


# --------------------------------------------------------------------------- #
# 组装
# --------------------------------------------------------------------------- #

def iter_shared_entries(pack_dir: Path):
    for entry in sorted(pack_dir.iterdir(), key=lambda p: p.name):
        if entry.name in SKIP_IN_PACK or entry.name.startswith("_"):
            continue
        if entry.name.endswith(SKIP_SUFFIXES):
            continue
        yield entry


def copy_file(src: Path, dst: Path) -> None:
    """复制单个文件；文本类资源统一按 LF 写入（见 TEXT_SUFFIXES 的说明）。"""
    if src.suffix.lower() in TEXT_SUFFIXES:
        data = src.read_bytes()
        if b"\r\n" in data:
            data = data.replace(b"\r\n", b"\n")
        dst.write_bytes(data)
        shutil.copystat(src, dst)
    else:
        shutil.copy2(src, dst)


def copy_tree(src: Path, dst: Path) -> int:
    """把 src 内容合并到 dst（同名覆盖），返回复制的文件数。"""
    count = 0
    for root_str, dirs, files in os.walk(src):
        dirs.sort()
        root = Path(root_str)
        rel = root.relative_to(src)
        target_root = dst / rel
        target_root.mkdir(parents=True, exist_ok=True)
        for name in sorted(files):
            if name.endswith(SKIP_SUFFIXES):
                continue
            copy_file(root / name, target_root / name)
            count += 1
    return count


def overlay_dir(pack_dir: Path, line_id: str) -> Path:
    return pack_dir / "overlays" / line_id


def build_mcmeta(cfg: dict, line: dict) -> dict:
    """生成 pack.mcmeta 内容（唯一真值来源是 build.json）。"""
    pack: dict = {
        "pack_format": line["packFormat"],
        "version": f"v{line['packVersion']} for MC{line['mc']}",
        "description": cfg["description"],
    }
    # 允许每条线自定义 supported_formats / 覆盖字段（build.json 里写 supportedFormats）
    if line.get("supportedFormats") is not None:
        pack["supported_formats"] = line["supportedFormats"]
    for k, v in (line.get("mcmetaOverrides") or {}).items():
        pack[k] = v
    return {"pack": pack}


def assemble(pack_dir: Path, cfg: dict, line: dict, out_root: Path, do_zip: bool) -> dict:
    line_id = line["line"]
    if line["packFormat"] is None:
        err(f"{cfg['id']}/{line_id}：packFormat 为 null（未知），无法构建。请在 {pack_dir.name}/build.json 填上该 MC 版本的 pack format。")
        return {}

    if line["packFormatSource"] == "assumed":
        warn(f"{cfg['id']}/{line_id}（MC {line['mc']}）的 pack_format={line['packFormat']} 标记为 assumed —— 发布前请核对官方 Pack format 表。")
    elif line["packFormatSource"] == "unknown":
        warn(f"{cfg['id']}/{line_id}：packFormatSource=unknown 但已给出数字，请改回 verified。")

    zip_name = f"{cfg['id']}-mc{line['mc']}-v{line['packVersion']}"
    out_dir = out_root / zip_name

    # 安全护栏：只允许清理 dist 下的目标目录
    out_root_resolved = out_root.resolve()
    if out_dir.resolve() == out_root_resolved or out_root_resolved not in out_dir.resolve().parents:
        err(f"拒绝清理不在 {out_root_resolved} 之下的路径：{out_dir.resolve()}")
        return {}
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    shared_count = 0
    for entry in iter_shared_entries(pack_dir):
        if entry.is_dir():
            shared_count += copy_tree(entry, out_dir / entry.name)
        else:
            copy_file(entry, out_dir / entry.name)
            shared_count += 1

    ov = overlay_dir(pack_dir, line_id)
    overlay_count = 0
    overlay_note = "无 overlay 目录（该线与主体完全相同，仅 pack.mcmeta 不同）"
    if ov.is_dir():
        filtered = [p for p in ov.iterdir() if p.name not in SKIP_IN_OVERLAY_NAMES and not p.name.startswith("_")]
        for entry in sorted(filtered, key=lambda p: p.name):
            if entry.is_dir():
                overlay_count += copy_tree(entry, out_dir / entry.name)
            else:
                copy_file(entry, out_dir / entry.name)
                overlay_count += 1
        overlay_note = f"{overlay_count} 个文件来自 overlay"

    # pack.mcmeta 由 build.json 生成，最后一次写入以确保覆盖任何残留。
    # 注意必须显式指定 newline="\n"：Path.write_text 在 Windows 上会把 \n 变成
    # \r\n，导致本地构建的 pack.mcmeta 与 CI / Linux 上生成的不一致。
    mcmeta = build_mcmeta(cfg, line)
    with open(out_dir / "pack.mcmeta", "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(mcmeta, ensure_ascii=False, indent=2) + "\n")

    # 校验：产物必须是「根目录下有 pack.mcmeta 和 assets/ 的资源包」
    problems = []
    written = json.loads((out_dir / "pack.mcmeta").read_text(encoding="utf-8"))
    if written["pack"]["pack_format"] != line["packFormat"]:
        problems.append("pack.mcmeta 的 pack_format 与 build.json 不一致")
    if not (out_dir / "assets" / "minecraft").is_dir():
        problems.append("产物缺少 assets/minecraft 目录")
    crlf = [
        p.relative_to(out_dir).as_posix()
        for p in out_dir.rglob("*")
        if p.is_file() and p.suffix.lower() in TEXT_SUFFIXES and b"\r\n" in p.read_bytes()
    ]
    if crlf:
        problems.append(f"{len(crlf)} 个文本资源仍含 CRLF（行尾未归一化）：{', '.join(crlf[:3])} …")
    if problems:
        for p in problems:
            err(f"{cfg['id']}/{line_id} 产物校验失败：{p}")
        return {}

    files = sum(1 for p in out_dir.rglob("*") if p.is_file())
    size = sum(p.stat().st_size for p in out_dir.rglob("*") if p.is_file())

    result = {
        "pack": cfg["id"],
        "line": line_id,
        "mc": line["mc"],
        "version": line["packVersion"],
        "dir": out_dir,
        "name": zip_name,
        "files": files,
        "bytes": size,
        "shared": shared_count,
        "overlay": overlay_count,
        "overlayNote": overlay_note,
        "packFormat": line["packFormat"],
        "zip": None,
        "sha256": None,
    }

    if do_zip:
        zip_path = out_root / f"{zip_name}.zip"
        make_zip(out_dir, zip_path)
        result["zip"] = zip_path
        result["sha256"] = sha256_file(zip_path)

    return result


def make_zip(src_dir: Path, zip_path: Path) -> None:
    """确定性打包：条目排序 + 固定时间戳 + zip 根目录即资源包根目录。"""
    if zip_path.exists():
        zip_path.unlink()
    entries: list[tuple[Path, str]] = []
    for path in src_dir.rglob("*"):
        if path.is_file():
            entries.append((path, path.relative_to(src_dir).as_posix()))
    entries.sort(key=lambda t: t[1])
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for path, arcname in entries:
            info = zipfile.ZipInfo(arcname, date_time=ZIP_DATE_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            with zf.open(info, "w") as dst, open(path, "rb") as src:
                shutil.copyfileobj(src, dst, 1024 * 256)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def human(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.1f}{unit}" if unit != "B" else f"{n}B"
        n /= 1024.0
    return f"{n}B"


# --------------------------------------------------------------------------- #
# 输出模式
# --------------------------------------------------------------------------- #

def cmd_list(packs: list[tuple[Path, dict]]) -> None:
    for pack_dir, cfg in packs:
        print(f"\n=== {cfg['id']} ({cfg['name']}) —— {pack_dir.name}/build.json ===")
        header = f"{'线':<9} {'MC 目标':<10} {'format':>6} {'来源':<9} {'包版本':>7} {'冻结':<5} {'overlay':>8}  说明"
        print(header)
        print("-" * len(header))
        for line in cfg["lines"]:
            pf = "?" if line["packFormat"] is None else str(line["packFormat"])
            ov = overlay_dir(pack_dir, line["line"])
            n = sum(1 for p in ov.rglob("*") if p.is_file()) if ov.is_dir() else 0
            ov_txt = f"{n}" if ov.is_dir() else "无目录"
            note = (line.get("notes") or "").split("；")[0].split("。")[0][:46]
            print(
                f"{line['line']:<9} {line['mc']:<10} {pf:>6} {line.get('packFormatSource','assumed'):<9} "
                f"v{line['packVersion']:>5} {'是' if line.get('frozen') else '否':<5} {ov_txt:>8}  {note}"
            )
        print(f"默认线（--dev 不带 --line 时）：{cfg.get('defaultLine', cfg['lines'][0]['line'])}")


def cmd_matrix(selection: list[tuple[dict, dict]]) -> str:
    """selection: [(cfg, line), ...] —— 只导出 pack_format 已确定的线。"""
    include = []
    for cfg, line in selection:
        if line["packFormat"] is None:
            continue
        include.append({
            "pack": cfg["id"],
            "line": line["line"],
            "mc": line["mc"],
            "version": line["packVersion"],
            "artifact": f"{cfg['id']}-mc{line['mc']}-v{line['packVersion']}",
            "zip": f"{cfg['id']}-mc{line['mc']}-v{line['packVersion']}.zip",
        })
    return json.dumps({"include": include}, ensure_ascii=False, separators=(",", ":"))


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="build.py",
        description="Frozen Pear Pack 多版本线构建（主体 + 每线 overlay -> 解包目录/zip）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--pack", action="append", default=[], help="材质包工程名/ID（默认全部）")
    ap.add_argument("--line", action="append", default=[], help="版本线 id，如 mc1.21（可重复；默认全部）")
    ap.add_argument("--all", action="store_true", help="强制构建全部版本线")
    ap.add_argument("--out", default="dist", help="产物目录（默认 dist/，相对仓库根）")
    ap.add_argument("--zip", action="store_true", help="额外生成分发包 zip")
    ap.add_argument("--dev", action="store_true", help="只生成解包目录，并可省略 --line（用 defaultLine）")
    ap.add_argument("--release", action="store_true", help="发布模式：pack_format 未知即报错")
    ap.add_argument("--list", action="store_true", help="列出版本线后退出")
    ap.add_argument("--matrix", action="store_true", help="输出 GitHub Actions matrix JSON 后退出")
    ap.add_argument("--github-output", action="store_true", help='输出 "matrix=<json>" 一行，供 $GITHUB_OUTPUT 使用')
    ap.add_argument("--unknown-lines", action="store_true", help="输出 pack_format 未知（会被跳过）的版本线 id，供 CI 提醒")
    args = ap.parse_args(argv)

    packs = select_packs(args.pack)

    if args.list:
        cmd_list(packs)
        return 0

    if args.unknown_lines:
        unknown = [f"{cfg['id']}/{l['line']}" for _, cfg in packs for l in cfg["lines"] if l["packFormat"] is None]
        print(", ".join(unknown))
        return 0

    if args.matrix or args.github_output:
        selection = []
        for _pack_dir, cfg in packs:
            for line in select_lines(cfg, args.line, args.all):
                selection.append((cfg, line))
        payload = cmd_matrix(selection)
        if not json.loads(payload)["include"]:
            print(
                "[错误] 没有可构建的版本线：选中的线要么不存在，要么 pack_format 为 null。"
                "请检查 build.json，或改用别的 --line。",
                file=sys.stderr,
            )
            return 1
        print(f"matrix={payload}" if args.github_output else payload)
        return 0

    # 选定版本线
    wanted = list(args.line)
    if args.dev and not wanted and not args.all:
        for _, cfg in packs:
            default = cfg.get("defaultLine") or cfg["lines"][0]["line"]
            if default not in wanted:
                wanted.append(default)
        print(f"[dev] 未指定 --line，使用默认线：{', '.join(wanted)}")

    out_root = (REPO_ROOT / args.out).resolve()
    out_root.mkdir(parents=True, exist_ok=True)

    results = []
    for pack_dir, cfg in packs:
        lines = select_lines(cfg, wanted, args.all)
        for line in lines:
            # pack_format 未知的线：显式点名或 --release 时是硬错误，其余情况跳过并提示。
            if line["packFormat"] is None:
                msg = (
                    f"{cfg['id']}/{line['line']}（MC {line['mc']}）：pack_format 未知，无法构建。"
                    f"请在 {pack_dir.name}/build.json 里填上该 MC 版本的 pack format。"
                )
                if args.release or line["line"] in args.line:
                    err(msg)
                else:
                    warn(f"已跳过 {cfg['id']}/{line['line']} —— {msg}")
                continue
            r = assemble(pack_dir, cfg, line, out_root, do_zip=args.zip)
            if r:
                results.append(r)

    if results:
        print("\n构建结果")
        print("-" * 96)
        for r in results:
            print(
                f"{r['pack']}/{r['line']:<8} MC {r['mc']:<9} v{r['version']:<6} format={r['packFormat']:<4} "
                f"{r['files']:>5} 文件 {human(r['bytes']):>8}  ({r['overlayNote']})"
            )
            print(f"    目录：{r['dir'].relative_to(REPO_ROOT).as_posix()}")
            if r["zip"]:
                print(f"    压缩包：{r['zip'].relative_to(REPO_ROOT).as_posix()}  sha256:{r['sha256'][:16]}")
        print("-" * 96)

    if WARN:
        print("\n⚠️  警告")
        for w in WARN:
            print(f"  - {w}")
    if ERR:
        print("\n❌ 错误")
        for e in ERR:
            print(f"  - {e}")
        return 1

    if not results:
        print("\n没有构建任何版本线（可能都被跳过了）。")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
