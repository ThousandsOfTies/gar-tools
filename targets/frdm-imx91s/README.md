# FRDM-IMX91S UUU Target

This Target Pack uses a full Linux image as the deploy artifact. The default
command is equivalent to:

```bash
uuu -b sd_all <image.wic.zst>
```

For eMMC or NAND, change `provisioning.uuu.command` in `target.json` to the
UUU mode and arguments required by the Product image. The command is an argv
array; GAR never evaluates it through a shell.

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

The Product artifact must contain exactly one image in `deploy.image.files`.
The `src` is passed to the configured UUU command as `{image}`.
