# Troubleshooting record

These are deterministic failures observed while establishing the factory
flow. Start with the serial console; a UUU stage timeout often reports only
that the expected next USB protocol never appeared.

| Symptom | Cause | Resolution |
|---|---|---|
| `Wait for Known USB Device Appear...` | Board is not attached to WSL, is in the wrong boot mode, or is already running another protocol | Check `usbipd list`, attach the NXP bus ID, set Serial Downloader mode, power-cycle, then run `uuu -lsusb` |
| SDPS upload fails near the SPL transition | NAND-specific image was used as the RAM/SDPS boot image | Use the normal manufacturing image for SDPS and reserve the SPI-NAND image for `fspinand` |
| `FB: download` times out | Short fixed bulk timeout through WSL2/usbipd | Use generated chunked `FB: write` transfers |
| A large transfer repeatedly fails at 97% or at the first bytes after a full chunk | Final non-aligned Fastboot chunk triggers a deterministic transport problem | Transfer the generator's zero-padded `pub/uuu-ram` copy and retain the original boot size separately |
| `too long command` on `FB: acmd booti ...` | Fastboot command-length limit | Store the command in a U-Boot environment variable, then run that variable |
| RAM Linux never reaches FBK | Kernel, DTB, or initramfs address/format is wrong | Watch serial, run `iminfo` on the legacy initramfs, and use the configured `0x85000000` initrd address |
| ELE/S400 fault while probing | The initramfs overlaps the ELE reserved DDR range | Do not use the U-Boot default initrd address for this image; use the Target Pack default unless the memory map is revalidated |
| Final `acmd reboot -f` reports `LIBUSB_ERROR_IO` | Reboot intentionally disconnects USB before UUU reads a reply | Do not auto-reboot; treat `GAR_IMX91S_NAND_FLASH_COMPLETE` as completion |
| Linux boots but logind/resolved/timesyncd fail with `Result: resources` | `/` inherited UID 1000 from a build archive; systemd-tmpfiles rejects unsafe path transitions | Extract the overlay with `tar -o`, normalize `/` to `root:root` mode `0755`, and verify before unmounting |
| `/var/volatile/tmp` and `/var/volatile/log` are absent | Consequence of the same systemd-tmpfiles ownership rejection | Fix `/` ownership once on the affected UBIFS, rerun tmpfiles, and restart failed services; future factory runs are protected |

## Expected serial checkpoints

During RAM boot, U-Boot should report `Boot from USB for mfgtools`, run
`bootcmd_mfg`, and enter Fastboot if no valid initramfs is initially present.
After the generated kernel/DTB/initramfs load, the manufacturing Linux should
enumerate as FBK. After NAND boot, `/proc/cmdline` should select
`ubi.mtd=4 root=ubi0:rootfs rootfstype=ubifs` for the validated layout.

## Post-flash checks

```sh
cat /proc/cmdline
cat /proc/mtd
ls -ld / /usr /usr/local /var/volatile/tmp /var/volatile/log
systemctl --failed
```

The validated image reports five MTD partitions, mounts its root from UBIFS,
owns `/` as UID/GID `0:0`, and has no failed systemd units after first-boot
initialization.
