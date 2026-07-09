#pragma once

#include <stddef.h>
#include <stdint.h>

#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef int spi_host_device_t;
typedef void *spi_device_handle_t;

typedef struct {
  int mosi_io_num;
  int miso_io_num;
  int sclk_io_num;
  int quadwp_io_num;
  int quadhd_io_num;
  int max_transfer_sz;
} spi_bus_config_t;

typedef struct {
  int command_bits;
  int address_bits;
  int dummy_bits;
  int mode;
  int clock_speed_hz;
  int spics_io_num;
  int queue_size;
} spi_device_interface_config_t;

typedef struct {
  uint32_t flags;
  size_t length;
  const void *tx_buffer;
  void *rx_buffer;
} spi_transaction_t;

esp_err_t spi_bus_initialize(spi_host_device_t host_id, const spi_bus_config_t *bus_config, int dma_chan);
esp_err_t spi_bus_free(spi_host_device_t host_id);
esp_err_t spi_bus_add_device(spi_host_device_t host_id, const spi_device_interface_config_t *dev_config, spi_device_handle_t *handle);
esp_err_t spi_bus_remove_device(spi_device_handle_t handle);
esp_err_t spi_device_transmit(spi_device_handle_t handle, spi_transaction_t *trans_desc);

#ifdef __cplusplus
}
#endif
