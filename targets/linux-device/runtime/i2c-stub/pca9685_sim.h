#ifndef GAR_PCA9685_SIM_H
#define GAR_PCA9685_SIM_H

#include <stdint.h>

#define PCA9685_SIM_ADDR 0x40
#define PCA9685_CHANNEL_COUNT 16

void pca9685_sim_init(void);
uint8_t pca9685_sim_read_reg(uint8_t reg);
void pca9685_sim_write_reg(uint8_t reg, uint8_t value);

#endif
