# BSP component contract

The Target Pack does not redistribute NXP firmware or build outputs. A Product
or CI system supplies components built from one internally consistent NXP BSP
release.

The validated baseline used these NXP branches/configurations:

- U-Boot: `lf_v2024.04`
- Linux: `lf-6.6.y`
- ARM Trusted Firmware: `lf_v2.8`
- imx-mkimage: `lf-6.6.3_1.0.0`
- NAND U-Boot configuration: `imx91_11x11_frdm_imx91s_spinand_defconfig`
- DTB: `imx91-11x11-frdm-imx91s.dtb`

Do not casually mix releases. DDR training firmware, ELE firmware, ATF,
U-Boot, imx-mkimage, kernel, DTB, and manufacturing initramfs form one BSP
compatibility set.

## Two boot images are required

| Role | Required property |
|---|---|
| RAM boot image | Proven SD/manufacturing configuration that survives SDPS and exposes Fastboot |
| NAND boot image | Built for SPI-NAND and accepted by `fspinand` for FCB/DBBT and redundant firmware installation |

Products choose both filenames in `imx91s-uuu.env`. They may use branded
names; the Target Pack does not assume them.

## Root filesystem inputs

The base root filesystem is supplied as `rootfs.squashfs`. The manufacturing
Linux expands it into a writable UBIFS volume because the final target is raw
SPI-NAND, not a block device. Optional Product content is supplied as
`usr.local.tar.bz2` and is extracted without retaining build-host ownership.

The manufacturing initramfs must contain the FBK daemon and MTD/UBI tools used
by the factory template. The generator validates file presence and sizes; the
running manufacturing image validates its commands and live MTD geometry
before destructive writes.

## Build-system integration

Keep Product-selected names and the confirmed write gate in a committed
Product configuration. Keep machine-local values such as the path to `uuu`
outside it. Stage the component tree with `provisioning/uuu/stage.sh`; do not
hand-edit its generated `.lst` or padded transfer files.
