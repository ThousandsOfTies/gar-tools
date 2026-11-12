# GC9A01 initialization and Linux output

`gc9a01_linux.hpp` exposes `gar::Gc9a01Linux(spiPath, chipPath, dcLine, hz,
resetLine)` and `frame(pixels, count)` for 240x240 RGB565 output. The caller
supplies wiring and pixels, not a physical/VM mode. It uses the same Linux
spidev/GPIO API on physical and CUSE/gpio-sim devices.

An optional reset line selects hardware reset; without a connected reset line,
the driver sends SWRESET and waits. Both paths then execute the identical full
`gar_gc9a01_initialize` sequence. There is no shortened simulation initializer.
Opened descriptors are released on initialization failure as well as shutdown.

`gc9a01_init.h` provides a transport-independent C/C++ initializer for a 240x240
GC9A01A in RGB565. Supply command and delay callbacks after performing a hardware
or software reset. Command errors stop the sequence. The callbacks retain SPI,
GPIO, module voltage, orientation and reset wiring ownership in the caller.

The controller register sequence is adapted from the BSD-licensed
[Adafruit driver at e742c29](https://github.com/adafruit/Adafruit_GC9A01A/blob/e742c29db8d4b84e1bbca16005aa7bfd59cf0b3c/Adafruit_GC9A01A.cpp).
Its attribution and redistribution notice are retained in the header. This
reference does not identify the manufacturer of an unbranded LCD module.

`make check HOSTCC=gcc HOSTCXX=g++` checks RGB565, required sleep/display delays,
identical initialization after either reset, frame encoding with short writes,
and failure cleanup. Tests intercept OS calls and do not access hardware.
The CUSE model still does not validate electrical timing or every controller
register; executing the real init sequence does not establish physical fidelity.
No face, animation, fixed Linux path or board pin is built into this driver.
