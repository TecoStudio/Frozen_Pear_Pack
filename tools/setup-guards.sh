#!/bin/sh
# Frozen Pear Pack —— 安装本地防误推防护（clone 之后执行一次）
#
#   sh tools/setup-guards.sh
#
# 第 2 层：启用仓库内的 .githooks（阻止在 master 上提交 / 推送）
# 第 3 层：把 master 的 pushRemote 指向一个不存在的远端，
#          于是"在 master 上直接敲 git push"会失败，必须显式写
#          git push origin master 才会生效。

set -e

repo_root=$(git rev-parse --show-toplevel)
cd "$repo_root"

git config core.hooksPath .githooks
git config branch.master.pushRemote __no_push__

echo "✅ 已启用 core.hooksPath = .githooks"
echo "✅ 已设置 branch.master.pushRemote = __no_push__"
echo ""
echo "效果："
echo "  - 在 master 上 git commit          → 被拒绝"
echo "  - git push（含 master）            → 被拒绝 / 失败"
echo "  - 正常流程：git switch -c <line>/<topic> && git push -u origin HEAD"
echo "  - 单次放行：ALLOW_MAIN=1 git push origin master"
echo ""
echo "注意：如果主分支不叫 master，请自行调整上面两条命令。"
