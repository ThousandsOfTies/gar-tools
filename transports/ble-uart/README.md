# BLE UART byte adapters

Reusable single-peer GATT transport, independent of boards and application JSON.

- `arduino/BleUart.h`: NimBLE-Arduino 2.3.6, bounded RX/TX buffers, numeric
  comparison consent callback, authenticated encrypted bonding, MTU chunks,
  disconnect epoch reset. Call `poll()` and `send()` on the application task.
- `pc/gatt_pipe.py`: Bleak 2.1.1, Windows/Linux stdio pipe. Explicit device
  address and service/RX/TX UUIDs are supplied by its caller. No default UUID or
  application token is embedded. `--scan` lists only matching services.

The pipe emits open/data/written/error events as JSON Lines; byte data is base64.
Input accepts write commands with opaque id/data and close. Only one write runs
at a time. A written event reports GATT Write Request completion, not acceptance
by a remote application. A disconnected transfer is never replayed.

NimBLE callbacks only buffer data and facts; the main task handles consent and
application bytes. RX requires encryption and authentication. TX is sent only
after a secure authenticated bond and a notification subscription.

These adapters require physical peer testing on each supported board/OS.
