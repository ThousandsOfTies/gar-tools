/* Generic LVGL 7 browser display and pointer driver. No application code. */
#include <lvgl.h>
#include <stdint.h>
#include <string.h>

#ifndef GAR_LV_WIDTH
#define GAR_LV_WIDTH 240
#endif
#ifndef GAR_LV_HEIGHT
#define GAR_LV_HEIGHT 240
#endif
#ifndef GAR_LV_BUFFER_ROWS
#define GAR_LV_BUFFER_ROWS 24
#endif
#if GAR_LV_WIDTH <= 0 || GAR_LV_HEIGHT <= 0 || GAR_LV_BUFFER_ROWS <= 0
#error "Display dimensions and draw buffer rows must be positive"
#endif
#define DRAW_ROWS ((GAR_LV_BUFFER_ROWS < GAR_LV_HEIGHT) ? GAR_LV_BUFFER_ROWS : GAR_LV_HEIGHT)

static uint8_t rgba[GAR_LV_WIDTH * GAR_LV_HEIGHT * 4];
static lv_color_t buffer[GAR_LV_WIDTH * DRAW_ROWS];
static lv_disp_buf_t display_buffer;
static lv_indev_t* pointer;
static lv_indev_data_t pointer_data;
static unsigned frame;

static void flush(lv_disp_drv_t* display, const lv_area_t* area, lv_color_t* pixels) {
  for (int y = area->y1; y <= area->y2; ++y) {
    for (int x = area->x1; x <= area->x2; ++x) {
      lv_color32_t colour = { .full = lv_color_to32(*pixels++) };
      if (x < 0 || x >= GAR_LV_WIDTH || y < 0 || y >= GAR_LV_HEIGHT) continue;
      const unsigned at = ((unsigned)y * GAR_LV_WIDTH + x) * 4;
      rgba[at] = colour.ch.red; rgba[at + 1] = colour.ch.green;
      rgba[at + 2] = colour.ch.blue; rgba[at + 3] = 255;
    }
  }
  ++frame;
  lv_disp_flush_ready(display);
}
static bool read_pointer(lv_indev_drv_t* driver, lv_indev_data_t* data) {
  (void)driver;
  *data = pointer_data;
  return false;
}
void gar_lv_init(void) {
  lv_init();
  lv_disp_buf_init(&display_buffer, buffer, NULL, GAR_LV_WIDTH * DRAW_ROWS);
  lv_disp_drv_t display;
  lv_disp_drv_init(&display);
  display.hor_res = GAR_LV_WIDTH; display.ver_res = GAR_LV_HEIGHT;
  display.buffer = &display_buffer; display.flush_cb = flush;
  lv_disp_drv_register(&display);
  lv_indev_drv_t input;
  lv_indev_drv_init(&input);
  input.type = LV_INDEV_TYPE_POINTER; input.read_cb = read_pointer;
  input.long_press_time = 900;
  pointer = lv_indev_drv_register(&input);
  pointer_data.state = LV_INDEV_STATE_REL;
}
void gar_lv_tick(unsigned ms) { lv_tick_inc(ms); lv_task_handler(); }
void gar_lv_pointer(int x, int y, int pressed) {
  pointer_data.point.x = x; pointer_data.point.y = y;
  pointer_data.state = pressed ? LV_INDEV_STATE_PR : LV_INDEV_STATE_REL;
  /* Sample every browser input, including down/up inside one animation frame. */
  lv_task_ready(pointer->driver.read_task);
  lv_task_handler();
}
void gar_lv_cancel(void) {
  pointer_data.state = LV_INDEV_STATE_REL;
  lv_indev_reset(pointer, NULL);
}
uint8_t* gar_lv_framebuffer(void) { return rgba; }
unsigned gar_lv_frame(void) { return frame; }
unsigned gar_lv_width(void) { return GAR_LV_WIDTH; }
unsigned gar_lv_height(void) { return GAR_LV_HEIGHT; }
