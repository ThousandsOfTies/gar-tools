# Luckfox RK3506 Hardware Template

Default simulation hardware contract for the Luckfox Lyra Plus RX product:
an ILI9341 SPI display and a KY-040 rotary encoder.

The line numbers are the stable simulator contract. A physical Lyra maps the
same roles to its board-specific GPIO offsets through `/etc/gar/gar-stream-rx.env`;
the application continues to use Linux `/dev/gpiochip*` and `/dev/spidev*`
interfaces in both environments.
