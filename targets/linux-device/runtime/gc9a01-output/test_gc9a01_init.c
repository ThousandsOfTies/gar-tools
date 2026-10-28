#include "gc9a01_init.h"
#include <assert.h>
#include <stdio.h>

struct capture { unsigned calls, delays; int fail_at; uint8_t last; int sleep_out, display_on, rgb565; };
static int command(void *context, uint8_t instruction, const uint8_t *data, size_t length) {
    struct capture *capture = context;
    capture->calls++;
    if ((int)capture->calls == capture->fail_at) return -1;
    if (instruction == 0x3a) { assert(length == 1 && data[0] == 0x05); capture->rgb565 = 1; }
    if (instruction == 0x11) { assert(capture->rgb565); capture->sleep_out = 1; }
    if (instruction == 0x29) { assert(capture->sleep_out && capture->delays == 1); capture->display_on = 1; }
    capture->last = instruction;
    return 0;
}
static void delay(void *context, unsigned milliseconds) {
    struct capture *capture = context;
    assert(milliseconds >= 120 && (capture->last == 0x11 || capture->last == 0x29));
    capture->delays++;
}
int main(void) {
    struct capture ok = {0};
    assert(gar_gc9a01_initialize(&ok, command, delay) == 0);
    assert(ok.display_on && ok.delays == 2 && ok.last == 0x29);
    struct capture failure = {.fail_at = 4};
    assert(gar_gc9a01_initialize(&failure, command, delay) == -1);
    assert(failure.calls == 4 && failure.delays == 0 && !failure.display_on);
    puts("PASS: RGB565 initialization, sleep/display timing and transport failure propagation");
    return 0;
}
