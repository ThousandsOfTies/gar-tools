# Product composition

A Product pins three independent repositories: application, gar-tools and board.
Its `product.json` selects those inputs, an OS profile, hardware CSVs, application
build/launch declarations and the runtime version. No board model, SDK layout,
pin number or init-system rule is hard-coded in the Product hooks.

```sh
python3 tools/product.py describe
python3 tools/product.py validate
python3 tools/product.py hardware --environment simulation
GAR_BOARD_SDK=/external/sdk python3 tools/product.py build
python3 tools/product.py package --output artifacts/a-new-release
```

`describe` and `validate` are offline. `build` calls the selected application's
build hook using the board's compiler profile. `package` verifies target ELF/ABI,
copies the selected inputs and renders launch, board preparation and OS startup
files. Native verification builds cannot be packaged as physical target builds.
Output paths are immutable; choose a fresh path for another release.

The existing BusyBox PID-identity manager and systemd unit template are reused.
The board selects the init system and boot order; the Product selects the entry
point, runtime, service identity and hardware binding. GPIO/SPI readiness is
bounded by the board profile. Applications keep their own input decoding and
rendering. This library does not add simulation branches to an application.

SDK/ROM/compiler bytes are external. Machine-local USB identity and SDK location
belong to `.gar/device.json`; they are excluded from composition reports and
packages. Only an explicit `composition/device.py` action accesses ADB. That
adapter supports the existing BusyBox path; it is not a claim of universal GAR
transport or lifecycle integration. Core GAR's existing Target Packs remain
compatible; this additive composition path does not rewrite their definitions.

Board profiles contain a versioned resource inventory and preparation-provider
parameters. Product CSVs contain actual peripheral assignments and debounce
values. The board repository must not contain application names or wiring uses.

Products can keep one physical GPIO/SPI binding and declare a small override CSV
with `table,name,field,value` columns. Set `hardware.simulation_overrides` to that
file and `hardware.simulation` to a generated path under `.gar/`, `build/` or
`artifacts/`. The `hardware` command derives the simulation CSVs without modifying
the canonical files. A name glob can apply a common policy to several rows.
The application and simulated device provider must read that same generated
directory. Generated files are not authored or committed. Existing Products
without overrides continue using their separately selected simulation directory.

Validation: `python3 -m unittest discover -s tests -p test_product_composition.py -v`.

## Embedded firmware profiles

A board profile with `kind: platformio` declares its pinned PlatformIO version,
platform/board/framework, driver dependencies, flash capacity, resources and I/O
adapter paths. The Product selects resource names in a binding JSON and declares
its application sources, includes, identity/options and firmware entry point.
It contains no duplicated board pin numbers or driver implementation.

`prepare` generates the `[board]` INI section, board constants, application
constants and selected source includes under `.gar/composition/`. Headers are
scoped by build-host platform so Windows firmware and Linux/WASM builds do not
overwrite each other's absolute paths. Generated constants also work from C
LVGL configuration headers. The fixed path-free `board.ini` is included by the
Product's PlatformIO file. The Product adds its own app libraries and uses the
generated source include list in exactly one translation unit.

`build` prepares those files and compiles using an isolated PlatformIO runtime.
It never opens a serial port. Firmware startup is Arduino `setup`/`loop`; it does
not generate BusyBox/systemd files. Firmware and simulator artifact packaging
continue using the Product's existing GAR build hooks; the Linux `package`
command intentionally rejects MCU profiles. Core Target Pack transport and
deployment contracts are unchanged.

Validate with `python3 -m unittest discover -s tests -p test_embedded_composition.py -v`.

## Interpreted Linux applications and planned ports

`build.backend: python` selects application/tool payload files and checks Python
syntax without importing device libraries. `launch.runtime` selects an interpreter
from the board profile. The Product owns launch defaults and an explicit mapping
from GPIO/SPI/I2C CSV fields to its application's environment variable names.
The library contains no board, application, GPIO number or camera-mode defaults.

