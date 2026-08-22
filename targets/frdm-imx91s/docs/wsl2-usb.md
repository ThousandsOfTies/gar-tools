# WSL2 USB setup

WSL2 does not see a Windows-owned USB device automatically. USB pass-through
is not a filesystem mount; ownership is transferred with `usbipd-win`.

From an elevated Windows PowerShell:

```powershell
usbipd list
usbipd bind --busid <UUU_BUSID>
usbipd attach --wsl --busid <UUU_BUSID> --auto-attach
```

The initial ROM device is NXP `VID:PID 1fc9:0159` and appears to UUU as MX91
SDPS. After U-Boot starts, the board re-enumerates, normally as Fastboot
`1fc9:0152`. Auto-attach is important because these are two USB identities in
one factory run.

Verify from WSL with one hyphen:

```bash
uuu -lsusb
```

`uuu --lsusb` is not a valid option. If Windows shows the device as only
`Shared`, run `usbipd attach`; WSL cannot use a merely shared device. After a
power cycle or mode change, check `usbipd list` again because the bus ID or
attachment state may change.

The CH342/CH343 debug UART is separate from UUU. Attach its bus ID only when
the serial console is needed. On the observed adapter, the first interface was
the Cortex-A console at `/dev/ttyACM0` and the second was `/dev/ttyACM1`; use
enumeration rather than assuming those names on every host.

For the most reliable setup, keep both open during bring-up:

- USB1 (`J5`) attached to UUU through usbipd;
- debug USB-C (`J11`) attached as a serial device and monitored at 115200 8N1.
