# Consolidated composition candidate

This working tree combines previously separate, versioned implementations:

- Python/explicitly planned Linux packaging and hardware overrides:
  `25535365108aa31e9c071829c2cd09038cf16b1c`.
- MCU composition, constrained ESP32 bundles and SDK byte-port transport:
  `68930ee9da2492fb5d0b18031e4360414e465e4e`.
- Optional I2C, native build options, systemd groups/runtime directories,
  audio and Live transport:
  `550d7069aeea448e67dee47b6dd5a3adee3e2088`.
- Native GC9A01 driver and its mock-system-call tests also incorporate the
  existing uncommitted driver work in the Orange Pi Product's tools checkout.
  The source checkout remains unchanged.

The existing canonical checkout's reusable part UI is retained. Audio/Live and
BLE additions are protocol/driver boundaries; no Product motion, conversation
instructions or device credentials are moved into this library.

The nine-Product offline matrix passed using this tools candidate and the
existing Orange Pi I2C board extension. This proves contract compatibility,
not target firmware or physical-board behavior. Product submodule pins have
not yet been changed or published by this consolidation.

`capabilities.json` advertises additive engine commands. GAR checks this marker
before routing MCU/custom artifact commands, so old pinned engines retain their
existing build route. `artifact --kind target_app` builds/exports MCU firmware;
it never runs a flasher. Native specialized backends explicitly declare their
compatibility adapter in `build.target_hook`, `simulation_hook`, `runtime_hook`.

Python Linux simulators can declare `simulation.packaging` with `panel`, `after`,
`wants`, optional `/etc/gar/*.env` files and `wait_for_hardware_socket`. Then
`artifact --kind sim_app` packages unchanged App sources, resolves the simulation
hardware environment and renders the existing GAR systemd/panel artifact layout.
System topology overrides remain after static defaults. This packaging does not
start an App, connect a device, install services or substitute App protocol code.

All physical evaluation is skipped for the current improvement task at the
owner's request. Preserve this distinction in subsequent validation reports.

Native Linux simulation builds can declare `simulation.native_artifact`:
an explicit `architecture`, authored `sources`, argument-array `commands`, ELF
`outputs` and an `entrypoint`. Commands run only in a fresh source staging tree
inside the selected Linux builder. `{root}` and `{build}` expand to that tree;
no command is evaluated by a shell. Existing App build scripts can be invoked
explicitly with `sh` as in ordinary GAR build hooks. Firmware/native-target
outputs never substitute for simulation outputs.

The packager verifies each ELF architecture, hashes the complete archive input,
and emits `files/vm.tar.gz` with `simulator-manifest.json`, preserving the existing
Product runtime adapter's deployment contract. It does not boot a VM or transfer
source there to compile. App source, native peripheral controller, virtual I2C
and SPI drivers remain unchanged. Product-specific commands and service files
stay in the Product manifest/archive. Runtime deploy/start/diag remain separate.
