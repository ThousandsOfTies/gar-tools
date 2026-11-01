# Linux device runtime simulation tools build

# gar sim build runtime passes CC for the selected simulation host. Keep the
# direct-invocation default compatible with the EC2 Graviton runtime.
ifeq ($(origin CC),default)
CC = aarch64-linux-gnu-gcc
endif

HOSTCC ?= cc

.PHONY: all runtime examples experiments check clean

all: runtime

runtime:
	$(MAKE) -C spi-stub      CC=$(CC)
	$(MAKE) -C i2c-stub      CC=$(CC)
	$(MAKE) -C ili9341-stub  CC=$(CC)
	$(MAKE) -C gc9a01-stub   CC=$(CC)
	$(MAKE) -C rotary-input  CC=$(CC)

examples:
	$(MAKE) -C test          CC=$(CC)

experiments:
	$(MAKE) -C gpio-stub     CC=$(CC)

check:
	$(MAKE) -C i2c-stub check HOSTCC=$(HOSTCC)
	$(MAKE) -C rotary-input check HOSTCC=$(HOSTCC)
	$(MAKE) -C gc9a01-output check HOSTCC=$(HOSTCC)

clean:
	$(MAKE) -C spi-stub      clean
	$(MAKE) -C i2c-stub      clean
	$(MAKE) -C ili9341-stub  clean
	$(MAKE) -C gc9a01-stub   clean
	$(MAKE) -C rotary-input  clean
	$(MAKE) -C gpio-stub     clean
	$(MAKE) -C test          clean
