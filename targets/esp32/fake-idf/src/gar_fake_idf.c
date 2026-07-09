#include "driver/gpio.h"
#include "driver/i2c.h"
#include "driver/spi_master.h"
#include "driver/uart.h"
#include "esp_event.h"
#include "esp_netif.h"
#include "esp_wifi.h"
#include "freertos/event_groups.h"
#include "freertos/queue.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#include "freertos/timers.h"
#include "nvs_flash.h"

#include <string.h>

static int gar_fake_handle;
static TickType_t gar_fake_ticks;

static void *gar_fake_nonnull_handle(void) {
  return &gar_fake_handle;
}

const char *esp_err_to_name(esp_err_t code) {
  return code == ESP_OK ? "ESP_OK" : "ESP_FAIL";
}

BaseType_t xTaskCreate(TaskFunction_t task, const char *name, uint32_t stack_depth, void *params, UBaseType_t priority, TaskHandle_t *handle) {
  (void)task;
  (void)name;
  (void)stack_depth;
  (void)params;
  (void)priority;
  if (handle) {
    *handle = gar_fake_nonnull_handle();
  }
  return pdPASS;
}

void vTaskDelay(TickType_t ticks) {
  gar_fake_ticks += ticks;
}

void vTaskDelete(TaskHandle_t task) {
  (void)task;
}

TickType_t xTaskGetTickCount(void) {
  return gar_fake_ticks;
}

QueueHandle_t xQueueCreate(UBaseType_t length, UBaseType_t item_size) {
  (void)length;
  (void)item_size;
  return gar_fake_nonnull_handle();
}

BaseType_t xQueueSend(QueueHandle_t queue, const void *item, TickType_t ticks_to_wait) {
  (void)queue;
  (void)item;
  (void)ticks_to_wait;
  return pdPASS;
}

BaseType_t xQueueReceive(QueueHandle_t queue, void *buffer, TickType_t ticks_to_wait) {
  (void)queue;
  (void)buffer;
  (void)ticks_to_wait;
  return pdPASS;
}

void vQueueDelete(QueueHandle_t queue) {
  (void)queue;
}

SemaphoreHandle_t xSemaphoreCreateMutex(void) {
  return gar_fake_nonnull_handle();
}

BaseType_t xSemaphoreTake(SemaphoreHandle_t semaphore, TickType_t ticks_to_wait) {
  (void)semaphore;
  (void)ticks_to_wait;
  return pdPASS;
}

BaseType_t xSemaphoreGive(SemaphoreHandle_t semaphore) {
  (void)semaphore;
  return pdPASS;
}

void vSemaphoreDelete(SemaphoreHandle_t semaphore) {
  (void)semaphore;
}

EventGroupHandle_t xEventGroupCreate(void) {
  return gar_fake_nonnull_handle();
}

EventBits_t xEventGroupSetBits(EventGroupHandle_t event_group, EventBits_t bits_to_set) {
  (void)event_group;
  return bits_to_set;
}

EventBits_t xEventGroupClearBits(EventGroupHandle_t event_group, EventBits_t bits_to_clear) {
  (void)event_group;
  (void)bits_to_clear;
  return 0;
}

EventBits_t xEventGroupWaitBits(EventGroupHandle_t event_group, EventBits_t bits_to_wait_for, BaseType_t clear_on_exit, BaseType_t wait_for_all_bits, TickType_t ticks_to_wait) {
  (void)event_group;
  (void)clear_on_exit;
  (void)wait_for_all_bits;
  (void)ticks_to_wait;
  return bits_to_wait_for;
}

void vEventGroupDelete(EventGroupHandle_t event_group) {
  (void)event_group;
}

TimerHandle_t xTimerCreate(const char *name, TickType_t period, BaseType_t auto_reload, void *timer_id, TimerCallbackFunction_t callback) {
  (void)name;
  (void)period;
  (void)auto_reload;
  (void)timer_id;
  (void)callback;
  return gar_fake_nonnull_handle();
}

BaseType_t xTimerStart(TimerHandle_t timer, TickType_t ticks_to_wait) {
  (void)timer;
  (void)ticks_to_wait;
  return pdPASS;
}

BaseType_t xTimerStop(TimerHandle_t timer, TickType_t ticks_to_wait) {
  (void)timer;
  (void)ticks_to_wait;
  return pdPASS;
}

BaseType_t xTimerDelete(TimerHandle_t timer, TickType_t ticks_to_wait) {
  (void)timer;
  (void)ticks_to_wait;
  return pdPASS;
}

esp_err_t nvs_flash_init(void) {
  return ESP_OK;
}

esp_err_t nvs_flash_erase(void) {
  return ESP_OK;
}

esp_err_t nvs_flash_deinit(void) {
  return ESP_OK;
}

esp_err_t esp_event_loop_create_default(void) {
  return ESP_OK;
}

esp_err_t esp_event_handler_register(esp_event_base_t event_base, int32_t event_id, esp_event_handler_t event_handler, void *event_handler_arg) {
  (void)event_base;
  (void)event_id;
  (void)event_handler;
  (void)event_handler_arg;
  return ESP_OK;
}

