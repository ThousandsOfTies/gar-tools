# Luckfox Lyra Plus (RK3506)

Physical Target definition for the Luckfox Lyra Plus.

The verified board environment is:

- Rockchip RK3506
- `armv7l`
- Buildroot 2024.02
- BusyBox init
- SSH deployment over Ethernet

This Target is intentionally separate from `luckfox-rv1106`, which describes
the Luckfox Pico RV1106 family. Simulation uses the shared `linux-device`
runtime; physical deployment uses the board's real kernel interfaces.

The product build owns the self-contained armv7 application artifact. This
Target owns the constrained deploy helper and the BusyBox init launcher used
to start `/opt/gar/apps/<app>/run` at boot. Do not install systemd units,
simulation dummy devices, or application-specific configuration.

Run `gar target prepare --workspace <name>` once before the first deploy. The
recipe requires the default root SSH account and does not install or require
`sudo`. Each later
`gar target deploy` atomically replaces the application directory and restarts
its `/etc/init.d/S95<app>` process (`gar-` is added when the app name lacks it).

The manifest's `gar-app-lifecycle-v1` capability exposes the same
`status`, `log`, `health`, `reload APP --build-id BUILD_ID`, and
`running-build-id` contract used by the Raspberry Pi systemd recipe. The
Buildroot implementation delegates process state to the generated BusyBox init
script and reads logs from `/var/log/gar/<app>.log`; GAR invokes the helper
directly because the SSH account is root. An executable application-owned
`health` probe is optional and runs with the same root identity as the
application.

Persistent product configuration is `/etc/gar/<app>.env`. GAR system orchestration
may atomically install root-owned mode-0644 runtime values at
`/etc/gar/system/<app>.env`; the BusyBox launcher reads that file after the
persistent file, so runtime keys override persistent keys for that process.
The constrained installer owns both files and a normal artifact deploy changes neither.

`reload` records a running build ID only after restart and health succeed and
the requested ID matches schema-v2
`/opt/gar/apps/<app>/.artifact-info.json`. `running-build-id` returns that ID
only while the application remains healthy and the deployed marker still
matches. This detects the important case where new files were placed but an
old process is still running.

GAR deploy uses the installer's `register-app` action to stop the previous
process, run the constrained configuration hook, and generate the init script
without starting it. The following lifecycle `reload` exclusively owns start
and convergence. The legacy `enable-app` action remains as a compatible
register-and-start entry point.

An application may include an executable `configure-target` beside `run` when
its physical hardware needs a one-time board configuration. The constrained
installer runs it as root before creating the BusyBox init entry. Exit status
`10` means that configuration succeeded but a reboot is required; deploy then
finishes without starting the app, and BusyBox starts it on the next boot.
Other non-zero statuses fail deploy. This hook is for narrowly scoped board
configuration, not for installing simulation devices or replacing a rootfs.
The installer records this state under `/var/lib/gar-target/state`; lifecycle
`reload` then returns non-zero with an explicit `target reboot is required`
message instead of accidentally starting the application before that reboot.

Preparation also writes `/etc/gar/target-id` with `luckfox-rk3506`; compatibility
checks combine that logical ID with the measured architecture and libc before
any application payload is transferred.

## Hardware boundary

`hardware/capabilities.json` declares the board's available GPIO, SPI, and
network resources. The file is target-owned and is intentionally free of
application components or wiring. Product CSV assignments, requirements, and
physical bindings are kept outside this Target and supplied by the selected
Product workspace. This separation lets GAR reject incompatible assignments
before a deploy without turning a board definition into an application profile.
