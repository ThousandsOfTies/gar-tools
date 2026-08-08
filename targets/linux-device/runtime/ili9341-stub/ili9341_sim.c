/*
 * ili9341_sim.c — ILI9341 320x240 panel simulation for the CUSE SPI stub.
 *
 * Ported from the same design as ssd1306_sim.c (i2c-stub), adapted for a
 * write-only SPI panel whose command/data framing depends on an external DC
 * GPIO line rather than an in-band control byte.
 *
 * Command/data phase:
 *   DC = 0 (low)  -> the transfer's bytes are a command (usually 1 byte)
 *   DC = 1 (high) -> the transfer's bytes are data for the last command
 *
 * We only need to understand enough of the ILI9341 command set to track the
 * addressing window and stream pixels into a framebuffer for the panel:
 *   0x2A CASET   - column address set (x0,x1, 16-bit big-endian each)
 *   0x2B PASET   - page/row address set (y0,y1, 16-bit big-endian each)
 *   0x2C RAMWR   - stream RGB565 pixel data into the current window
 *   0x36 MADCTL  - memory access control (only the MV/row-col-exchange bit
 *                  is used here, to pick portrait vs landscape framebuffer
 *                  shape to match ili9341.py's ROTATIONS table)
 * Everything else (SWRESET, SLPOUT, DISPON, power/gamma registers, ...) is
 * accepted and ignored - we don't need real panel timing/electrical
 * behavior for a "does the picture look right" simulator.
 */

#include "ili9341_sim.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>

#define ILI9341_CASET  0x2A
#define ILI9341_PASET  0x2B
#define ILI9341_RAMWR  0x2C
#define ILI9341_MADCTL 0x36

#define MAX_W 320
#define MAX_H 240

/* Push at most this often.  A full-screen blit() is split into ~4KB chunks
 * by ili9341.py, but the bridge must only receive a completed RAM window:
 * publishing after the first chunk makes almost the whole virtual panel stay
 * on the previous frame and looks like a frozen display. */
#define PUSH_MIN_INTERVAL_S 0.1

static uint8_t  framebuf[MAX_W * MAX_H * 2];
static uint16_t panel_w = MAX_W, panel_h = MAX_H;

static uint8_t  active_cmd = 0;
static uint8_t  cmd_arg_buf[8];
static int      cmd_arg_len = 0;

static uint16_t win_x0, win_y0, win_x1, win_y1;
static uint16_t cur_x, cur_y;
static size_t ramwr_pixels_remaining;

static int      have_hi_byte = 0;
static uint8_t  hi_byte = 0;

static int      dc_line = 16;

/* ------------------------------------------------------------------ */
/* Bridge connection                                                    */
/* ------------------------------------------------------------------ */

static int bridge_fd = -1;

static const char *bridge_socket_path(void) {
    const char *explicit_path = getenv("GAR_HW_SIM_SOCK");
    if (explicit_path && explicit_path[0]) {
        return explicit_path;
    }

    const char *runtime_dir = getenv("GAR_RUNTIME_DIR");
    if (runtime_dir && runtime_dir[0]) {
        static char path[108];
        snprintf(path, sizeof(path), "%s/hw_sim.sock", runtime_dir);
        return path;
    }

    return "/tmp/hw_sim.sock";
}

