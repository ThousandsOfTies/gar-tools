HOSTCC ?= cc
HOSTCXX ?= c++
CFLAGS = -std=c11 -Wall -Wextra -Werror -O2

check:
	@set -e; test_bin=$$(mktemp /tmp/gar-gc9a01-test.XXXXXX); \
	trap 'rm -f "$$test_bin"' EXIT; \
	$(HOSTCC) $(CFLAGS) -o "$$test_bin" test_gc9a01_init.c; "$$test_bin"
	@set -e; test_bin=$$(mktemp /tmp/gar-gc9a01-linux-test.XXXXXX); \
	trap 'rm -f "$$test_bin"' EXIT; \
	$(HOSTCXX) -std=c++11 -Wall -Wextra -Werror -O2 test_gc9a01_linux.cpp \
	-Wl,--wrap=open,--wrap=close,--wrap=ioctl,--wrap=write,--wrap=nanosleep \
	-o "$$test_bin"; "$$test_bin"

.PHONY: check
