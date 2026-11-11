#include "rotary_config.h"
#include <assert.h>
#include <stdio.h>

int main(void) {
    assert(rotary_debounce_period("0") == 0);
    assert(rotary_debounce_period("1000") == 1000);
    assert(rotary_debounce_period("1000000") == 1000000);
    const char *invalid[] = {"", "-1", "1000001", "1.5", "no", "999999999999999999999999"};
    for (unsigned i = 0; i < sizeof(invalid) / sizeof(invalid[0]); i++)
        assert(rotary_debounce_period(invalid[i]) == -1);

    struct gpio_v2_line_config config;
    rotary_configure_input(&config, 0, 0);
    assert(config.flags == (GPIO_V2_LINE_FLAG_INPUT | GPIO_V2_LINE_FLAG_EDGE_RISING |
                            GPIO_V2_LINE_FLAG_EDGE_FALLING));
    assert(config.num_attrs == 0); /* Existing users request no debounce by default. */
    rotary_configure_input(&config, GPIO_V2_LINE_FLAG_BIAS_PULL_UP, 1000);
    assert(config.flags & GPIO_V2_LINE_FLAG_BIAS_PULL_UP);
    assert(config.num_attrs == 1);
    assert(config.attrs[0].attr.id == GPIO_V2_LINE_ATTR_ID_DEBOUNCE);
    assert(config.attrs[0].attr.debounce_period_us == 1000);
    assert(config.attrs[0].mask == 7); /* All three requested inputs, only. */
    rotary_configure_input(&config, 0, 0);
    assert(config.num_attrs == 0 && config.attrs[0].mask == 0);
    puts("PASS: optional kernel debounce, unchanged default request and period validation");
    return 0;
}
