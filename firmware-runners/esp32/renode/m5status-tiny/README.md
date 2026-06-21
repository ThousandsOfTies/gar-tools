# M5Status Tiny Renode Target

This is the smallest Renode-executable firmware smoke target for the
M5Stack/ESP32 path.

It intentionally does **not** claim to boot an ESP32 LX6, Arduino, M5Unified, or
the production Vibe Remote firmware yet. Current Renode has a verified
`xtensa-sample-controller` target, while the ESP32/M5Stack board model still has
to be grown. This target gives GAR a repeatable first firmware execution point:

- create a Renode machine,
- load an Xtensa ELF,
- start CPU execution,
- observe UART output from Robot Framework.

The ELF currently comes from Renode's upstream Xtensa Zephyr hello-world sample.
Once an ESP32 or local Xtensa toolchain is available, replace the ELF/load path
with a GAR-built tiny UART firmware that prints `GAR_RENODE_HELLO`.

## Run

```bash
cd ~/Yurufuwa/gar-tools
renode --console --disable-xwt --execute \
  "include @firmware-runners/esp32/renode/m5status-tiny/run.resc; start; quit"
```

## Test

```bash
cd ~/Yurufuwa/gar-tools
renode-test firmware-runners/esp32/renode/m5status-tiny/m5status-tiny.robot
```

