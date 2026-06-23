#pragma once

#include <stddef.h>
#include <stdint.h>

#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef int i2c_port_t;

typedef enum {
  I2C_MODE_SLAVE = 0,
  I2C_MODE_MASTER = 1,
} i2c_mode_t;

typedef struct {
  i2c_mode_t mode;
  int sda_io_num;
  int scl_io_num;
  uint32_t master_clk_speed;
} i2c_config_t;

typedef void *i2c_cmd_handle_t;

esp_err_t i2c_param_config(i2c_port_t i2c_num, const i2c_config_t *i2c_conf);
esp_err_t i2c_driver_install(i2c_port_t i2c_num, i2c_mode_t mode, size_t slv_rx_buf_len, size_t slv_tx_buf_len, int intr_alloc_flags);
esp_err_t i2c_driver_delete(i2c_port_t i2c_num);
i2c_cmd_handle_t i2c_cmd_link_create(void);
void i2c_cmd_link_delete(i2c_cmd_handle_t cmd_handle);
esp_err_t i2c_master_cmd_begin(i2c_port_t i2c_num, i2c_cmd_handle_t cmd_handle, uint32_t ticks_to_wait);

#ifdef __cplusplus
}
#endif
