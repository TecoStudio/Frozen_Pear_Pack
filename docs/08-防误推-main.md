# 08 · 防误推 main —— 三层防护

目标：**手滑的时候直接在本地就被挡住**，而不是靠事后回滚。

## 第 1 层：GitHub 分支保护（服务端，最硬）

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

## 第 2 层：仓库自带的本地钩子

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

（钩子内容见 [`.githooks/`](../.githooks/)，已实测：master 被拦、feature 与 tag 放行、
`ALLOW_MAIN=1` 放行。）

## 第 3 层：git 自身兜底

`branch.master.pushRemote = __no_push__` 让"在 master 上直接敲 `git push`"失败：

```
error: failed to push some refs to '__no_push__'
```

要真想推必须写全 `git push origin master`（所以不会"手滑"，但也不会被彻底锁死）。

## 日常流程（照这个做就不会出事）

```sh
git switch -c mc1.21/fix-lantern-animation   # 按 线/主题 开分支
# …改文件…
python tools/build.py --line mc1.21 --dev     # 本地验证
git commit -m "fix: ..."
git push -u origin HEAD                       # 永远不写 master 字样
# 然后开 PR → 合并
```

## 撤销这些防护

```sh
git config --unset core.hooksPath
git config --unset branch.master.pushRemote
```

> 注意：第 1 层在服务端，撤销需要在 GitHub 上改，本地解不掉。
> 另外这三层都**不防"把 tag 推到错的提交上"** —— 发版前按
> [06-发布规范](06-发布规范.md) 检查 tag 指向。
