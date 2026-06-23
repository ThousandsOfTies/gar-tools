#pragma once

#include "freertos/FreeRTOS.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef void *TimerHandle_t;
typedef void (*TimerCallbackFunction_t)(TimerHandle_t timer);

TimerHandle_t xTimerCreate(const char *name, TickType_t period, BaseType_t auto_reload, void *timer_id, TimerCallbackFunction_t callback);
BaseType_t xTimerStart(TimerHandle_t timer, TickType_t ticks_to_wait);
BaseType_t xTimerStop(TimerHandle_t timer, TickType_t ticks_to_wait);
BaseType_t xTimerDelete(TimerHandle_t timer, TickType_t ticks_to_wait);

#ifdef __cplusplus
}
#endif
