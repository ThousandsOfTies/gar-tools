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
  u-boot/flash_gar_servo_pet_spinand.bin
  kernel/Image
  kernel/imx91-11x11-frdm-imx91s.dtb
  uuu-ram/flash_gar_servo_pet_spinand.bin.padded
  uuu-ram/Image.padded
  uuu-ram/imx91-11x11-frdm-imx91s.dtb.padded
  uuu-ram/fsl-image-mfgtool-initramfs-imx_mfgtools.cpio.zst.padded
  rootfs/rootfs.squashfs
  rootfs/usr.local.tar.bz2
  mfgtools/fsl-image-mfgtool-initramfs-imx_mfgtools.cpio.zst
```

The supporting files are declared under `deploy.uuu`. The kernel and DTB are
needed because UUU first RAM-boots the SD/manufacturing U-Boot and the
manufacturing initramfs before switching to the Linux `FBK` protocol. The
separate SPI-NAND image is passed to `fspinand` for persistent installation.
The script uses the fixed MTD layout in the FRDM-IMX91S DTS. GAR runs UUU with
the script's parent directory as its working directory, so `pub/...`
references resolve without a shell wrapper. GAR never evaluates the command
through a shell.

Before confirming the layout, power the board off and set the official
FRDM-IMX91S boot switch to Serial Downloader: `SW1[4-1] = 0001`, i.e.
`SW1-4=OFF`, `SW1-3=OFF`, `SW1-2=OFF`, `SW1-1=ON` (NXP's table defines
`1=ON`, `0=OFF`). Connect the UUU cable to USB1 (`J5`), not the debug UART
(`J11`), then power the board on. Generate the read-only probe from the
Product repository and run it:

```bash
GarServoPet/scripts/generate-imx91s-layout-probe.sh --validate
cd GarServoPet/artifacts/from-codespace
/home/user/.local/bin/uuu Inspect-imx91s-layout.lst
```

The probe only boots the kernel/initramfs into RAM and prints `/proc/mtd`, MTD
names, sizes, erase/write geometry, and UBI state. It does not erase, format,
mount, or write NAND. Set `GAR_IMX91S_NAND_LAYOUT_CONFIRMED=1` only after mtd0
through mtd4 match `bootloader`, `config`, `kernel`, `dtb`, and `rootfs`.

The `.lst` file owns the board-specific SDP/FBK sequence, SPI-NAND firmware
installation, raw MTD writes, and UBIFS root creation. Do not reuse a script
from another i.MX board until its NAND-capable `flash_*` binary and MTD layout
have been verified.

## Connections

The download connection and the debug console are separate:

- Put the board into Serial Downloader mode and connect its USB OTG/download
  port for UUU.
- Connect the USB-C debug UART (`J11`) for boot verification. The first
  CH342/CH343 serial interface is the Cortex-A console at 115200 8N1. With
  the observed CH342 adapter under WSL2, this is usually `/dev/ttyACM0`
  (Windows COM5); the second interface is `/dev/ttyACM1` (Windows COM4).

Set the workspace target serial device before deploying when `serialVerify` is
enabled:

```json
{
  "target": {
    "serial": "/dev/ttyACM0"
  }
}
```

## WSL2 USB pass-through

When GAR runs inside WSL2, a USB device attached to Windows is not visible in
WSL automatically and does not need to be mounted as a filesystem. Install
`usbipd-win`, then use an elevated Windows PowerShell to share and attach the
UUU port:

```powershell
usbipd list
usbipd bind --busid <UUU_BUSID>
usbipd attach --wsl --busid <UUU_BUSID>
```

The UUU port should appear in the Windows list as NXP `VID:PID 1fc9:0159`
(MX91 SDPS). The CH342/CH343 entry labelled `COMx` is the separate debug UART;
attach that bus ID as well only when console access is needed. In WSL, verify
the UUU device before running the probe or factory script:

```bash
/home/user/.local/bin/uuu -lsusb
```

The Product artifact must contain exactly one UUU script in
`deploy.image.files`. Its `src` is passed to the configured UUU command as
`{image}`. All files referenced by that script must also be present in the
artifact bundle (normally via `deploy.uuu.files`).
