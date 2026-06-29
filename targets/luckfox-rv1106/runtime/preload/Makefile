CC ?= gcc
CFLAGS ?= -O2 -fPIC -Wall -Wextra -Wpedantic
LDFLAGS ?= -shared -ldl

OUT = libgar_devredir.so

.PHONY: all clean

all: $(OUT)

$(OUT): devredir.c
	$(CC) $(CFLAGS) -o $@ $< $(LDFLAGS)

clean:
	rm -f $(OUT)
