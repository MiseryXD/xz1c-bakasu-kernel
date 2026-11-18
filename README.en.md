# BakaSU on Sony XZ1 Compact (lilac) — Havoc-OS 3.11, kernel 4.4.240

A from-source kernel port of **BakaSU** (a KernelSU fork) for the Sony Xperia XZ1 Compact
(`lilac`, G8441 / SO-02K) running **Havoc-OS 3.11** (Android 10). It also documents the two
non-obvious kernel traps that make a self-built kernel hang on the boot animation.

中文说明见 [README.md](README.md)。

## Result

- Kernel `4.4.240-whatawurst+`, built with **clang 9.0.3 (r353983c)** — the same compiler as the ROM
- All six vendor modules load from `/vendor/lib/modules`:
  `wlan` `kscl` `fpc1145` `ldo_vibrator` `sim_detect` `bu520x1nvx`
- BakaSU manager reports *working*; `ksud` starts normally; no boot hang
- Only the `boot` partition is modified — `system` / `vendor` / `data` untouched

Verified on: Havoc-OS 3.11, `QQ3A.200805.001`, build 2020-11-20, msm8998.

## The two kernel traps

### 1. The compiler must match the ROM exactly (clang 9.0.3 / r353983c)

Kernels built with GCC or clang 14 have the right vermagic and `module_layout` CRC, but the
genksyms CRCs for `printk` and `__stack_chk_fail` differ from the stock kernel — so every vendor
`.ko` is rejected with `disagrees about version of symbol ...`. Only r353983c produces all 425
symbols matching.

### 2. `ARCH_RELOCATES_KCRCTAB` conflicts with GNU ld

`arch/arm64/include/asm/module.h` defines `ARCH_RELOCATES_KCRCTAB`, which makes the kernel subtract
`reloc_start` from each CRC. Builds linked with lld store segment-relative values (what the stock
kernel has), while GNU ld keeps the absolute genksyms value — so every symbol becomes
`0xffffffe7xxxxxxxx` and every module fails with
`disagrees about version of symbol module_layout` / `Exec format error`.

Symptom: the phone hangs on the boot animation — `insmod` fails for all modules, the vibrator and
fingerprint HALs crash, and the watchdog kills `system_server`. The quickest signal is
`cat /proc/modules | wc -l` (6 when healthy, 0 when broken).

**Fix**: this build comments the macro out (`patches/0002-*`). That is not disabling the check —
it makes the comparison use absolute values, so CRC verification stays fully effective.

## Layout

```
config/config_lilac.txt     kernel config exported from the device's /proc/config.gz
config/ksu.config           BakaSU kernel config fragment
patches/0001-*.patch        BakaSU manual hooks (fs/stat.c fs/exec.c fs/open.c kernel/reboot.c + Kconfig/Makefile)
patches/0002-*.patch        arm64: drop ARCH_RELOCATES_KCRCTAB for GNU ld builds
scripts/repack_boot.py      replace the kernel inside boot.img, keep the stock ramdisk (v0 header)
```

## Build

```bash
# 1. Kernel source (same tree the ROM was built from)
git clone -b lineage-17.1 https://github.com/whatawurst/android_kernel_sony_msm8998 kernel
cd kernel && git checkout 9f9628377bbe

# 2. BakaSU (tag must match the manager version)
git clone -b v4.2.0-rc3 https://github.com/Baka-SU/BakaSU KernelSU
ln -s ../KernelSU/kernel drivers/kernelsu

# 3. Apply patches
git apply ../patches/0001-kernelsu-manual-hooks.patch
git apply ../patches/0002-arm64-disable-ARCH_RELOCATES_KCRCTAB.patch

# 4. Configure (device config + BakaSU fragment)
mkdir -p out && cp ../config/config_lilac.txt out/.config
scripts/kconfig/merge_config.sh -O out out/.config ../config/ksu.config
make O=out ARCH=arm64 olddefconfig

# 5. Build (clang 9.0.3 on PATH)
make O=out ARCH=arm64 CC=clang CLANG_TRIPLE=aarch64-linux-gnu- \
     CROSS_COMPILE=aarch64-linux-gnu- CROSS_COMPILE_ARM32=arm-linux-gnueabihf- \
     -j$(nproc) Image.gz-dtb

# 6. Repack with the ROM's stock boot.img (ramdisk untouched)
python3 ../scripts/repack_boot.py boot_havoc.img out/arch/arm64/boot/Image.gz-dtb boot_ksu.img
fastboot flash boot boot_ksu.img
```

