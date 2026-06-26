# GAR Wokwi M5StackC Simulation

This project is generated from `gar-tools/targets/esp32/wokwi/m5stackc` by
`gar setup` or `gar sim env start` when the Wokwi simulation backend is
selected.

Build:

```bash
pio run
```

Run with Wokwi CLI:

```bash
export WOKWI_CLI_TOKEN=...
wokwi-cli .
```

Run the button smoke scenario:

```bash
wokwi-cli . --scenario button.test.yaml --timeout 60000 --timeout-exit-code 1
```

Override paths with `GAR_WOKWI_PROJECT_DIR`, `GAR_WOKWI_TEMPLATE_DIR`,
`GAR_WOKWI_FIRMWARE`, `GAR_WOKWI_ELF`, and `GAR_WOKWI_TIMEOUT_MS`.
