# Linux Device Target Tools

Tools that make a Linux host behave like the device surface expected by GAR
applications.

This target is not EC2-specific. EC2 Graviton is one simulation host that can
run this runtime; the runtime itself is about Linux `/dev` compatibility:

- `runtime/gpio-stub/`: legacy CUSE GPIO spike and notes
- `runtime/i2c-stub/`: CUSE I2C device with SSD1306 and VL53L0X simulation
- `runtime/spi-stub/`: CUSE SPI device with MFRC-522 simulation
- `runtime/web-bridge/`: HTTP bridge and panel for observing and driving state
- `runtime/test/`: small Linux test applications

GAR orchestration and EC2 provisioning live in `GaplessAgentRuntime`.
