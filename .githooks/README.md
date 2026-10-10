# .githooks

本地防护钩子，用来阻止"手滑把工作提交/推到 master"。属于防误操作的第 2 层
（第 1 层是 GitHub 的 branch protection，第 3 层是 `branch.master.pushRemote` 兜底，
详见 [docs/08-防误推-main.md](../docs/08-防误推-main.md)）。

## 安装（clone 之后执行一次）

```sh
sh tools/setup-guards.sh
```

等价于：

```sh
git config core.hooksPath .githooks
git config branch.master.pushRemote __no_push__
```

## 行为

| 钩子 | 触发时机 | 行为 |
| --- | --- | --- |
| `pre-commit` | 在 master 上 `git commit` | 拒绝，提示先开分支 |
| `pre-push` | 推送 `refs/heads/master` | 拒绝，提示走 PR |

## 临时放行 / 撤销

```sh
ALLOW_MAIN=1 git commit -m "..."     # 单次放行提交
ALLOW_MAIN=1 git push origin master  # 单次放行推送
git config --unset core.hooksPath    # 彻底关闭钩子
git config --unset branch.master.pushRemote   # 恢复普通 git push
```
