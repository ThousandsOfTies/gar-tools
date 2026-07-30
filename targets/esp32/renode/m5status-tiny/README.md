# M5Status Tiny Renode Target

This is the smallest Renode-executable firmware smoke target for the
M5Stack/ESP32 path.

It intentionally does **not** claim to boot an ESP32 LX6, Arduino, M5Unified, or
the production firmware. Renode has a verified `xtensa-sample-controller`
target, while the ESP32/M5Stack board model still has to be built. This target
provides a repeatable first firmware execution point:

- create a Renode machine,
- load a checksum-verified Xtensa ELF,
- start CPU execution,
- observe UART output from Robot Framework.

The sample currently uses Renode's upstream Xtensa Zephyr hello-world ELF. Once
an ESP32 or local Xtensa toolchain is available, replace it with a GAR-built tiny
UART firmware that prints `GAR_RENODE_HELLO`.

## Pinned inputs

The runner requires Renode `1.16.1`. The official portable .NET archives and
release checksums are:

```text
# Linux x86_64
https://github.com/renode/renode/releases/download/v1.16.1/renode-1.16.1.linux-portable-dotnet.tar.gz
sha256: 00e113cdbd0f5354cf2f64bbe3f5a070d8958409542fca66e45ac97d982938c0

# Linux arm64
https://github.com/renode/renode/releases/download/v1.16.1/renode-1.16.1.linux-arm64-portable-dotnet.tar.gz
sha256: fff3a098c96ed0a4ffbdff3f028c9c5fde432db09587c7bd7c99406180f90007
```

`run.py` downloads the firmware to a temporary directory and checks this digest
before invoking Renode:

```text
https://dl.antmicro.com/projects/renode/xtensa-sample-controller-zephyr-hello-world.elf-s_293544-4be60f8a3891e70c30e1e8a471df4ad12ab08144
sha256: 6b4e9193b68fd6459de648560094d1d1a96f82a654f8a1f90629e5fb3a843079
```

No downloaded ELF is stored in the repository.

## Run

From the `gar-tools` repository root:

```bash
python3 targets/esp32/renode/m5status-tiny/run.py
```

## Test

```bash
python3 targets/esp32/renode/m5status-tiny/run.py --test
```

The runner prefers the `renode-test` launcher beside the version-checked
`renode` command. This keeps the Robot dependencies installed by `gar setup`
paired with the same Renode installation.

For an offline run, provide a previously downloaded file. The same SHA-256
check is still required:

```bash
python3 targets/esp32/renode/m5status-tiny/run.py --elf path/to/sample.elf
```