static int bridge_connect(void) {
    if (bridge_fd >= 0) return bridge_fd;
    bridge_fd = socket(AF_UNIX, SOCK_STREAM, 0);
    if (bridge_fd < 0) return -1;
    struct sockaddr_un addr = { .sun_family = AF_UNIX };
    const char *sock_path = bridge_socket_path();
    if (strlen(sock_path) >= sizeof(addr.sun_path)) {
        close(bridge_fd);
        bridge_fd = -1;
        return -1;
    }
    strcpy(addr.sun_path, sock_path);
    if (connect(bridge_fd, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        close(bridge_fd);
        bridge_fd = -1;
    }
    return bridge_fd;
}

/* Ask the bridge for the DC line's live value. Defaults to "command phase"
 * (0) if the bridge isn't reachable, so we fail closed (ignore data) rather
 * than misinterpreting garbage as pixels. */
static int bridge_get_dc(void) {
    int s = bridge_connect();
    if (s < 0) return 0;

    char req[80];
    int n = snprintf(req, sizeof(req),
        "{\"req\":\"get\",\"device\":\"gpio_out\",\"line\":%d}\n", dc_line);
    if (write(s, req, n) < 0) {
        close(bridge_fd);
        bridge_fd = -1;
        return 0;
    }

    char resp[128] = {0};
    int r = read(s, resp, sizeof(resp) - 1);
    if (r <= 0) {
        close(bridge_fd);
        bridge_fd = -1;
        return 0;
    }

    char *p = strstr(resp, "\"value\"");
    if (!p) return 0;
    p += 7;
    while (*p == ' ' || *p == ':') p++;
    return (*p == '1');
}

/* ------------------------------------------------------------------ */
/* base64 (same encoder used by ssd1306_sim.c)                         */
/* ------------------------------------------------------------------ */

static const char b64chars[] =
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

static void b64_encode(const uint8_t *in, size_t in_len, char *out) {
    size_t i, o = 0;
    for (i = 0; i + 2 < in_len; i += 3) {
        out[o++] = b64chars[(in[i] >> 2) & 0x3F];
        out[o++] = b64chars[((in[i] & 0x03) << 4) | ((in[i + 1] >> 4) & 0x0F)];
        out[o++] = b64chars[((in[i + 1] & 0x0F) << 2) | ((in[i + 2] >> 6) & 0x03)];
        out[o++] = b64chars[in[i + 2] & 0x3F];
    }
    if (i < in_len) {
        out[o++] = b64chars[(in[i] >> 2) & 0x3F];
        if (i + 1 < in_len) {
            out[o++] = b64chars[((in[i] & 0x03) << 4) | ((in[i + 1] >> 4) & 0x0F)];
            out[o++] = b64chars[(in[i + 1] & 0x0F) << 2];
        } else {
            out[o++] = b64chars[(in[i] & 0x03) << 4];
            out[o++] = '=';
        }
        out[o++] = '=';
    }
    out[o] = '\0';
}

static void push_framebuffer(void) {
    static struct timespec last_push;
    struct timespec now;
    clock_gettime(CLOCK_MONOTONIC, &now);
    double dt = (double)(now.tv_sec - last_push.tv_sec) +
                (double)(now.tv_nsec - last_push.tv_nsec) / 1e9;
    if (last_push.tv_sec != 0 && dt < PUSH_MIN_INTERVAL_S) return;
    last_push = now;

    int s = bridge_connect();
    if (s < 0) return;

    size_t raw_len = (size_t)panel_w * panel_h * 2;
    size_t b64_cap = ((raw_len + 2) / 3) * 4 + 1;
    char *b64 = malloc(b64_cap);
    if (!b64) return;
    b64_encode(framebuf, raw_len, b64);

    size_t msg_cap = b64_cap + 128;
    char *msg = malloc(msg_cap);
    if (!msg) { free(b64); return; }
    int n = snprintf(msg, msg_cap,
        "{\"event\":\"set\",\"device\":\"ili9341\",\"width\":%u,\"height\":%u,\"pixels\":\"%s\"}\n",
        panel_w, panel_h, b64);
    if (n > 0 && write(s, msg, (size_t)n) < 0) {
        close(bridge_fd);
        bridge_fd = -1;
    }
    free(b64);
    free(msg);
}

/* ------------------------------------------------------------------ */
/* Command/window state machine                                        */
/* ------------------------------------------------------------------ */

static void reset_window(void) {
    win_x0 = 0; win_y0 = 0;
    win_x1 = panel_w - 1; win_y1 = panel_h - 1;
    cur_x = 0; cur_y = 0;
    have_hi_byte = 0;
    ramwr_pixels_remaining = 0;
}

static void handle_command_byte(uint8_t cmd) {
    switch (cmd) {
    case ILI9341_CASET:
    case ILI9341_PASET:
    case ILI9341_MADCTL:
        active_cmd = cmd;
        cmd_arg_len = 0;
        break;
    case ILI9341_RAMWR:
        active_cmd = cmd;
        cur_x = win_x0;
        cur_y = win_y0;
        have_hi_byte = 0;
        ramwr_pixels_remaining =
            (size_t)(win_x1 - win_x0 + 1) * (size_t)(win_y1 - win_y0 + 1);
        break;
    default:
        active_cmd = 0; /* data bytes for unhandled commands are ignored */
        break;
    }
}

static void handle_data_bytes(const uint8_t *data, size_t len) {
    switch (active_cmd) {
    case ILI9341_CASET:
        for (size_t i = 0; i < len && cmd_arg_len < 4; i++) cmd_arg_buf[cmd_arg_len++] = data[i];
        if (cmd_arg_len >= 4) {
            win_x0 = ((uint16_t)cmd_arg_buf[0] << 8) | cmd_arg_buf[1];
            win_x1 = ((uint16_t)cmd_arg_buf[2] << 8) | cmd_arg_buf[3];
        }
        break;

    case ILI9341_PASET:
        for (size_t i = 0; i < len && cmd_arg_len < 4; i++) cmd_arg_buf[cmd_arg_len++] = data[i];
        if (cmd_arg_len >= 4) {
            win_y0 = ((uint16_t)cmd_arg_buf[0] << 8) | cmd_arg_buf[1];
            win_y1 = ((uint16_t)cmd_arg_buf[2] << 8) | cmd_arg_buf[3];
        }
        break;

    case ILI9341_MADCTL:
        if (len >= 1) {
            /* Bit 0x20 = MV (row/column exchange): matches the width/height
             * swap ili9341.py's _ROTATIONS table performs per rotation. */
            if (data[0] & 0x20) { panel_w = MAX_W; panel_h = MAX_H; }
            else                { panel_w = MAX_H; panel_h = MAX_W; }
            reset_window();
        }
        break;

    case ILI9341_RAMWR:
        for (size_t i = 0; i < len; i++) {
            uint8_t b = data[i];
            if (!have_hi_byte) {
                hi_byte = b;
                have_hi_byte = 1;
                continue;
            }
            have_hi_byte = 0;

            if (cur_x < panel_w && cur_y < panel_h &&
                cur_x <= win_x1 && cur_y <= win_y1) {
                size_t idx = ((size_t)cur_y * panel_w + cur_x) * 2;
                if (idx + 1 < sizeof(framebuf)) {
                    framebuf[idx] = hi_byte;
                    framebuf[idx + 1] = b;
                }
            }

            int ramwr_complete = 0;
            if (ramwr_pixels_remaining > 0) {
                ramwr_pixels_remaining--;
                ramwr_complete = ramwr_pixels_remaining == 0;
            }

            cur_x++;
            if (cur_x > win_x1) {
                cur_x = win_x0;
                cur_y++;
                if (cur_y > win_y1) cur_y = win_y0;
            }

            /* Send only after the complete SPI RAM window is populated.
             * For the normal video path this is exactly one 320x240 frame. */
            if (ramwr_complete) {
                push_framebuffer();
            }
        }
        break;

    default:
        break; /* command with data we don't track (gamma tables, etc.) */
    }
}

/* ------------------------------------------------------------------ */
/* Public API                                                           */
/* ------------------------------------------------------------------ */

void ili9341_sim_init(void) {
    memset(framebuf, 0, sizeof(framebuf));
    reset_window();
    fprintf(stderr, "[cuse_spi_ili9341] ILI9341 sim initialised (%ux%u, dc_line=%d)\n",
            panel_w, panel_h, dc_line);
}

void ili9341_sim_set_dc_line(int line) {
    dc_line = line;
}

void ili9341_sim_transfer(const uint8_t *tx, uint8_t *rx, size_t len) {
    if (rx) memset(rx, 0, len);
    if (!tx || len == 0) return;

    if (!bridge_get_dc()) {
        for (size_t i = 0; i < len; i++) handle_command_byte(tx[i]);
    } else {
        handle_data_bytes(tx, len);
    }
}
