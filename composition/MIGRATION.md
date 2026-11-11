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
