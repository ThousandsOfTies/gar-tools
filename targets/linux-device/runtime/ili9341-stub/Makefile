CC       = gcc
CFLAGS   = -Wall -Wextra -O2 -D_FILE_OFFSET_BITS=64 -I/usr/include/fuse3
LDFLAGS  = -lfuse3

# ARM build from this subdirectory: make CC=aarch64-linux-gnu-gcc

SRCS = cuse_spi_ili9341.c ili9341_sim.c
HEADERS = ili9341_sim.h
BIN  = cuse_spi_ili9341

$(BIN): $(SRCS) $(HEADERS)
	$(CC) $(CFLAGS) -o $@ $(SRCS) $(LDFLAGS)

clean:
	rm -f $(BIN)

# Helper: run the stub (needs /dev/fuse accessible)
run: $(BIN)
	sudo ./$(BIN) -f --devname=spidev0.0 --dc-line=16

# Run without sudo if group 'fuse' is set up:
run-user: $(BIN)
	./$(BIN) -f --devname=spidev0.0 --dc-line=16

.PHONY: clean run run-user
