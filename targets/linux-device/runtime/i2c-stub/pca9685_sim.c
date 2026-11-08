/* PCA9685 register model and web-bridge state publisher. */
#include "pca9685_sim.h"

#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>

#define MODE1 0x00
#define MODE2 0x01
#define LED0_ON_L 0x06
#define LED_REGISTER_COUNT (PCA9685_CHANNEL_COUNT * 4)
#define ALL_LED_ON_L 0xFA
#define ALL_LED_OFF_H 0xFD
#define PRE_SCALE 0xFE

static uint8_t registers[256];
static bool frequency_configured;
static int bridge_fd = -1;

static const char *bridge_socket_path(void) {
    const char *explicit_path = getenv("GAR_HW_SIM_SOCK");
    if (explicit_path && explicit_path[0]) return explicit_path;

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

    struct sockaddr_un address = {.sun_family = AF_UNIX};
    const char *path = bridge_socket_path();
    if (strlen(path) >= sizeof(address.sun_path)) {
        close(bridge_fd);
        bridge_fd = -1;
        return -1;
    }
    strcpy(address.sun_path, path);
    if (connect(bridge_fd, (struct sockaddr *)&address, sizeof(address)) < 0) {
        close(bridge_fd);
        bridge_fd = -1;
    }
    return bridge_fd;
}

static void close_bridge(void) {
    if (bridge_fd >= 0) close(bridge_fd);
    bridge_fd = -1;
}

static double pwm_frequency_hz(void) {
    return 25000000.0 / (4096.0 * ((double)registers[PRE_SCALE] + 1.0));
}

static void publish_state(void) {
    if (bridge_connect() < 0) return;

    char message[4096];
    size_t used = 0;
    int written = snprintf(
        message,
        sizeof(message),
        "{\"event\":\"set\",\"device\":\"pca9685\",\"address\":64,"
        "\"frequencyHz\":");
    if (written < 0 || (size_t)written >= sizeof(message)) return;
    used = (size_t)written;

    if (frequency_configured) {
        written = snprintf(message + used, sizeof(message) - used, "%.3f", pwm_frequency_hz());
    } else {
        written = snprintf(message + used, sizeof(message) - used, "null");
    }
    if (written < 0 || (size_t)written >= sizeof(message) - used) return;
    used += (size_t)written;

    written = snprintf(message + used, sizeof(message) - used, ",\"channels\":[");
    if (written < 0 || (size_t)written >= sizeof(message) - used) return;
    used += (size_t)written;

    for (unsigned int channel = 0; channel < PCA9685_CHANNEL_COUNT; ++channel) {
        size_t base = LED0_ON_L + channel * 4;
        unsigned int on = registers[base] | ((registers[base + 1] & 0x0fU) << 8);
        unsigned int off = registers[base + 2] | ((registers[base + 3] & 0x0fU) << 8);
        bool full_on = (registers[base + 1] & 0x10U) != 0;
        bool full_off = (registers[base + 3] & 0x10U) != 0;
        written = snprintf(
            message + used,
            sizeof(message) - used,
            "%s{\"channel\":%u,\"on\":%u,\"off\":%u,\"fullOn\":%s,\"fullOff\":%s}",
            channel ? "," : "",
            channel,
            on,
            off,
            full_on ? "true" : "false",
            full_off ? "true" : "false");
        if (written < 0 || (size_t)written >= sizeof(message) - used) return;
        used += (size_t)written;
    }

    written = snprintf(message + used, sizeof(message) - used, "]}\n");
    if (written < 0 || (size_t)written >= sizeof(message) - used) return;
    used += (size_t)written;

    ssize_t sent = send(bridge_fd, message, used, MSG_NOSIGNAL);
    if (sent < 0 || (size_t)sent != used) close_bridge();
}

void pca9685_sim_init(void) {
    memset(registers, 0, sizeof(registers));
    registers[MODE1] = 0x01;
    registers[MODE2] = 0x04;
    registers[PRE_SCALE] = 0x1e;
    frequency_configured = false;
    close_bridge();
}

uint8_t pca9685_sim_read_reg(uint8_t reg) {
    return registers[reg];
}

void pca9685_sim_write_reg(uint8_t reg, uint8_t value) {
    registers[reg] = value;
    if (reg == PRE_SCALE) frequency_configured = true;

    if (reg >= ALL_LED_ON_L && reg <= ALL_LED_OFF_H) {
        unsigned int field = reg - ALL_LED_ON_L;
        for (unsigned int channel = 0; channel < PCA9685_CHANNEL_COUNT; ++channel) {
            registers[LED0_ON_L + channel * 4 + field] = value;
        }
    }

    bool completed_channel = reg >= LED0_ON_L
        && reg < LED0_ON_L + LED_REGISTER_COUNT
        && ((reg - LED0_ON_L) % 4U) == 3U;
    if (completed_channel || reg == MODE1 || reg == MODE2 || reg == PRE_SCALE
            || reg == ALL_LED_OFF_H) {
        publish_state();
    }
}
