# Downloads and installation

Download the current [PixelOS 17.0 (Android 17) release for SM-G9650](https://github.com/yvanliang/pixelos17-g9650/releases/tag/android17-g9650-20261010).

Version tags use `android17-g9650-YYYYMMDD`, where the date identifies the image build. This is an unofficial, experimental release.

## Downloads

- `PixelOS-17.0-Android17-G9650-20261010-UNOFFICIAL-boot.img.xz` contains the project's compatible kernel and ramdisk. It is **unrooted**; flash the extracted image to **Boot**.
- `PixelOS-17.0-Android17-G9650-20261010-UNOFFICIAL-system.img.xz` contains Android 17. Flash the extracted image to **System Image**.

An XZ-capable archive tool can extract the images on Windows, macOS, or Linux. With XZ command-line tools installed, extract them while keeping the downloaded archives:

```bash
xz -dk PixelOS-17.0-Android17-G9650-20261010-UNOFFICIAL-boot.img.xz
xz -dk PixelOS-17.0-Android17-G9650-20261010-UNOFFICIAL-system.img.xz
```

Flash the extracted `.img` files. The `.xz` archives and GitHub's automatically generated source-code ZIP are not flashable images.

## Required setup

Use **SM-G9650 / star2qltechn**, an unlocked bootloader, **Samsung Android 10 FVA4** vendor prepared for this Treble setup, and **TWRP 3.7.0_9-0**. Keep the bootloader unlocked.

The compatible BOOT uses a patched **klabit V6.5 / Linux 4.9.186** kernel with the required dm-verity/block-cgroup configuration and the SELinux RCU/qtaguid fixes already used on the test phone. Its version string remains `4.9.186-klabitV6.5`; that string alone does not establish that another kernel has the same configuration and patches.

The release supplies Boot and System. It assumes the firmware/vendor and recovery preparation is complete; it does not include the earlier Odin, bootloader-unlocking, or Vendor preparation process. Other Galaxy S9/S9+ models are not supported by this release.

## First installation from stock or another ROM

**Install the compatible BOOT first, format Data, then install SYSTEM.** Stay in recovery until both images are installed.

1. Extract both images and place them on a microSD card, USB storage, or another location that will remain accessible after formatting Data. Boot into TWRP.
2. Choose **Install → Install Image**, select `...-boot.img`, and flash it to **Boot**.
3. **Format Data**. A first installation needs clean Data rather than the previous ROM's apps, settings, and encryption state. This **erases internal storage**, including photos and downloads. A cache/Dalvik wipe alone is insufficient.
4. Choose **Reboot → Recovery** if needed to reload Data. Then use **Install → Install Image** to flash `...-system.img` to **System Image**.
5. Keep the prepared FVA4 Vendor and TWRP Recovery, then reboot into the system.

The tested TWRP build has shown instability while formatting Data on this device. If formatting fails or recovery crashes, resolve that problem before proceeding.

## Updating this adaptation

If this PixelOS adaptation and its compatible BOOT are already installed, flash the new SYSTEM image to **System Image** in TWRP. **Keep Boot, Vendor, Recovery, and Data; do not format Data.** A kernel reinstall is only needed when a release explicitly requires a BOOT update.

The release BOOT is unrooted. Flashing it over a Magisk-patched Boot removes that boot patch. Root can be installed separately after the first installation; SYSTEM-only updates retain the existing Boot.

## Current status

Wi-Fi, Bluetooth, mobile network, camera, fingerprint, and brightness adjustment work in the supported setup. Iris recognition is not supported.

SELinux is currently Permissive. The older kernel has per-app network firewall and KeyMint limitations, and banking, DRM, or Play Integrity checks may fail. The SYSTEM image has booted on the test phone; a full regression test of every app and hardware function has not been completed for this build. The BOOT uses the same kernel, device trees, and original ramdisk as the tested pre-root setup; the running rooted setup retains the same kernel and device trees.

See the [README](../README.md) for screenshots, the [SYSTEM build guide](BUILDING.md), or the [kernel source and build notes](https://github.com/yvanliang/pixelos17-g9650/tree/g9650-seventeen-kernel).
