# GPIO rotary input

Reads three line offsets from a Linux GPIO v2 character device. The same reader
works with kernel gpio-sim and physical GPIO controllers with the v2 API.
It emits line-delimited JSON on stdout: `ready`, `rotate` with `direction` (-1/1)
and `counter`, and `press`. Application-specific actions stay in the Product.

```sh
make -C targets/linux-device/runtime/rotary-input CC=gcc
targets/linux-device/runtime/rotary-input/gar_rotary_input \
  --chip /dev/gpiochip0 --clock 20 --data 21 --switch 22
```

The example offsets are virtual line offsets, not physical board pins. Configure
the Product's actual controller and lines before using real hardware. Clock/data
idle high and the switch is active low; provide suitable pull-ups. One detent
uses four quadrature transitions; partial/bouncing or diagonal transitions do
not produce a detent. Switch presses have a 60 ms repeat suppression interval.
Dropped kernel events discard the partial detent. Run `make check HOSTCC=gcc`
for the platform-independent decoder tests.

Use `--bias pull-up` to request the controller's internal pull-ups on all three
lines. `pull-down`, `disabled`, and `as-is` are also accepted; the default is
`as-is` for compatibility. Unsupported bias requests fail instead of silently
leaving physical inputs floating. The GPIO request owns the bias for its lifetime.

Use `--debounce-us MICROSECONDS` to request Linux GPIO v2 debounce on all three
inputs when acquiring the lines. The range is 0..1000000; the default 0 leaves
the original input request unchanged. The Product chooses the period; it is not
a board-specific reader default. Hardware support or kernel software fallback
determines the implementation. Software timing also depends on kernel timer
granularity and scheduling, and raw IRQs may still occur. Long periods may hide
legitimate quadrature transitions, so validate the chosen period on the device.

Event-loss detection retains the original request-wide `seqno` check. Configure
input filtering before interpreting mechanical contact edges rather than
changing the sequence-number policy for one controller. `make check HOSTCC=gcc`
also validates the GPIO debounce request and its disabled default.
