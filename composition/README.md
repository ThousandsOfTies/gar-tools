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

On Windows, default embedded build caches use a short per-Product/platform path
under `%USERPROFILE%/.cache/gar/` to keep GCC expanded commands below the process
command-line limit. The isolated Python runtime stays inside the Product.
`GAR_BUILD_CACHE` still overrides the location; choose a short absolute path.
