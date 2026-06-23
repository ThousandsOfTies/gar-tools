#pragma once

#include <stdint.h>

#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef void *esp_event_base_t;
typedef int32_t esp_event_handler_instance_t;
typedef void (*esp_event_handler_t)(void *handler_arg, esp_event_base_t event_base, int32_t event_id, void *event_data);

esp_err_t esp_event_loop_create_default(void);
esp_err_t esp_event_handler_register(esp_event_base_t event_base, int32_t event_id, esp_event_handler_t event_handler, void *event_handler_arg);

#ifdef __cplusplus
}
#endif