The toolchain is AOSP prebuilt `clang-r353983c` (clang 9.0.3, from the `android-10.0.0_r*` branch);
put its `bin/` first in `PATH` and verify with `clang --version`.

## Verify

```bash
adb shell 'getprop sys.boot_completed'        # 1
adb shell 'cat /proc/modules | wc -l'         # 6
adb shell 'uname -r'                          # 4.4.240-whatawurst+
```

## Notes

- This kernel has no `CONFIG_KPROBES`, so KernelSU uses `CONFIG_KSU_MANUAL_HOOK` — a path outside
  KernelSU's officially supported kernels; 4.4 is an edge case
- The manager must match the kernel build (v4.2.0-rc3 / KernelSU 35171); do not upgrade it alone
- Do not OTA: boot and vendor modules are tied together, a new ROM build requires a rebuild

## Debug notes

Device and source: msm8998, Havoc-OS 3.11 (`QQ3A.200805.001`), kernel source `9f9628377bbe`.
The device's `/proc/config.gz` and the generated `.config` were compared item by item: missing 0 /
changed 0.

CRC comparison with a GCC build:

```
printk            kernel 0x27e1a049  module 0x985558a1   ✗
__stack_chk_fail  kernel 0xdb7305a1  module 0xf0fdf6cb   ✗
```

Printing the actual compared values inside `check_version()` shows the `ARCH_RELOCATES_KCRCTAB`
problem immediately:

```
KSDBG: dev_alloc_name kernel_crc=0xffffffe7e508dca4 module_crc=0xe7a8dca4
```

Manual hook locations (`CONFIG_KSU_MANUAL_HOOK`, no KPROBES on this kernel):

| file | hook |
|---|---|
| `fs/stat.c` | stat interception for init |
| `fs/exec.c` | `su` / ksud exec redirection (3.14+ branch) |
| `fs/open.c` | init file reads (4.19− branch) |
| `kernel/reboot.c` | reboot command handling |
| setuid / initrc / input | injected by LSM (`CONFIG_KSU_MANUAL_HOOK_AUTO_*`) |

Note: KernelSU intercepts a fixed path, `/system/bin/su`. This ROM has no such file, so `su` does
not work from `adb shell` (root granted to apps by the manager is unaffected).

## Not included

`boot.img`, the BakaSU manager APK, Sony's proprietary ramdisk and the `/vendor` binary modules are
not in this repository (copyright). Extract them from the ROM package yourself. Ready-to-flash
images are attached to the Releases page instead.

## Disclaimer

- **Only for Havoc-OS 3.11 (`QQ3A.200805.001`, build 2020-11-20).** Other ROMs or other builds will hang at the boot animation.
- Flashing carries risk (brick, data loss). Back up first and make sure your bootloader is unlocked.
- Provided as-is, without warranty; you are responsible for your own device.
- Not affiliated with Sony, Havoc-OS, or the KernelSU / BakaSU projects.

## Credits

- [whatawurst/android_kernel_sony_msm8998](https://github.com/whatawurst/android_kernel_sony_msm8998) — the kernel tree the ROM was built from (GPL-2.0)
- [Baka-SU/BakaSU](https://github.com/Baka-SU/BakaSU) — KernelSU fork and manager (GPL-2.0)
- [tiann/KernelSU](https://github.com/tiann/KernelSU) — upstream
- AOSP `clang-r353983c` — compiler matching the Havoc build

## License

The kernel patches (`patches/`) derive from a GPL-2.0 kernel and are **GPL-2.0**; the tools under
`scripts/` are **MIT**.
