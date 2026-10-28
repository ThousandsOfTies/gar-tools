CC = gcc
HOSTCC ?= cc
CFLAGS = -std=c11 -Wall -Wextra -Werror -O2
BIN = gar_rotary_input

$(BIN): rotary_input.c rotary_decoder.h
	$(CC) $(CFLAGS) -o $@ rotary_input.c

check:
	@set -e; test_bin=$$(mktemp /tmp/gar-rotary-test.XXXXXX); \
	trap 'rm -f "$$test_bin"' EXIT; \
	$(HOSTCC) $(CFLAGS) -o "$$test_bin" test_rotary_decoder.c; "$$test_bin"

clean:
	rm -f $(BIN)

.PHONY: check clean
