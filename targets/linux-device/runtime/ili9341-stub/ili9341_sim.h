#pragma once
#include <stddef.h>
#include <stdint.h>

/*
 * ILI9341 command/pixel-stream simulation for the CUSE SPI stub.
 *
 * gar-stream-rx's ili9341.py drives the panel write-only over /dev/spidevX.Y,
 * using a separate DC (data/command) GPIO line to say whether the current
 * SPI bytes are a command or pixel data - that split isn't visible in the
 * SPI ioctl itself. This module asks the web bridge (GAR_HW_SIM_SOCK or
 * GAR_RUNTIME_DIR/hw_sim.sock) for the DC line's current value before each
 * transfer, tracks CASET/PASET/RAMWR/MADCTL state the same way the real
 * panel would, and forwards the resulting RGB565 framebuffer to the bridge
 * so the Virtual Hardware Panel can render it on a canvas.
 */

void ili9341_sim_init(void);

/* Which gpio-sim line number the bridge should report as the DC pin. */
void ili9341_sim_set_dc_line(int line);

/*
 * Process one SPI transfer of `len` bytes (write-only; `rx`, if non-NULL,
 * is zero-filled since ili9341.py never reads from the panel).
 */
void ili9341_sim_transfer(const uint8_t *tx, uint8_t *rx, size_t len);
