# FRDM-IMX91S Target Pack

This Target Pack captures the reusable factory-provisioning path for the NXP
FRDM-IMX91S onboard 256 MiB SPI-NAND. It connects GAR's `uuu` backend to a
Product-owned artifact bundle and supplies the generators, safety gates, and
bring-up knowledge needed to create that bundle.

The implementation was validated with UUU 1.5.243, the NXP Linux 6.6
Scarthgap manufacturing image, and the public FRDM-IMX91S device tree. A new
board revision or BSP release must pass the read-only layout probe before NAND
writes are enabled.

## What this pack owns

```text
frdm-imx91s/
├── target.json
├── README.md
├── provisioning/uuu/
│   ├── factory-spinand.lst.in
│   ├── generate.sh
│   ├── update-dtb.lst.in
│   ├── generate-dtb-update.sh
│   ├── generate-layout-probe.sh
│   ├── stage.sh
│   └── imx91s-uuu.env.example
└── docs/
    ├── bsp-components.md
    ├── factory-flow.md
    ├── troubleshooting.md
    └── wsl2-usb.md
```

The Target Pack owns the board protocol, transfer workarounds, SPI-NAND
procedure, MTD/UBI safety checks, and host connection guidance. A Product owns
its boot-image filenames, root filesystem and overlay, confirmed layout
configuration, artifact manifest, and application.

## Artifact contract

The Product supplies this component tree. Boot-image filenames and the DTB are
selected in its copied `imx91s-uuu.env`.

```text
pub/
  u-boot/<RAM_BOOT_IMAGE>
  u-boot/<NAND_BOOT_IMAGE>
  kernel/Image
  kernel/<DTB>
  rootfs/rootfs.squashfs
  rootfs/usr.local.tar.bz2
  mfgtools/fsl-image-mfgtool-initramfs-imx_mfgtools.cpio.zst
```

The generators add zero-padded transfer copies under `pub/uuu-ram/`. The
staged bundle also contains one generated `.lst`, `checksums.sha256`, and
`bundle-info.txt`. GAR passes that `.lst` to `uuu` with the bundle directory as
the working directory.

## Safe first use

Copy the example configuration into the Product repository, set its artifact
filenames, and leave the write gate disabled:

```bash
cp targets/frdm-imx91s/provisioning/uuu/imx91s-uuu.env.example \
  /path/to/product/config/imx91s-uuu.env
```

Put the board in Serial Downloader mode, attach USB1, and generate the
read-only probe:

```bash
targets/frdm-imx91s/provisioning/uuu/generate-layout-probe.sh \
  --config /path/to/product/config/imx91s-uuu.env \
  --bundle-dir /path/to/components \
  --output /path/to/components/Inspect-imx91s-layout.lst \
  --validate

cd /path/to/components
uuu Inspect-imx91s-layout.lst
```

Confirm that the live MTD table is exactly:

| MTD | Name | Size |
|---|---|---:|
| 0 | `bootloader` | 8 MiB |
| 1 | `config` | 8 MiB |
| 2 | `kernel` | 36 MiB |
| 3 | `dtb` | 128 KiB |
| 4 | `rootfs` | 203.875 MiB (remaining NAND) |

Only then set `GAR_IMX91S_NAND_LAYOUT_CONFIRMED=1` and stage the factory
bundle:

```bash
targets/frdm-imx91s/provisioning/uuu/stage.sh \
  --input-dir /path/to/components \
  --output-dir /path/to/factory-bundle \
  --config /path/to/product/config/imx91s-uuu.env \
  --validate --force
```

Run the generated factory script from its bundle directory. A successful run
ends with `GAR_IMX91S_NAND_FLASH_COMPLETE`; it deliberately does not reboot,
because forced USB disconnects are otherwise reported by libusb as failures.

For a board-specific pinmux change, generate a guarded DTB-only updater. It
boots the same manufacturing environment but erases and writes only the
confirmed `dtb` partition; the bootloader, kernel, config, and rootfs remain
untouched:

```bash
targets/frdm-imx91s/provisioning/uuu/generate-dtb-update.sh \
  --config /path/to/product/config/imx91s-uuu.env \
  --bundle-dir /path/to/components \
  --output /path/to/components/Update-dtb-frdm-imx91s.lst \
  --validate
```

A successful run ends with `GAR_IMX91S_DTB_UPDATE_COMPLETE` and deliberately
leaves the board in manufacturing Linux. Power-cycle it in internal boot mode
after UUU exits successfully.

## Board connections

- Serial Downloader: `SW1[4-1] = 0001`, meaning
  `SW1-4=OFF`, `SW1-3=OFF`, `SW1-2=OFF`, `SW1-1=ON`.
- UUU data: USB1 (`J5`).
- Cortex-A debug console: USB-C debug UART (`J11`), 115200 8N1.
- The first CH342/CH343 serial channel is normally the Cortex-A console.

The UUU and debug UART connections are separate USB devices. See
[`docs/wsl2-usb.md`](docs/wsl2-usb.md) when GAR runs under WSL2.

## Further reading

- [`docs/factory-flow.md`](docs/factory-flow.md): protocol stages and safety design
- [`docs/bsp-components.md`](docs/bsp-components.md): required NXP build outputs
- [`docs/troubleshooting.md`](docs/troubleshooting.md): observed failures and fixes
- [`docs/wsl2-usb.md`](docs/wsl2-usb.md): Windows/WSL USB ownership and re-enumeration