The `environment --environment physical|simulation` command resolves those values;
`--format systemd` renders environment assignments for an existing Product service.
Simulation values come from the same canonical CSV plus declared overrides.
Generated launchers preserve values supplied at runtime, including existing GAR
persistent/system environment files. Payloads contain only selected sources.

For `deployment.manager: gar-target`, packages retain the constrained GAR layout:
one app directory under the board's application root, a generated `run`, and
composition provenance. Root-owned preparation, service installation and lifecycle
stay with GAR; no second startup manager is added. The legacy Target discovery and
transport contracts are not moved by this library.

`package --output artifacts/a-new-release` is immutable by default. Existing build
hooks may explicitly select `--replace` for their generated staging directory.
`clean --output artifacts/from-codespace` can remove only a generated child of the
Product's artifacts directory; linked paths are rejected before a move or cleanup.

`build.backend: planned` requires `status: planned` and an explanation. Such a
Product can describe and validate its selected resources, including I2C, while
build/package still fail. Adding a board component never qualifies an unfinished
physical port or creates an artificial successful artifact.

Validation: `python3 -m unittest discover -s tests -p test_python_composition.py -v`.

## CSV-owned hardware contracts

`hardware.contract` opts a Product into deriving GAR's requirement and binding
JSON from authored CSVs. Parts stay in `components.csv`, physical wiring in
`connections.csv`, and Linux I/O assignment in the physical runtime CSVs.
An `interfaces.csv` supplies only interface identity, component/terminal names,
runtime row selection, driver/electrical constraints and optional resource IDs.
Do not repeat header pins or Linux GPIO line numbers in that intent table.

```json
{"hardware":{"contract":{
  "product":"example-app","board_component":"board",
  "components":"hardware/components.csv","connections":"hardware/connections.csv",
  "interfaces":"hardware/interfaces.csv"
}}}
```

The intent columns are `id,kind,component_id,runtime_name,component_pins,required_drivers`.
Electrical GPIO/SPI interfaces also require `voltage_v`. `resource`, `min_speed_hz`
and `min_fps` are optional constraints. Driver and terminal lists use semicolons.
For SPI, terminals explicitly name signals, for example
`SDI:MOSI;SCK:SCLK;CS:CS0`; GPIO uses a single terminal such as `CLK`.
Unspecified resources must resolve uniquely from kind/device; ambiguity fails.

```sh
python tools/product.py hardware-contract --capabilities /path/to/capabilities.json
```

Generated files live only under `.gar/hardware-contract/`. Source CSVs and authored
JSON are never overwritten. The core `gar hw validate` derives both JSON inputs
when this opt-in is present, then runs the existing offline capability validator.
Explicit `--requirements` or `--binding` overrides retain their existing meaning.
A derivation error never falls back to stale generated or authored JSON.
Write-only SPI may omit MISO through the Product's existing `spi_miso: false`;
clock, chip select and data wiring remain checked. I2C uses `frequency_hz` in the
intent CSV, a 7-bit address from its runtime CSV, and `SDA:SDA;SCL:SCL` wiring.
Core validation allows shared controller pins at distinct addresses, while
rejecting address collisions, voltage/speed mismatches and foreign pin claims.

MCU Products can declare `hardware.binding_csv` with `components`, `connections`
and `board_component` instead of authoring a parallel binding JSON. Each internal
selection connects `source=board_component`, `source_pin=<board resource name>`
to its component ID, with `signal=display|button`. These are built-in resource
names, not an external wiring claim or a second copy of board pin numbers.
The board owns native display orientation. Validation is read-only; `prepare`
derives `.gar/composition/binding.json` for existing build/hash consumers.
`gar hw validate` delegates to the pinned MCU validator and explicitly reports
its scope as offline built-in resource selection, without electrical verification.