esp_err_t esp_netif_init(void) {
  return ESP_OK;
}

esp_netif_t *esp_netif_create_default_wifi_sta(void) {
  return gar_fake_nonnull_handle();
}

esp_netif_t *esp_netif_create_default_wifi_ap(void) {
  return gar_fake_nonnull_handle();
}

esp_err_t esp_wifi_init(const wifi_init_config_t *config) {
  (void)config;
  return ESP_OK;
}

esp_err_t esp_wifi_deinit(void) {
  return ESP_OK;
}

esp_err_t esp_wifi_set_mode(wifi_mode_t mode) {
  (void)mode;
  return ESP_OK;
}

esp_err_t esp_wifi_start(void) {
  return ESP_OK;
}

esp_err_t esp_wifi_stop(void) {
  return ESP_OK;
}

esp_err_t esp_wifi_connect(void) {
  return ESP_OK;
}

esp_err_t esp_wifi_disconnect(void) {
  return ESP_OK;
}

esp_err_t gpio_config(const gpio_config_t *config) {
  (void)config;
  return ESP_OK;
}

esp_err_t gpio_set_direction(gpio_num_t gpio_num, gpio_mode_t mode) {
  (void)gpio_num;
  (void)mode;
  return ESP_OK;
}

esp_err_t gpio_set_level(gpio_num_t gpio_num, uint32_t level) {
  (void)gpio_num;
  (void)level;
  return ESP_OK;
}

int gpio_get_level(gpio_num_t gpio_num) {
  (void)gpio_num;
  return 0;
}

esp_err_t uart_param_config(uart_port_t uart_num, const uart_config_t *uart_config) {
  (void)uart_num;
  (void)uart_config;
  return ESP_OK;
}

esp_err_t uart_set_pin(uart_port_t uart_num, int tx_io_num, int rx_io_num, int rts_io_num, int cts_io_num) {
  (void)uart_num;
  (void)tx_io_num;
  (void)rx_io_num;
  (void)rts_io_num;
  (void)cts_io_num;
  return ESP_OK;
}

esp_err_t uart_driver_install(uart_port_t uart_num, int rx_buffer_size, int tx_buffer_size, int queue_size, void *uart_queue, int intr_alloc_flags) {
  (void)uart_num;
  (void)rx_buffer_size;
  (void)tx_buffer_size;
  (void)queue_size;
  (void)uart_queue;
  (void)intr_alloc_flags;
  return ESP_OK;
}

int uart_write_bytes(uart_port_t uart_num, const void *src, size_t size) {
  (void)uart_num;
  (void)src;
  return (int)size;
}

int uart_read_bytes(uart_port_t uart_num, void *buf, uint32_t length, uint32_t ticks_to_wait) {
  (void)uart_num;
  (void)ticks_to_wait;
  if (buf && length > 0) {
    memset(buf, 0, length);
  }
  return 0;
}

esp_err_t i2c_param_config(i2c_port_t i2c_num, const i2c_config_t *i2c_conf) {
  (void)i2c_num;
  (void)i2c_conf;
  return ESP_OK;
}

esp_err_t i2c_driver_install(i2c_port_t i2c_num, i2c_mode_t mode, size_t slv_rx_buf_len, size_t slv_tx_buf_len, int intr_alloc_flags) {
  (void)i2c_num;
  (void)mode;
  (void)slv_rx_buf_len;
  (void)slv_tx_buf_len;
  (void)intr_alloc_flags;
  return ESP_OK;
}

esp_err_t i2c_driver_delete(i2c_port_t i2c_num) {
  (void)i2c_num;
  return ESP_OK;
}

i2c_cmd_handle_t i2c_cmd_link_create(void) {
  return gar_fake_nonnull_handle();
}

void i2c_cmd_link_delete(i2c_cmd_handle_t cmd_handle) {
  (void)cmd_handle;
}

esp_err_t i2c_master_cmd_begin(i2c_port_t i2c_num, i2c_cmd_handle_t cmd_handle, uint32_t ticks_to_wait) {
  (void)i2c_num;
  (void)cmd_handle;
  (void)ticks_to_wait;
  return ESP_OK;
}

esp_err_t spi_bus_initialize(spi_host_device_t host_id, const spi_bus_config_t *bus_config, int dma_chan) {
  (void)host_id;
  (void)bus_config;
  (void)dma_chan;
  return ESP_OK;
}

esp_err_t spi_bus_free(spi_host_device_t host_id) {
  (void)host_id;
  return ESP_OK;
}

esp_err_t spi_bus_add_device(spi_host_device_t host_id, const spi_device_interface_config_t *dev_config, spi_device_handle_t *handle) {
  (void)host_id;
  (void)dev_config;
  if (handle) {
    *handle = gar_fake_nonnull_handle();
  }
  return ESP_OK;
}

esp_err_t spi_bus_remove_device(spi_device_handle_t handle) {
  (void)handle;
  return ESP_OK;
}

esp_err_t spi_device_transmit(spi_device_handle_t handle, spi_transaction_t *trans_desc) {
  (void)handle;
  (void)trans_desc;
  return ESP_OK;
}
