# cuse_gpio

Experimental CUSE GPIO chip stub for Gapless Agent Runtime.

This stub can expose `/dev/gpiochip0`, answer chip/line metadata ioctls, and
route simple output/input value operations to `web-bridge/bridge.py`.

Important limitation:

Linux GPIO chardev v1 and v2 line request ioctls return a new line-request file
descriptor to the caller. A userspace CUSE daemon cannot install a fresh file
descriptor into another process. Because of that, this stub cannot be a fully
transparent replacement for `gpio_shim.so` for existing applications that call
`GPIO_GET_LINEHANDLE_IOCTL` or `GPIO_V2_GET_LINE_IOCTL` and then operate on the
returned fd.

Use this as an ABI/bridge spike. A production replacement needs one of:

- a small application-side GPIO abstraction that keeps using the chip fd in sim,
- a kernel-backed fake GPIO provider such as `gpio-mockup`,
- a dedicated kernel module, or
- keeping an `LD_PRELOAD`/seccomp-style fd mediation layer for the fd-returning
  request ioctl only.

For the supported GPIO simulation path, let GAR inspect and start `gpio-sim`:

```bash
gar sim gpio check --json
gar sim gpio plan --json
gar sim runtime start
gar sim runtime diag --json
```

Run this CUSE spike directly only when investigating its ABI behavior:

```bash
make -C targets/linux-device/runtime/gpio-stub
sudo targets/linux-device/runtime/gpio-stub/cuse_gpio -f --devname=gpiochip0
sudo chmod 666 /dev/gpiochip0
```

## What the spike proves

The spike can create a CUSE node and answer `GPIO_GET_CHIPINFO_IOCTL` with:

```text
name= gpiochip0_sim
label= gar CUSE GPIO
lines= 54
```

It does not solve the line-request fd handoff described above and is not the
runtime acceptance target. Use `gar sim runtime diag --json` to verify the
selected runtime, generated GPIO lines, bridge, and application-facing device
nodes together.
