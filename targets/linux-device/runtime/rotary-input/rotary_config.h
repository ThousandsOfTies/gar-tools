#ifndef GAR_ROTARY_CONFIG_H
#define GAR_ROTARY_CONFIG_H
#include <errno.h>
#include <linux/gpio.h>
#include <stdint.h>
#include <stdlib.h>

static inline int rotary_debounce_period(const char *text) {
    char *end;
    errno = 0;
    long value = strtol(text, &end, 10);
    if (errno || !*text || *end || value < 0 || value > 1000000) return -1;
    return (int)value;
}

static inline void rotary_configure_input(struct gpio_v2_line_config *config,
                                          uint64_t bias, unsigned debounce_us) {
    *config = (struct gpio_v2_line_config){
        .flags = GPIO_V2_LINE_FLAG_INPUT | GPIO_V2_LINE_FLAG_EDGE_RISING |
                 GPIO_V2_LINE_FLAG_EDGE_FALLING | bias,
    };
    if (debounce_us) {
        config->num_attrs = 1;
        config->attrs[0].attr.id = GPIO_V2_LINE_ATTR_ID_DEBOUNCE;
        config->attrs[0].attr.debounce_period_us = debounce_us;
        /* Bits refer to clock/data/switch request indices, not board pins. */
        config->attrs[0].mask = 7;
    }
}
#endif
