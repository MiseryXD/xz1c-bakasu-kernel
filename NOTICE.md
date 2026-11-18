# NOTICE / 第三方组件说明

本仓库**不包含**任何第三方二进制（boot.img、APK、`.ko`、Sony ramdisk）。
以下项目仅以补丁、脚本和文档的形式被引用：

| 项目 | 用途 | 许可 |
|---|---|---|
| [whatawurst/android_kernel_sony_msm8998](https://github.com/whatawurst/android_kernel_sony_msm8998) | 内核源码基线（lineage-17.1, commit `9f9628377bbe`），与本机 Havoc-OS 3.11 构建同源 | GPL-2.0 |
| [Baka-SU/BakaSU](https://github.com/Baka-SU/BakaSU) | KernelSU 分支，内核驱动与手动钩子（tag `v4.2.0-rc3`） | GPL-2.0 |
| [tiann/KernelSU](https://github.com/tiann/KernelSU) | BakaSU 的上游 | GPL-2.0 |
| AOSP prebuilts `clang-r353983c` | 与 ROM 一致的 clang 9.0.3 工具链 | Apache-2.0 / LLVM |

`patches/0001-kernelsu-manual-hooks.patch` 是对 BakaSU 集成步骤的记录，其内容版权归
KernelSU/BakaSU 作者所有，按 GPL-2.0 分发。
