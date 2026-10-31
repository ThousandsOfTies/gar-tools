CC = gcc
HOSTCC ?= cc
CFLAGS = -std=c11 -Wall -Wextra -Werror -O2
BIN = gar_rotary_input

$(BIN): rotary_input.c rotary_decoder.h rotary_sequence.h
	$(CC) $(CFLAGS) -o $@ rotary_input.c

check:
	@set -e; test_bin=$$(mktemp /tmp/gar-rotary-test.XXXXXX); \
	trap 'rm -f "$$test_bin"' EXIT; \
	$(HOSTCC) $(CFLAGS) -o "$$test_bin" test_rotary_decoder.c; "$$test_bin"; \
	$(HOSTCC) $(CFLAGS) -o "$$test_bin" test_rotary_sequence.c; \
	"$$test_bin" ../../../../tests/fixtures/rotary-lyra-events.csv

clean:
	rm -f $(BIN)

.PHONY: check clean
