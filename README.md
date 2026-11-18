# BakaSU on Sony XZ1 Compact (lilac) — Havoc-OS 3.11, kernel 4.4.240

在 Sony Xperia XZ1 Compact（`lilac`，G8441 / SO-02K）上，为 **Havoc-OS 3.11（Android 10）**
自编译内核并集成 **BakaSU**（KernelSU 分支）。记录一个会让手机**卡在开机动画**的内核陷阱，
以及复现所需的配置与补丁。

A from-source kernel port of BakaSU (KernelSU fork) for the Sony Xperia XZ1 Compact running
Havoc-OS 3.11 (Android 10, kernel 4.4.240).

## 结果 / Result

- 内核 `4.4.240-whatawurst+`，用 **clang 9.0.3 (r353983c)** 编译（与 ROM 一致）
- `/vendor/lib/modules` 的 6 个模块全部加载：`wlan` `kscl` `fpc1145` `ldo_vibrator` `sim_detect` `bu520x1nvx`
- BakaSU 管理器显示「工作中」，`ksud` 正常启动，无开机卡死
- 只改 boot 分区，system/vendor/data 未动

## 两个关键问题 / Two kernel traps

### 1. 编译器必须和 ROM 完全一致（clang 9.0.3 / r353983c）

GCC 或 clang 14 编译出的内核 vermagic 和 `module_layout` CRC 都对，但 `printk`、
`__stack_chk_fail` 的 genksyms CRC 与原厂不同 → 所有 vendor `.ko` 拒载
（`disagrees about version of symbol ...`）。只有 **r353983c** 编出来的 425 个符号全部匹配。

### 2. `ARCH_RELOCATES_KCRCTAB` 与 GNU ld 冲突

`arch/arm64/include/asm/module.h` 定义了 `ARCH_RELOCATES_KCRCTAB`，内核会把 CRC 减去
`reloc_start`。lld 构建的 CRC 是段内相对值（原厂正常），而 GNU ld 保留 genksyms 的绝对值，
结果每个符号都变成 `0xffffffe7xxxxxxxx`，所有模块报
`disagrees about version of symbol module_layout` / `Exec format error`。

表现为**卡在开机动画**：`insmod` 全失败 → 振动/指纹 HAL 崩溃 → watchdog 杀死 system_server。
最快的判断信号是 `cat /proc/modules | wc -l`（正常 6，异常 0）。

**修复**：本 build 注释掉该宏（见 `patches/0002-*`）。这不是跳过校验，而是让比较走绝对值，
CRC 验证依然真实有效。

## 仓库内容 / Layout

```
config/config_lilac.txt     设备 /proc/config.gz 导出的内核配置
config/ksu.config           BakaSU 所需的内核配置片段
patches/0001-*.patch        BakaSU 手动钩子（fs/stat.c fs/exec.c fs/open.c kernel/reboot.c + Kconfig/Makefile）
patches/0002-*.patch        arm64: 关闭 ARCH_RELOCATES_KCRCTAB（GNU ld 构建）
scripts/repack_boot.py      替换 boot.img 内核、保留 ramdisk 的 v0 header 重打包
```

## 用法 / Build

```bash
# 1. 内核源码（与 ROM 同源）
git clone -b lineage-17.1 https://github.com/whatawurst/android_kernel_sony_msm8998 kernel
cd kernel && git checkout 9f9628377bbe

# 2. BakaSU（tag 与管理器版本对应）
git clone -b v4.2.0-rc3 https://github.com/Baka-SU/BakaSU KernelSU
ln -s ../KernelSU/kernel drivers/kernelsu

# 3. 打补丁
git apply ../patches/0001-kernelsu-manual-hooks.patch
git apply ../patches/0002-arm64-disable-ARCH_RELOCATES_KCRCTAB.patch

# 4. 配置（设备配置 + BakaSU 片段）
mkdir -p out && cp ../config/config_lilac.txt out/.config
scripts/kconfig/merge_config.sh -O out out/.config ../config/ksu.config

# 5. 构建（clang 9.0.3）
make O=out ARCH=arm64 CC=clang CLANG_TRIPLE=aarch64-linux-gnu- \
     CROSS_COMPILE=aarch64-linux-gnu- CROSS_COMPILE_ARM32=arm-linux-gnueabihf- \
     -j$(nproc) Image.gz-dtb

# 6. 用 ROM 原版 boot.img 重打包（ramdisk 不动）
python3 ../scripts/repack_boot.py boot_havoc.img out/arch/arm64/boot/Image.gz-dtb boot_ksu.img
fastboot flash boot boot_ksu.img
```

## 验证 / Verify

```bash
adb shell 'getprop sys.boot_completed'        # 1
adb shell 'cat /proc/modules | wc -l'         # 6
adb shell 'uname -r'                          # 4.4.240-whatawurst+
```

## 已知限制 / Notes

- 该内核无 `CONFIG_KPROBES`，KernelSU 走 `CONFIG_KSU_MANUAL_HOOK`（非官方支持路径，4.4 属边界用法）
- 管理器必须与内核版本配套（v4.2.0-rc3 / KernelSU 35171），不要单独升级管理器
- 不要 OTA：boot 与 vendor 模块是绑定的，换 ROM 必须重编

## 调试记录 / Debug notes

设备与源码：msm8998，Havoc-OS 3.11（`QQ3A.200805.001`），内核源码 `9f9628377bbe`；设备
`/proc/config.gz` 与源码生成的 `.config` 逐项对比 missing 0 / changed 0。

CRC 对比（GCC 构建时）：

```
printk            kernel 0x27e1a049  module 0x985558a1   ✗
__stack_chk_fail  kernel 0xdb7305a1  module 0xf0fdf6cb   ✗
```

在 `check_version()` 里临时打印实际比较值，可一眼看出 `ARCH_RELOCATES_KCRCTAB` 的问题：

```
KSDBG: dev_alloc_name kernel_crc=0xffffffe7e508dca4 module_crc=0xe7a8dca4
```

手动钩子位置（`CONFIG_KSU_MANUAL_HOOK`，该内核无 KPROBES）：

| 文件 | 钩子 |
|---|---|
| `fs/stat.c` | 对 init 的 stat 拦截 |
| `fs/exec.c` | `su` / ksud 执行重定向（3.14+ 分支） |
| `fs/open.c` | init 文件读取（4.19− 分支） |
| `kernel/reboot.c` | 重启命令处理 |
| setuid / initrc / input | 由 LSM 自动注入（`CONFIG_KSU_MANUAL_HOOK_AUTO_*`） |

注意：KSU 的 `su` 拦截路径固定为 `/system/bin/su`，该 ROM 没有这个文件，所以 adb shell 无法
`su`（管理器给 app 的 root 不受影响）。

## 不包含 / Not included

`boot.img`、BakaSU 管理器 APK、Sony 私有 ramdisk、`/vendor` 二进制模块都没有放进仓库
（版权原因），请自行从 ROM 包提取。

## Credits

- [whatawurst/android_kernel_sony_msm8998](https://github.com/whatawurst/android_kernel_sony_msm8998) — 本机同源内核树（GPL-2.0）
- [Baka-SU/BakaSU](https://github.com/Baka-SU/BakaSU) — KernelSU 分支与管理器（GPL-2.0）
- [tiann/KernelSU](https://github.com/tiann/KernelSU) — 上游
- AOSP `clang-r353983c` — 与 Havoc 构建一致的编译器

## License

内核补丁（`patches/`）衍生自 GPL-2.0 内核，遵循 **GPL-2.0**；`scripts/` 下的工具为 **MIT**。
