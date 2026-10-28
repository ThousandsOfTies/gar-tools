#define _POSIX_C_SOURCE 200809L
#include "rotary_decoder.h"
#include <errno.h>
#include <fcntl.h>
#include <getopt.h>
#include <linux/gpio.h>
#include <poll.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <unistd.h>

static volatile sig_atomic_t running = 1;
static void stop(int signum) { (void)signum; running = 0; }
static int offset(const char *text) {
    char *end; errno = 0; long value = strtol(text, &end, 10);
    if (errno || !*text || *end || value < 0 || value > 4095) return -1;
    return (int)value;
}
static unsigned phase_from_bits(uint64_t bits) {
    return ((bits & 1) ? 2u : 0u) | ((bits & 2) ? 1u : 0u);
}
static int sample(int fd, struct gpio_v2_line_values *values) {
    values->mask = 7;
    return ioctl(fd, GPIO_V2_LINE_GET_VALUES_IOCTL, values);
}
int main(int argc, char **argv) {
    const char *chip = NULL; int clock_line = -1, data_line = -1, switch_line = -1;
    const struct option options[] = {
        {"chip", required_argument, NULL, 'c'}, {"clock", required_argument, NULL, 'a'},
        {"data", required_argument, NULL, 'b'}, {"switch", required_argument, NULL, 's'},
        {"help", no_argument, NULL, 'h'}, {NULL, 0, NULL, 0}
    };
    int option;
    while ((option = getopt_long(argc, argv, "", options, NULL)) != -1) {
        switch (option) {
        case 'c': chip = optarg; break;
        case 'a': clock_line = offset(optarg); break;
        case 'b': data_line = offset(optarg); break;
        case 's': switch_line = offset(optarg); break;
        case 'h': puts("gar_rotary_input --chip /dev/gpiochipN --clock OFFSET --data OFFSET --switch OFFSET"); return 0;
        default: return 2;
        }
    }
    if (!chip || clock_line < 0 || data_line < 0 || switch_line < 0 || optind != argc ||
        clock_line == data_line || clock_line == switch_line || data_line == switch_line) {
        fputs("Select a GPIO chip and three distinct line offsets. Use --help.\n", stderr); return 2;
    }
    int chip_fd = open(chip, O_RDONLY | O_CLOEXEC);
    if (chip_fd < 0) { perror("open rotary GPIO chip"); return 1; }
    struct gpio_v2_line_request request = {0};
    request.offsets[0] = (unsigned)clock_line; request.offsets[1] = (unsigned)data_line;
    request.offsets[2] = (unsigned)switch_line; request.num_lines = 3; request.event_buffer_size = 64;
    request.config.flags = GPIO_V2_LINE_FLAG_INPUT | GPIO_V2_LINE_FLAG_EDGE_RISING | GPIO_V2_LINE_FLAG_EDGE_FALLING;
    strcpy(request.consumer, "GAR rotary input");
    if (ioctl(chip_fd, GPIO_V2_GET_LINE_IOCTL, &request) < 0) {
        perror("request rotary GPIO lines"); close(chip_fd); return 1;
    }
    close(chip_fd);
    struct gpio_v2_line_values values = {0};
    if (sample(request.fd, &values) < 0) { perror("sample rotary GPIO"); close(request.fd); return 1; }
    struct rotary_decoder decoder = {phase_from_bits(values.bits), 0};
    int pressed = !(values.bits & 4); uint64_t last_press = 0; unsigned last_sequence = 0;
    long long counter = 0;
    struct sigaction action = {0}; action.sa_handler = stop; sigemptyset(&action.sa_mask);
    sigaction(SIGTERM, &action, NULL); sigaction(SIGINT, &action, NULL);
    setvbuf(stdout, NULL, _IOLBF, 0);
    puts("{\"type\":\"ready\",\"counter\":0}");
    int result = 0;
    while (running) {
        struct pollfd descriptor = {request.fd, POLLIN, 0};
        int available = poll(&descriptor, 1, 500);
        if (available < 0 && errno == EINTR) continue;
        if (available < 0 || (descriptor.revents & (POLLERR | POLLHUP | POLLNVAL))) { perror("poll rotary GPIO"); result = 1; break; }
        if (!available) continue;
        struct gpio_v2_line_event event;
        ssize_t count = read(request.fd, &event, sizeof(event));
        if (count < 0 && errno == EINTR) continue;
        if (count != (ssize_t)sizeof(event)) { fputs("Incomplete rotary GPIO event\n", stderr); result = 1; break; }
        if (last_sequence && event.seqno != last_sequence + 1) {
            fputs("Rotary GPIO events lost; discarding incomplete detent\n", stderr);
            if (sample(request.fd, &values) < 0) { perror("resample rotary GPIO"); result = 1; break; }
            decoder.phase = phase_from_bits(values.bits); decoder.quarter_steps = 0;
            pressed = !(values.bits & 4); last_sequence = event.seqno; continue;
        }
        last_sequence = event.seqno;
        unsigned bit = event.offset == (unsigned)clock_line ? 0 : event.offset == (unsigned)data_line ? 1 : 2;
        if (event.id == GPIO_V2_LINE_EVENT_RISING_EDGE) values.bits |= (uint64_t)1 << bit;
        else if (event.id == GPIO_V2_LINE_EVENT_FALLING_EDGE) values.bits &= ~((uint64_t)1 << bit);
        else continue;
        if (bit < 2) {
            int direction = rotary_decode(&decoder, phase_from_bits(values.bits));
            if (direction) {
                counter += direction;
                printf("{\"type\":\"rotate\",\"direction\":%d,\"counter\":%lld}\n", direction, counter);
            }
        } else {
            int next_pressed = !(values.bits & 4);
            if (next_pressed && !pressed && event.timestamp_ns - last_press >= 60000000) {
                last_press = event.timestamp_ns;
                printf("{\"type\":\"press\",\"counter\":%lld}\n", counter);
            }
            pressed = next_pressed;
        }
    }
    close(request.fd); return result;
}
