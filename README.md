# PixelOS 17.0 (Android 17) kernel for SM-G9650

The release BOOT contains the project's unrooted, compatible **klabit V6.5 / Linux 4.9.186** kernel and the original ramdisk/device trees used in the tested FVA4 setup. This is the kernel used on the test phone, including the following changes:

- Enable `CONFIG_DM_VERITY`, `CONFIG_BLK_CGROUP`, and their required dependencies for Android's APEX and cgroup setup.
- Restore the upstream SELinux RCU error-pointer handling used during inode permission checks.
- Set the Android qtaguid accounting groups while retaining the existing UID checks.

The kernel still reports `4.9.186-klabitV6.5`. Use the project's BOOT image for the matching configuration and fixes. For installation, see [Downloads and installation](https://github.com/yvanliang/pixelos17-g9650/blob/g9650-seventeen/docs/RELEASES.md).

## Source

This branch contains the complete kernel source for the compatible SM-G9650 BOOT. It is based on [klabit87/android_kernel_samsung_sdm845](https://github.com/klabit87/android_kernel_samsung_sdm845) at commit `408d5b0f04aebbae4265a056e9a235c8f5a7c133`, with the SELinux RCU and qtaguid changes applied. The validated build configuration is [g9650-validated.config](g9650-validated.config).

The PixelOS manifest, SYSTEM adaptation, and installation guide are maintained on [g9650-seventeen](https://github.com/yvanliang/pixelos17-g9650/tree/g9650-seventeen). The original Linux README, `COPYING` file, and copyright notices remain in this source tree.

## Build the kernel

Use Linux x86-64 with GCC/make, binutils, bc, bison, flex, and the host development libraries required by this older kernel. Use the historical Android AArch64 GCC 4.9 toolchain for this build.

Get this kernel branch and the pinned toolchain. Run these commands from a directory where you want to keep the build:

```bash
git clone --branch g9650-seventeen-kernel --single-branch --depth 1 \
  https://github.com/yvanliang/pixelos17-g9650.git g9650-kernel-20261010
git clone https://github.com/LineageOS/android_prebuilts_gcc_linux-x86_aarch64_aarch64-linux-android-4.9.git gcc-aarch64-4.9
git -C gcc-aarch64-4.9 checkout 5e030eafe024784a73cdf47e6936ac0dbfc763dc
```

Build outside the source directory, keeping the supplied configuration:

```bash
mkdir kernel-out
cp g9650-kernel-20261010/g9650-validated.config kernel-out/.config
g9650_kernel_out="$(pwd)/kernel-out"
g9650_gcc_bin="$(pwd)/gcc-aarch64-4.9/bin"
g9650_gcc="$g9650_gcc_bin/aarch64-linux-android-gcc"
if [ -x "$g9650_gcc_bin/real-aarch64-linux-android-gcc" ]; then
  g9650_gcc="$g9650_gcc_bin/real-aarch64-linux-android-gcc"
fi

make -C g9650-kernel-20261010 O="$g9650_kernel_out" ARCH=arm64 \
  CROSS_COMPILE="$g9650_gcc_bin/aarch64-linux-android-" \
  CC="$g9650_gcc" HOSTCC=gcc olddefconfig

make -C g9650-kernel-20261010 O="$g9650_kernel_out" ARCH=arm64 \
  CROSS_COMPILE="$g9650_gcc_bin/aarch64-linux-android-" \
  CC="$g9650_gcc" HOSTCC=gcc -j16 Image.gz-dtb
```

Adjust `-j16` to suit the build machine. The outputs are in `kernel-out/arch/arm64/boot/`.

This compiles the kernel, not a complete BOOT image. Repacking requires the compatible ramdisk, original device trees, and Samsung boot-header/footer settings from the release BOOT. Keep those components when replacing the kernel. The SYSTEM build script does not build, install, or root BOOT. Build timestamps and toolchain details can change the resulting bytes.
