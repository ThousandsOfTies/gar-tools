# Linux device runtime simulation tools build

CC = aarch64-linux-gnu-gcc

SUBDIRS = gpio-stub spi-stub i2c-stub ili9341-stub test

.PHONY: all clean $(SUBDIRS)

all:
	$(MAKE) -C gpio-stub     CC=$(CC)
	$(MAKE) -C spi-stub      CC=$(CC)
	$(MAKE) -C i2c-stub      CC=$(CC)
	$(MAKE) -C ili9341-stub  CC=$(CC)
	$(MAKE) -C test          CC=$(CC)

clean:
	$(MAKE) -C gpio-stub     clean
	$(MAKE) -C spi-stub      clean
	$(MAKE) -C i2c-stub      clean
	$(MAKE) -C ili9341-stub  clean
	$(MAKE) -C test          clean
