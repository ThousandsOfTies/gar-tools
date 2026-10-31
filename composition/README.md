# Product composition

A Product pins three independent repositories: application, gar-tools and board.
Its `product.json` selects those inputs, an OS profile, hardware CSVs, application
build/launch declarations and the runtime version. No board model, SDK layout,
pin number or init-system rule is hard-coded in the Product hooks.

```sh
python3 tools/product.py describe
python3 tools/product.py validate
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

Validation: `python3 -m unittest discover -s tests -p test_product_composition.py -v`.
