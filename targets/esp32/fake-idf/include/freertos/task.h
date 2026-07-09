#pragma once

#include "freertos/FreeRTOS.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef void (*TaskFunction_t)(void *);
typedef void *TaskHandle_t;

BaseType_t xTaskCreate(TaskFunction_t task, const char *name, uint32_t stack_depth, void *params, UBaseType_t priority, TaskHandle_t *handle);
void vTaskDelay(TickType_t ticks);
void vTaskDelete(TaskHandle_t task);
TickType_t xTaskGetTickCount(void);

#ifdef __cplusplus
}
#endif
