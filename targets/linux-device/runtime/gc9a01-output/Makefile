HOSTCC ?= cc
CFLAGS = -std=c11 -Wall -Wextra -Werror -O2

check:
	@set -e; test_bin=$$(mktemp /tmp/gar-gc9a01-test.XXXXXX); \
	trap 'rm -f "$$test_bin"' EXIT; \
	$(HOSTCC) $(CFLAGS) -o "$$test_bin" test_gc9a01_init.c; "$$test_bin"

.PHONY: check
