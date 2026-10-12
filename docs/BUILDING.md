# 构建与复现

这里是 PixelOS 17 的 SM-G9650 legacy-vendor/GSI 适配，不是从零编译完整三星设备固件。
`custom_g9650-cp2a-userdebug` 只生成 SYSTEM。现有 FVA4 Vendor、已验证的兼容 BOOT 和 TWRP 是独立前提。

## 已验证的版本

使用 Linux x86-64 和 Android 17 所需的构建依赖，安装 `repo`、Git LFS、Python 3、JDK 17。
完整新建 AOSP 工作区需要至少约 400 GB 空闲空间；已有工作区的增量构建需求较小。
不要在有未保存修改的旧工作区直接运行 `repo sync`，也不要为这个项目运行 `clean` 或 `installclean`。

```bash
git clone -b g9650-seventeen --single-branch https://github.com/yvanliang/pixelos17-g9650.git adaptation
mkdir source
cd source
repo init -u https://github.com/yvanliang/pixelos17-g9650.git \
  -b g9650-seventeen -m manifests/pinned.xml --git-lfs
repo sync -c -j8
cd ..
python3 adaptation/scripts/prepare_source.py --source source
```

`manifests/pinned.xml` 固定未经本地修改的 1,225 个项目及一份兼容源码快照。
271 份补丁分为 37 个队列：28 个 manifest 项目、8 个快照导入项目、1 个独立内核队列。
Android 准备脚本重放前 36 个队列，内核补丁另行维护。原先 240 项审计记录与导出的 Git 提交数口径不同。
快照基准用 tree hash 验证，不依赖构建机器生成的临时 commit ID。

`g9650-upstream/restless/.find-ignore` 会让 Android 的源码扫描器跳过快照原目录，
避免同一批 `Android.bp` / `Android.mk` 与导入后的项目重复定义模块。

## 原始应用输入

编译所需的应用输入记录在 `provenance/external-inputs.json`。
从 [GrapheneOS Camera 93 官方 Release](https://github.com/GrapheneOS/Camera/releases/tag/93)
取得 `Camera-93.apk` 后，准备相机及 legacy GMS 输入：

```bash
python3 adaptation/scripts/materialize_inputs.py --source source --camera-apk /path/to/Camera-93.apk
```

GMS 输入从固定版本的上游 GMS APEX 提取原始签名 APK，需要支持 EROFS 提取的 `fsck.erofs`。
可用 `--fsck-erofs /path/to/fsck.erofs` 指定工具；也可用 `--gms-apk /path/to/PrebuiltGmsCoreVic.apk`
提供原始文件。脚本会校验输入并保留其原始签名。

编译带兼容修复的 TrebleApp，安装 Android SDK platform 33 / build-tools 33.0.2 后：

```bash
export JAVA_HOME=/path/to/jdk17
export ANDROID_HOME=/path/to/android-sdk
bash adaptation/scripts/build_treble_app.sh source
```

Gradle 依赖与缓存需要可用。重新生成 APK 的摘要可能因工具链/签名实现而变化；
`external-inputs.json` 中 TrebleApp 摘要描述历史已验证文件，不保证 APK 字节级可重复。

## SYSTEM

```bash
python3 adaptation/scripts/validate.py --source source
python3 adaptation/scripts/build.py --source source --result-dir artifacts --jobs 32
```

Linux 构建脚本在启动前要求至少 60 GiB 剩余空间，运行中保留 40 GiB。
它使用现有输出和缓存，不执行 `repo sync`、清理或刷机。
若其他构建器共用输出，通过 `G9650_BUILD_LOCK` 指定相同的锁文件。
可用 `G9650_TOOL_PATH` 添加工作区自备工具，不必更改系统级环境。
正常构建生成 `source/out/target/product/tdgsi_arm64_ab/system.img`；
目标名中的 `ab` 不代表 SM-G9650 的物理分区是 A/B。

源码、原始 APK 输入、构建工具和构建时戳都会影响最终镜像摘要；不承诺字节级复现。

## 内核

上游：[klabit87/android_kernel_samsung_sdm845](https://github.com/klabit87/android_kernel_samsung_sdm845)，
基准 `408d5b0f04aebbae4265a056e9a235c8f5a7c133`。
[g9650-seventeen-kernel 分支](https://github.com/yvanliang/pixelos17-g9650/tree/g9650-seventeen-kernel)保存完整内核源码、对应的 `g9650-validated.config` 和编译说明。
主分支的内核源码改动摘要仍在 `patches/projects/kernel__samsung__sdm845/`，内核分支已经应用这两份补丁。
保留其 GPL-2.0 许可证与完整对应源码。内核通常需要该项目的旧版 GCC 工具链。
当前真机使用的兼容内核已启用 DM_VERITY、BLK_CGROUP 及其依赖，并包含已安装的 RCU/qtaguid 修复。
Release 提供这套内核对应的未 root BOOT；首次安装应先刷 Boot，再清空 Data 并刷 SYSTEM。
内核版本字符串仍是 `4.9.186-klabitV6.5`，不能只用这个字符串判断是否包含本项目的配置和修复。
完整对应内核源码、配置和编译步骤见[内核分支的 README](https://github.com/yvanliang/pixelos17-g9650/blob/g9650-seventeen-kernel/README.md)。
SYSTEM 构建脚本不会自动编译或刷入内核，也不会自动取得 root。
