# Common hardware CSV runtime

`sh hardware-run.sh /path/to/hardware command args...` reads `gpio.csv`,
`spi.csv` and `environment.csv` immediately before starting the unchanged App.
The same CSV bytes are packaged for physical and simulated Linux execution.
There are no generated environment-specific hardware tables or JSON caches.

`environment.csv` contains `variable,table,name,field` references, not copied
GPIO numbers or SPI speeds. The reader validates every reference before the
App starts and preserves explicitly supplied process environment overrides.
It needs only POSIX sh/awk, including on BusyBox targets; no Python is required.
CSV supports CRLF, quoted commas and doubled quotes. Multiline records are
rejected explicitly. Values are shell-quoted, never executed as commands.

The simulator provider creates virtual devices with the paths/lines selected
by the common data. Necessary provider settings (for example, disabling kernel
debounce for gpio-sim) belong to the starting process, not another CSV copy.
This validates software configuration, not physical electrical behavior.

`virtual_gpio.py` reads the same GPIO CSV, sizes gpio-sim banks from its line
offsets and exposes their character devices at the canonical chip paths. If
the kernel allocated another name, only a symlink to that managed virtual chip
is created. Occupied device paths are rejected; cleanup removes only aliases
to that instance and deactivates its gpio-sim banks. No alternate GPIO CSV is
generated. Stop the simulator before changing its chip layout.

`virtual_device.py` / `virtual-device.cjs` check a canonical I2C character device
through `/sys/dev/char` and require CUSE before a simulated motion command can
run. Physical controllers do not pass the gate, regardless of their bus number.
The simulator starts CUSE using the bus name already present in the common CSV.

The native rotary reader accepts the process setting `GAR_GPIO_DEBOUNCE_US`.
An explicit zero can disable kernel debounce for gpio-sim while preserving the
physical debounce value in the CSV. Default physical behavior remains unchanged.
Native I2C policy adapters can derive their legacy JSON with
`composition/i2c_binding.py`; authored parts, connections, interface intent and
runtime CSVs remain the inputs. Board-specific qualification remains a separate
validation step.
