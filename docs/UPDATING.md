# 引入 PixelOS 更新

`g9650-seventeen` 是维护分支。`upstream/seventeen` 跟踪官方 manifest。
当前复现清单固定在 `manifests/pinned.xml`；`default.xml` 保留官方结构并引入 legacy VNDK/兼容快照。
固定清单在验证新版本之前不随上游移动。

GitHub 每周及手动检查官方 manifest 和已打补丁项目的上游分支。
发现更新时建立/更新一个跟踪 Issue，不自动合并。该检查不覆盖所有未修改项目的分支变化，
也不能证明补丁能够应用到新平台版本；完整更新仍需要同步候选源码和编译验证。

## 候选分支

```bash
git remote add upstream https://github.com/PixelOS-AOSP/android_manifest.git  # 仅首次需要
git fetch upstream seventeen
git switch -c update/pixelos-YYYY-MM-DD origin/g9650-seventeen
git merge --no-ff upstream/seventeen
```

处理 manifest 合并冲突，保留 `manifests/g9650.xml` 的适配 include。
不要使用 GitHub 的“同步 fork / 丢弃本地提交”覆盖维护分支。
正式更新建议另用有充足空间的候选工作区，或先妥善保存各项目的本地提交与输出；
不要把生产构建工作区的 1,225 个仓库直接切回上游。

## 重放与重定基补丁

用候选分支的 `default.xml` 同步新的上游，在打补丁之前保存 `repo manifest -r` 作为新的基准清单。
如果上游项目基准没有改变，`prepare_source.py` 可正常重放。
如果基准改变，脚本会拒绝未知基准。对每个改变的项目，在新上游上按 `patches/series.json` 的顺序
运行 `git am --3way /path/to/patch`，逐个处理冲突并审核已有语义是否被新上游实现。
冲突时停止；不要批量跳过补丁、自动接受某一侧，或为了继续编译删掉兼容保护。

上游已实现的补丁应明确记录为不再需要，重新导出该项目的 `git format-patch 新基准..HEAD`，
更新队列顺序、每份 patch 的 SHA256、`base` / `base_tree` / `validated_head` / `head_tree`，
以及实际变化文件的 `expected_files`。修改补丁后只更新文件名而不更新索引会被 CI 拒绝。
兼容快照保持固定版本；如果同时更新快照，也需重定基其 8 个队列。

更新 `manifests/pinned-base.xml`，由同一基准加上固定快照重建 `manifests/pinned.xml`。
更新 `provenance/upstream.json` 的 manifest 基准与实际构建/测试记录，保留历史 Release 标签。
不要将 `repo manifest -r` 中重放后仅存在于本机的提交 ID 当成公开下载的上游基准。

## 从现有构建工作区发布修改

完整内核源码在同一仓库的 `g9650-seventeen-kernel` 分支维护，包括 `g9650-validated.config` 和内核编译说明。
5880 的 `kernel-source/klabit-v6.5` 是独立 Git 工作区；PixelOS 的 SYSTEM 构建不自动编译这个内核。
内核工作区的 `origin` 跟踪本仓库，`upstream` 保留 klabit 原仓库。
内核改动提交后，先推送 `g9650-seventeen-kernel`，再在主分支导出内核补丁，并更新 `provenance/upstream.json` 中的内核源码版本与配置摘要。
内核分支的 README 和配置不会重复导出成主分支的源码补丁。

```bash
git -C /path/to/kernel fetch origin g9650-seventeen-kernel
git -C /path/to/kernel switch g9650-seventeen-kernel
git -C /path/to/kernel pull --ff-only origin g9650-seventeen-kernel
# 在内核工作区提交并检查实际改动后：
git -C /path/to/kernel push origin g9650-seventeen-kernel
```

Android 工作区由多个 Git 项目组成。先在修改过的项目中提交源码；
再在本适配仓库中导出补丁，而不是把整套 Android 源码 push 到 manifest 仓库。

```bash
git pull --ff-only origin g9650-seventeen
git fetch upstream seventeen
python3 scripts/check_upstream.py

# 先在改过的 Android / kernel 项目中 git add、git commit。
# 不带 --write 时只预览；加入 --write 才替换补丁和设备 overlay。
python3 scripts/export_changes.py --source /path/to/source --kernel /path/to/kernel
python3 scripts/export_changes.py --source /path/to/source --kernel /path/to/kernel --write
python3 scripts/validate.py --source /path/to/source
python3 scripts/validate.py --replay-source /path/to/source --kernel /path/to/kernel
python3 -m unittest discover -s tests -v
git diff --stat
git add patches overlays scripts docs provenance manifests
git commit -m "Describe the adaptation changes"
git push origin g9650-seventeen
```

导出工具沿用 `patches/series.json` 的基准，不修改手机、构建输出或上游版本。
引入上游更新后，先按上一节重定基并更新基准和固定清单，再运行导出。
新增项目需补充 manifest 和补丁队列索引；工具不会猜测任意未登记目录的用途。
新导出的二进制输入仍由构建者单独准备，不作为源码补丁公开。

## 验证和提升

运行 `scripts/validate.py`、单元测试及 `--replay-source` 的完整补丁重放验证。
在候选环境手动编译 SYSTEM，核对尺寸、分区布局和实际启动行为后再提交 PR。
GitHub CI 只检查公开文件，不编译 Android，也不测试手机；绿色 CI 不能替代这些验证。
PR 合入维护分支后，新建版本标签/Release，记录对应源码 commit、镜像 SHA256 与已知问题。
若某个平台项目长期发生复杂冲突，可独立 fork 该项目，维护适配分支，
再用 manifest 的 `extend-project`/项目覆盖指向 fork；不必一开始复制全部 AOSP 仓库。
