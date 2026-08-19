#include "pca9685_sim.h"

#include <assert.h>
#include <stdio.h>

int main(void) {
    pca9685_sim_init();
    assert(pca9685_sim_read_reg(0x00) == 0x01);
    assert(pca9685_sim_read_reg(0x01) == 0x04);

    /* Channel 0: ON=0, OFF=307 (about 1.5 ms at 50 Hz). */
    pca9685_sim_write_reg(0x06, 0x00);
    pca9685_sim_write_reg(0x07, 0x00);
    pca9685_sim_write_reg(0x08, 0x33);
    pca9685_sim_write_reg(0x09, 0x01);
    assert(pca9685_sim_read_reg(0x08) == 0x33);
    assert(pca9685_sim_read_reg(0x09) == 0x01);

    /* ALL_LED full-off must be reflected by every channel. */
    pca9685_sim_write_reg(0xFD, 0x10);
    for (unsigned int channel = 0; channel < PCA9685_CHANNEL_COUNT; ++channel) {
        assert(pca9685_sim_read_reg(0x09 + channel * 4) == 0x10);
    }

    puts("pca9685 simulation tests passed");
    return 0;
}
