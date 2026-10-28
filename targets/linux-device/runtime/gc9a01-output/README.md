# GC9A01 physical initialization

`gc9a01_init.h` provides a transport-independent C/C++ initializer for a 240x240
GC9A01A in RGB565. Supply command and delay callbacks after performing a hardware
or software reset. Command errors stop the sequence. The callbacks retain SPI,
GPIO, module voltage, orientation and reset wiring ownership in the caller.

The controller register sequence is adapted from the BSD-licensed
[Adafruit driver at e742c29](https://github.com/adafruit/Adafruit_GC9A01A/blob/e742c29db8d4b84e1bbca16005aa7bfd59cf0b3c/Adafruit_GC9A01A.cpp).
Its attribution and redistribution notice are retained in the header. This
reference does not identify the manufacturer of an unbranded LCD module.

`make check HOSTCC=gcc` checks RGB565, required sleep/display delays and transport
failure handling. No face, animation, Linux path or board pin is built into it.
