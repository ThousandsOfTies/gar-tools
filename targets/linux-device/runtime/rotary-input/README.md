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
