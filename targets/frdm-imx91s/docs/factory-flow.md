# SPI-NAND factory flow

## Protocol sequence

```text
i.MX 91 ROM (SDPS, USB VID:PID 1fc9:0159)
  -> RAM boot the normal manufacturing U-Boot
U-Boot Fastboot (FB, normally VID:PID 1fc9:0152)
  -> install the NAND-specific boot image with fspinand
  -> load Image, DTB, and manufacturing initramfs into DDR
Manufacturing Linux (FBK)
  -> verify live MTD names, sizes, and required commands
  -> write raw kernel and DTB partitions
  -> format rootfs MTD as UBI and create the rootfs UBIFS volume
  -> expand the base SquashFS and Product overlay
  -> normalize and verify root filesystem ownership
```

The ROM-booted image and the persistent NAND image are separate inputs. The
normal manufacturing image is used for `SDPS: boot`; the NAND image is only
the payload for U-Boot's `fspinand` command. Booting the NAND-specific image
directly through SDPS was observed to disconnect during its SPL transition.

## DDR transfer rules

UUU's simple `FB: download` path and final short Fastboot chunks were
deterministically unreliable through WSL2/usbipd. The generator therefore:

1. creates transfer-only copies padded to a 1 MiB boundary;
2. transfers them with chunked `FB: write` commands;
3. copies every chunk from `fastboot_buffer` to its final DDR offset; and
4. passes the original, unpadded initramfs size to U-Boot.

The default Fastboot staging buffer is `0x82800000`. The manufacturing initrd
is placed at `0x85000000`; the U-Boot default near `0x83800000` caused the
17 MiB initramfs to overlap the FRDM-IMX91S ELE reserved region around
`0x84120000`.

## NAND safety barriers

Persistent writes require all of the following:

- the Product configuration explicitly sets the confirmation gate to `1`;
- live MTD names and byte sizes match the fixed device-tree layout;
- `flash_erase`, `nandwrite`, `ubiformat`, `ubiattach`, `ubidetach`,
  `ubimkvol`, and `stat` exist in the manufacturing image;
- kernel, DTB, and NAND boot image fit their partitions; and
- the expanded filesystem root is `root:root` with mode `0755`.

The Product overlay is extracted with `tar -o` so archive ownership from a
container or host build user is ignored. The UBIFS root is normalized after
all extraction. Without this, systemd-tmpfiles rejects transitions from a
UID-1000-owned `/`, volatile directories are not created, and services using
`PrivateTmp` fail with `Result: resources` and `Not a directory`.

## Completion behavior

The factory list finishes with the marker
`GAR_IMX91S_NAND_FLASH_COMPLETE` and leaves the manufacturing Linux running.
Power the board off, change the boot switch as required, and boot from NAND.
An automatic `reboot -f` is intentionally avoided because the expected USB
disconnect can make an otherwise successful UUU run end in
`LIBUSB_ERROR_IO`.
