#!/usr/bin/env python3
"""资源路径兼容性审计：主体里的文件，在某条版本线的目标 MC 里还读得到吗？

背景
----
`pack_format` 对不对，只决定游戏肯不肯加载这个包；**文件路径对不对，才决定包里的内容
有没有生效**。原版会在小版本里改路径（如 1.21.2 把实体贴图拆进子目录、1.17 把
`texts/credits.txt` 换成 `credits.json`、1.21.4 把物品模型搬到 `items/`），
而资源包是被动覆盖：路径变了，你那份文件就成了"孤儿"——不报错、不崩溃，只是**不生效**。

本脚本拿官方客户端 jar（`version_manifest_v2.json` 里的一手来源）当参照，
逐条版本线列出"你改过、但该版本原版已经不读"的文件，并尝试猜出它的新路径。

用法
----
    python tools/audit.py --list                 # 看有哪些线、各自目标版本
    python tools/audit.py --line mc1.21          # 审计某条线（缺失时自动下载 jar 并缓存）
    python tools/audit.py --line mc26.3 --json   # 机器可读输出
    python tools/audit.py --line mc1.21 --strict # 有需要处理的文件时退出码 1（可用于 CI）
    python tools/audit.py --all                  # 所有线（会下载多个 jar，约 20-35 MB/个）

缓存与基线
----------
jar 缓存在 `dist/.jarcache/`（`dist/` 已 gitignore），同一个版本只下载一次。
`--baseline` 默认取 `build.json` 里最老那条线的目标版本（即主体内容出处的年代），
用来区分"原版改名了"和"你自建的文件"：只有在基线里存在、在目标版本里不存在的路径，
才可能是被原版改名/移除的。加 `--no-baseline` 可跳过字节比对。

只需要 Python 3（纯标准库）。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = REPO_ROOT / "dist" / ".jarcache"
MANIFEST_URL = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
UA = {"User-Agent": "FPP-audit/1.0 (+https://github.com/LIPiston/Frozen_Pear_Pack)"}
MANIFEST_CACHE_SECONDS = 24 * 3600

# 主体里这些不算"资源文件"，不参与审计
SKIP_TOP = ("overlays",)
SKIP_NAMES = ("build.json", "pack.png")
PREFIX = "assets/minecraft/"


_LOG = sys.stdout  # --json 时改指 stderr，保证 stdout 只有干净的 JSON


def log(msg: str = "") -> None:
    print(msg, file=_LOG, flush=True)


def warn(msg: str) -> None:
    print(f"⚠️  {msg}", file=sys.stderr, flush=True)


def die(msg: str) -> None:
    print(f"[错误] {msg}", file=sys.stderr)
    raise SystemExit(2)


def fetch(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def manifest() -> dict:
    """官方版本清单（带 24h 本地缓存，避免每次审计都打 Mojang）。"""
    cached = CACHE_DIR / "version_manifest_v2.json"
    if cached.exists():
        import time

        if time.time() - cached.stat().st_mtime < MANIFEST_CACHE_SECONDS:
            try:
                return json.loads(cached.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                pass
    data = fetch(MANIFEST_URL)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cached.write_bytes(data)
    return json.loads(data.decode("utf-8"))


def client_jar(version: str) -> Path:
    """返回该版本官方客户端 jar 的本地路径，必要时下载并校验 sha1。"""
    jar = CACHE_DIR / f"client-{version}.jar"
    if jar.exists():
        return jar

    versions = {v["id"]: v for v in manifest()["versions"]}
    if version not in versions:
        die(f"官方版本清单里没有 {version!r}（用 --list 看本仓库的线，或核对版本号拼写）")
    meta = json.loads(fetch(versions[version]["url"]).decode("utf-8"))
    dl = meta["downloads"]["client"]
    size_mb = dl["size"] / 1e6
    log(f"  下载官方客户端 {version} …（{size_mb:.1f} MB，之后会缓存在 dist/.jarcache/）")
    data = fetch(dl["url"], timeout=300)

    got = hashlib.sha1(data).hexdigest()
    if got != dl["sha1"]:
        die(f"{version} 客户端 jar 校验失败：sha1 {got} != {dl['sha1']}（下载被截断或被篡改）")
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    jar.write_bytes(data)
    return jar


def jar_paths(version: str) -> set[str]:
    with zipfile.ZipFile(client_jar(version)) as z:
        return {n for n in z.namelist() if n.startswith(PREFIX)}


def jar_read(version: str, name: str) -> bytes:
    with zipfile.ZipFile(client_jar(version)) as z:
        return z.read(name)


def load_pack(pack_dir: Path) -> dict:
    cfg_path = pack_dir / "build.json"
    if not cfg_path.exists():
        die(f"{cfg_path} 不存在")
    return json.loads(cfg_path.read_text(encoding="utf-8"))


def effective_files(pack_dir: Path, line_id: str) -> dict[str, str]:
    """该线最终会打包进去的文件 → 来源（body / overlay）。overlay 覆盖 body。"""
    out: dict[str, str] = {}
    body = pack_dir
    for p in sorted(body.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(body).as_posix()
        if rel.startswith(SKIP_TOP) or rel in SKIP_NAMES:
            continue
        out[rel] = "body"
    overlay = pack_dir / "overlays" / line_id
    if overlay.is_dir():
        for p in sorted(overlay.rglob("*")):
            if p.is_file():
                out[p.relative_to(overlay).as_posix()] = "overlay"
    return out


def read_source(pack_dir: Path, line_id: str, rel: str, source: str) -> bytes:
    base = pack_dir if source == "body" else pack_dir / "overlays" / line_id
    return (base / rel).read_bytes()


def guess_new_path(name: str, target_names: set[str]) -> list[str]:
    """按文件名在目标版本里找候选新路径。

    只保留同类目录（textures/ ↔ textures/、models/ ↔ models/）的候选，
    否则 `models/block/bee_nest.json` 会被误指到 `blockstates/bee_nest.json`。
    """
    base = name.rsplit("/", 1)[-1]
    rel = name[len(PREFIX):] if name.startswith(PREFIX) else name
    kind = rel.split("/", 1)[0]
    hits = sorted(n[len(PREFIX):] for n in target_names if n.endswith("/" + base))
    same_kind = [h for h in hits if h.split("/", 1)[0] == kind]
    return same_kind or hits


def collect_lines(cfg: dict) -> list[dict]:
    return [ln for ln in cfg["lines"] if ln.get("packFormat") is not None]


def audit_one(pack_dir: Path, cfg: dict, line: dict, baseline: str | None, quiet: bool) -> dict:
    mc = line["mc"]
    if not quiet:
        log(f"\n审计 {cfg['id']} → MC {mc}（线 {line['line']}，pack_format={line['packFormat']}）")
    target = jar_paths(mc)
    base_set = jar_paths(baseline) if baseline else set()

    files = effective_files(pack_dir, line["line"])
    only_target, both, stale_same, stale_diff, pack_own = [], [], [], [], []

    for rel, source in files.items():
        # 主体里的路径本身就是 assets/minecraft/... ，与 jar 内条目可直接比对
        if not rel.startswith(PREFIX):
            pack_own.append(rel)  # 非 minecraft 命名空间（或根目录杂项）：不参与原版比对
            continue
        full = rel
        in_target, in_base = full in target, full in base_set
        if in_target:
            (both if in_base else only_target).append(rel)
        elif baseline and in_base:
            same = read_source(pack_dir, line["line"], rel, source) == jar_read(baseline, full)
            (stale_same if same else stale_diff).append(rel)
        else:
            pack_own.append(rel)

    if not quiet:
        total = len(files)
        pct = lambda n: f"{n} ({n / total * 100:.1f}%)" if total else "0"
        log(f"  该线最终打包 {total} 个文件：")
        log(f"    ✅ 该版本原版也有此路径（正常覆盖）        {pct(len(both))}")
        log(f"    ➕ 原版是后才加的路径（覆盖较新原版文件）  {pct(len(only_target))}")
        if baseline:
            log(f"    ⚪ 你自建的文件（原版从来没有）            {pct(len(pack_own))}")
            log(f"    ⚪ 与 {baseline} 原版逐字节相同（丢了不影响外观） {pct(len(stale_same))}")
            log(f"    ⚠️  你改过、但该版本原版已不读此路径        {pct(len(stale_diff))}  ← 需要 overlay")
        else:
            log(f"    ⚪ 该版本原版没有此路径（未与基线比对，无法区分自建/改名） {pct(len(pack_own))}")

    result = {
        "pack": cfg["id"],
        "line": line["line"],
        "mc": mc,
        "packFormat": line["packFormat"],
        "baseline": baseline,
        "counts": {
            "total": len(files),
            "both": len(both),
            "target_only": len(only_target),
            "pack_own": len(pack_own),
            "stale_identical": len(stale_same),
            "stale_custom": len(stale_diff),
        },
        "needs_overlay": [],
    }

    if stale_diff and not quiet:
        log(f"\n  ⚠️  这 {len(stale_diff)} 个文件在该版本下不生效（你改过，但原版不再读这个路径）：")
        by_dir: dict[str, list[str]] = {}
        for rel in stale_diff:
            by_dir.setdefault(rel.rsplit("/", 1)[0] if "/" in rel else ".", []).append(rel)
        for d in sorted(by_dir, key=lambda k: (-len(by_dir[k]), k)):
            group = by_dir[d]
            hint = ""
            if d in ("texts", "textures/item", "textures/block", "textures/environment"):
                cands: list[str] = []
                for rel in group:
                    cands += guess_new_path(rel, target)
                cands = sorted(set(cands))
                if cands:
                    hint = f"  → 该版本里同名文件在: {', '.join(cands[:3])}"
            log(f"    {d}/  {len(group)} 个{hint}")
        log("\n    完整清单（含猜测的新路径）：")
        for rel in sorted(stale_diff):
            cands = guess_new_path(rel, target)
            if len(cands) == 1:
                hint = f"  → {cands[0]}"
            elif cands:
                hint = f"  → 候选: {', '.join(cands[:3])}"
            else:
                hint = "  → 该文件名在原版里已彻底消失（可能被拆分/合并/弃用）"
            log(f"      {rel}{hint}")
            result["needs_overlay"].append({"path": rel, "target_candidates": cands})
        log("\n    处理方式见 docs/04-路径兼容性审计.md 与 docs/07-改动与-backport.md：给这些线补 overlay，主体保持不变。")

    return result


def cmd_list(pack_dir: Path, cfg: dict) -> None:
    log(f"{cfg['id']} 的版本线：")
    log(f"  {'线':<9} {'MC':<9} {'format':<7} 冻结")
    for ln in cfg["lines"]:
        log(f"  {ln['line']:<9} {ln['mc']:<9} {str(ln.get('packFormat')):<7} {'是' if ln.get('frozen') else '否'}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="audit.py",
        description="审计资源包主体里的文件在某条版本线目标 MC 里是否还生效（对照官方客户端 jar）",
        epilog="例：python tools/audit.py --line mc1.21",
    )
    ap.add_argument("--pack", default="FPP", help="包目录（默认 FPP）")
    ap.add_argument("--line", action="append", help="要审计的版本线（可重复；默认 defaultLine）")
    ap.add_argument("--all", action="store_true", help="审计所有线（会下载多个官方 jar）")
    ap.add_argument("--list", action="store_true", help="只列出版本线")
    ap.add_argument("--baseline", help="基线 MC 版本（默认取本包最老的线，用于区分改名与自建文件）")
    ap.add_argument("--no-baseline", action="store_true", help="跳过基线字节比对")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--strict", action="store_true", help="有需 overlay 的文件时退出码 1")
    args = ap.parse_args(argv)

    if args.json:
        global _LOG
        _LOG = sys.stderr  # 人读的进度/表格走 stderr，stdout 只留 JSON

    pack_dir = (REPO_ROOT / args.pack).resolve()
    cfg = load_pack(pack_dir)

    if args.list:
        cmd_list(pack_dir, cfg)
        return 0

    by_id = {ln["line"]: ln for ln in cfg["lines"]}
    if args.all:
        targets = collect_lines(cfg)
    else:
        ids = args.line or [cfg["defaultLine"]]
        targets = []
        for i in ids:
            if i not in by_id:
                die(f"没有版本线 {i!r}（可用 --list 查看）")
            targets.append(by_id[i])

    skipped = [ln["line"] for ln in targets if ln.get("packFormat") is None]
    targets = list(collect_lines({"lines": targets}))
    if skipped:
        warn(f"跳过 pack_format 未知的线：{', '.join(skipped)}")

    baseline = None
    if not args.no_baseline:
        if args.baseline:
            baseline = args.baseline
        else:
            baseline = cfg["lines"][0]["mc"] if cfg["lines"][0].get("packFormat") is not None else None
    if baseline:
        log(f"基线 = MC {baseline}（主体内容的年代；用于区分「原版改名」与「你自建的文件」）")

    results = [audit_one(pack_dir, cfg, ln, baseline, quiet=False) for ln in targets]

    if args.json:
        print(json.dumps({"results": results}, ensure_ascii=False, indent=2))

    bad = sum(len(r["needs_overlay"]) for r in results)
    if not args.json:
        log(f"\n汇总：{len(results)} 条线，共 {bad} 个文件在新版本下不生效。")
        if bad:
            log("这些是内容迁移工作（补 overlay），不是构建错误 —— 构建依然会成功。")
    if bad and args.strict:
        return 1
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # Windows 控制台默认 cp936
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    raise SystemExit(main())
