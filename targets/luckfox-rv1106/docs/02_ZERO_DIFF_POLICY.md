# Zero-Diff Policy (Real Device and EC2 Sim)

This target aims for zero source modifications between real Luckfox hardware
and EC2 simulation.

## Non-negotiable rules

1. Same application source for real and simulation.
2. Same binary artifact whenever architecture/toolchain is the same.
3. Same hardware-facing file paths in code:
   - `/dev/video0`
   - `/dev/fb0`
   - `/dev/i2c-3`
   - `/dev/spidev0.0`
   - `/dev/gpiochip0`
4. No simulation-specific `#ifdef` in core app logic.
5. Simulation adaptation must happen below app layer using system-level device substitution (`/dev` providers, kernel modules, CUSE, gpio-sim).
6. HAL replacement in application layer is not the GAR primary path.

## Allowed differences

- Kernel/runtime provider implementation under `/dev`.
- Presence or absence of vendor shared libraries (detected at runtime).
- Performance and image quality characteristics.

## Forbidden patterns

- Forked app code for sim vs real.
- Different device path constants for sim builds.
- Mandatory `LD_PRELOAD` in standard simulation path.
- HAL-level adapter branches that only exist for simulation.

## Validation checklist

1. App starts on real target without code changes.
2. App starts on EC2 after devfs runtime startup, without code changes.
3. Device path checks report identical expected path set.
4. Functional scenario behavior is equivalent at app state level.

## Operational note

When a new peripheral is introduced, update `/dev` substitution runtime first,
not application source. App changes are allowed only if both real and sim need
the same change.

In GAR, the primary simulation approach is AI-driven system substitution at the
device interface boundary, especially CUSE where applicable.
