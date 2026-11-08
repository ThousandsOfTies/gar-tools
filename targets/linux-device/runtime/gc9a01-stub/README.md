# GC9A01 CUSE SPI display model

Creates a real Linux character device, e.g. `/dev/spidev0.0`, supporting the
spidev write/ioctl interface. Applications send command/data phases with a real
GPIO line supplied by `gpio-sim`; the shared bridge reads the output level.
Only completed RGB565 address windows are published as `gc9a01` frames.

This uses the existing SPI ioctl plumbing and parameterized DCS pixel model in
`../ili9341-stub`. Its default ILI9341 dimensions/event remain unchanged.
GC9A01 selects 240×240 and a maximum publication rate of 20 Hz. The model tracks
CASET, PASET, RAMWR and the MADCTL axis bit; it does not model electrical timing,
power/gamma initialization, mirror orientation, inversion or BGR conversion.
The circular aperture belongs to the visible display component.

```
make -C targets/linux-device/runtime/gc9a01-stub CC=gcc
sudo env GAR_HW_SIM_SOCK=/run/gar/hw_sim.sock targets/linux-device/runtime/gc9a01-stub/cuse_spi_gc9a01 -f --devname=spidev0.0 --dc-line=16
```

Select `gc9a01` in the Product `hardware/spi.csv` sim column, and configure
`lcd_dc` in `gpio.csv`. Do not start another provider for the same device node.
The application must not publish framebuffer events directly to the bridge.
