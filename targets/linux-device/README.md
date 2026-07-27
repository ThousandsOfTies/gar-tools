# Linux Device Target Tools

Tools that make a Linux host behave like the device surface expected by GAR
applications.

This target is not EC2-specific. EC2 Graviton is one simulation host that can
run this runtime; the runtime itself is about Linux `/dev` compatibility:

- `runtime/gpio-stub/`: legacy CUSE GPIO spike and notes
- `runtime/i2c-stub/`: CUSE I2C device with SSD1306 and VL53L0X simulation
- `runtime/spi-stub/`: CUSE SPI device with MFRC-522 simulation
- `runtime/ili9341-stub/`: CUSE SPI device with ILI9341 320x240 panel
  simulation (gar-stream-rx video monitor); KY-040 rotary encoder support
  lives in `web-bridge` only (gpio-sim direct, no CUSE binary needed)
- `runtime/web-bridge/`: HTTP bridge and panel for observing and driving state
- `runtime/test/`: small Linux test applications
- `hardware/`: default CSV hardware definition copied by `gar hw init`
- `Dockerfile`: local container image used by the `local_docker` simulator

GAR orchestration and EC2 provisioning live in `GaplessAgentRuntime`.

## Local container

```bash
gar sim host start --workspace <name>
```

`target.json` declares the image, its build context, and the devices and mounts
the container needs (`/dev/cuse`, `/sys/kernel/config`, ...), so `gar` builds the
image on first start and holds no linux-device specific knowledge itself. Build
it manually with `docker build -t gar-linux-device:latest targets/linux-device`
when you want to iterate on the `Dockerfile`.

The container shares the host kernel. `gpio-sim` therefore requires a host
kernel of Linux 5.17 or newer with `CONFIG_GPIO_SIM`; WSL2 and Ubuntu 24.04 or
newer satisfy this. CUSE-backed I2C/SPI only needs `/dev/cuse`. Verify with:

```bash
gar sim gpio check --json
```

### Build architecture

`gar sim runtime build` exports `CC` and `GAR_SIM_ARCH` according to the selected
simulator, so the runtime binaries match the simulation host:

| simulator | `GAR_SIM_ARCH` | `CC` |
|---|---|---|
| `local_docker` | host architecture | `gcc` |
| `ssh_remote` | `aarch64` (override with `ec2.arch`) | `aarch64-linux-gnu-gcc` |

The Makefiles only override `CC` when make supplies its built-in default, so an
exported `CC` always wins.
