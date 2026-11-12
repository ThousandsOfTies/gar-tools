# Native snapshot execution

GAR builds `simulation.native_artifact` in a Linux BuildEnvironment and captures
the resulting immutable SIM_APP. `simulation.snapshot` declares a hardware CSV
directory, a bridge process when required, ordered services, their environment,
and a health endpoint/service. No Product names or pin numbers are built into the
host implementation. Keep Product commands and service wiring in product.json.

GAR's SSH channels transfer the archive, verify its checksum and complete file
inventory, and atomically install it under /var/lib/gar/snapshots/Product-id.
Only prepared Vagrant/VirtualBox hosts are qualified. A host ownership marker
rejects a different Product; allocate a separate machine per Product. Existing
hand-created VMs are not touched. The host never compiles application sources.

The devices service reads the same GPIO/SPI/I2C CSVs as the App. gpio-sim retains
the selected chip paths and line numbers; CUSE supplies the selected SPI/I2C
nodes. Occupied SPI/I2C paths are rejected. Optional bridge and native drivers
run in the service's process group and are stopped together.

`linkage: static` creates temporary compiler wrappers in the builder so newer
builder libc/libstdc++ versions are not required in the runtime guest. Compiler
wrappers are not archived. The host helper itself is included in the archive's
checksums. Private inputs are transferred separately into .gar/private, with
0700 directory and 0600 files, and never enter an artifact.

Diagnosis checks the captured file hashes, every service PID's GAR_BUILD_ID,
the health response's build ID and PID, and optional App build ID. A healthy HTTP
server alone is insufficient. Device behavior must still be exercised through
the retained App and drivers; health/identity checks do not prove electrical,
physical, audio or external network integration.
