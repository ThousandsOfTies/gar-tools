CC = gcc
CFLAGS = -Wall -Wextra -O2 -D_FILE_OFFSET_BITS=64 -I/usr/include/fuse3
MODEL_FLAGS = -DGAR_LCD_WIDTH=240 -DGAR_LCD_HEIGHT=240 -DGAR_LCD_EVENT_NAME='"gc9a01"' -DGAR_LCD_PUSH_INTERVAL_S=0.05
COMMON = ../ili9341-stub
BIN = cuse_spi_gc9a01

$(BIN): $(COMMON)/cuse_spi_ili9341.c $(COMMON)/ili9341_sim.c $(COMMON)/ili9341_sim.h
	$(CC) $(CFLAGS) $(MODEL_FLAGS) -o $@ $(COMMON)/cuse_spi_ili9341.c $(COMMON)/ili9341_sim.c -lfuse3

clean:
	rm -f cuse_spi_gc9a01

.PHONY: clean
