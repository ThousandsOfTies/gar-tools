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
