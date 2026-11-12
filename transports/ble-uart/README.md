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


## Host SDK substitute

`host/NimBLEDevice.h` and `host/freertos/stream_buffer.h` substitute only the
NimBLE 2.3.6 / FreeRTOS APIs consumed by the unchanged `arduino/BleUart.h`.
Put `host/` before SDK headers in a host build. No Product protocol lives here.
The fake peer starts each link unencrypted, including bonded reconnects;
`startSecurity` must be called before authentication can complete. Authentication,
subscription, disconnect, MTU and notification failure are independently controllable.
Writes without authenticated encryption are rejected. A bounded stream buffer
feeds the real receive callback and real BleUart polling/notification queue.
This is a deterministic SDK test double, not the NimBLE stack or radio emulator.
It does not establish Windows cache behavior, RF timing, real RTOS scheduling,
cryptography or interoperability. Physical tests remain necessary.

`host/node-byte-port.cjs` adapts a host SDK provider's `connect`, `disconnect`,
`write` and `subscribe` callbacks to a serial-like byte endpoint. A Product can
pass it to the unchanged PC relay instead of its physical GATT byte adapter.
It does not generate application messages, acknowledgements or successful
authentication; those remain in the real relay and SDK-hosted control code.
Each provider has one owner; distinct providers are independent. Run
`node --test transports/ble-uart/host/node-byte-port.test.cjs` to verify the
binary contract, ownership release, closed writes and independent endpoints.
