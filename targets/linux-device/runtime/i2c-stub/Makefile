CC       = gcc
CFLAGS   = -Wall -Wextra -O2 -D_FILE_OFFSET_BITS=64 -I/usr/include/fuse3
LDFLAGS  = -lfuse3 -lpthread
HOSTCC  ?= cc
TEST_CFLAGS = -std=c11 -Wall -Wextra -Werror -pedantic

# ARM build from this subdirectory: make CC=aarch64-linux-gnu-gcc

SRCS = cuse_i2c.c vl53l0x_sim.c ssd1306_sim.c
HEADERS = i2c_rdwr_plan.h vl53l0x_sim.h ssd1306_sim.h
BIN  = cuse_i2c

$(BIN): $(SRCS) $(HEADERS)
	$(CC) $(CFLAGS) -o $@ $(SRCS) $(LDFLAGS)

clean:
	rm -f $(BIN)

# Helper: run the stub (needs /dev/fuse accessible)
run: $(BIN)
	sudo ./$(BIN) -f --devname=i2c-1

# Run without sudo if group 'fuse' is set up:
run-user: $(BIN)
	./$(BIN) -f --devname=i2c-1

# Pure transfer-planning checks; no CUSE device or root privileges required.
check:
	@set -e; \
	tmp_bin=$$(mktemp /tmp/gar-i2c-rdwr-test.XXXXXX); \
	trap 'rm -f "$$tmp_bin"' EXIT; \
	$(HOSTCC) $(TEST_CFLAGS) -o "$$tmp_bin" test_i2c_rdwr_plan.c; \
	"$$tmp_bin"

.PHONY: clean run run-user check
