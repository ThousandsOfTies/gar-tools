# FRDM-IMX91S UUU Target

This Target Pack follows the factory-provisioning pattern used by the existing
NXP product: UUU executes a product-owned `.lst` script and the script refers
to bootloader, initramfs, rootfs, and persistent-storage artifacts in the same
bundle. The default command is equivalent to:

```bash
uuu <Factory-uuu-gar-servo-pet.lst>
```

The artifact bundle is laid out so relative paths in the script remain valid:

```text
Factory-uuu-gar-servo-pet.lst       # deploy.image: exactly one file
pub/
  u-boot/flash_gar_servo_pet.bin
  rootfs/rootfs.squashfs
  rootfs/usr.local.tar.bz2
  mfgtools/fsl-image-mfgtool-initramfs-imx_mfgtools.cpio.zst
```

The supporting files are declared under `deploy.uuu`. GAR runs UUU with the
script's parent directory as its working directory, so `pub/...` references
inside the script resolve without a shell wrapper. The command is an argv
array; GAR never evaluates it through a shell.

The `.lst` file owns the board-specific SDP/FBK sequence, partition layout,
SquashFS/overlay setup, and any factory updater initialization. Do not reuse a
script from another i.MX board until its `flash_*` binary and eMMC partition
layout have been verified.

## Connections

The download connection and the debug console are separate:

- Put the board into Serial Downloader mode and connect its USB OTG/download
  port for UUU.
- Connect the USB-C debug UART (`J11`) for boot verification. The first CH343
  serial device is the Cortex-A console at 115200 8N1.

Set the workspace target serial device before deploying when `serialVerify` is
enabled:

```json
{
  "target": {
    "serial": "/dev/ttyCH343USB0"
  }
}
```

The Product artifact must contain exactly one UUU script in
`deploy.image.files`. Its `src` is passed to the configured UUU command as
`{image}`. All files referenced by that script must also be present in the
artifact bundle (normally via `deploy.uuu.files`).
