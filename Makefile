# Gapless Agent Runtime target tools

SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c

# gar sim runtime build passes CC for the selected simulation host. Keep the
# direct-invocation default compatible with the EC2 Graviton runtime.
ifeq ($(origin CC),default)
CC = aarch64-linux-gnu-gcc
endif

HOSTCC ?= cc
NODE ?= node
PYTHON ?= python3
RUNTIME_DIR := targets/linux-device/runtime

.PHONY: all linux-runtime examples experiments check check-python check-json
.PHONY: check-shell check-js check-runtime-contract check-i2c clean

all: linux-runtime

linux-runtime:
	$(MAKE) -C $(RUNTIME_DIR) runtime CC=$(CC)

examples:
	$(MAKE) -C $(RUNTIME_DIR) examples CC=$(CC)

experiments:
	$(MAKE) -C $(RUNTIME_DIR) experiments CC=$(CC)

check: check-python check-json check-shell check-js check-runtime-contract check-i2c

check-python:
	$(PYTHON) tools/check_python_syntax.py
	$(PYTHON) -m unittest discover -s tests -v
	$(PYTHON) -m unittest discover -s targets/linux-device/runtime/web-bridge/tests -v

check-json:
	@find targets \
		-type d \( -name .pio -o -name build -o -name __pycache__ -o -name node_modules \) -prune \
		-o -type f -name '*.json' -print0 \
		| xargs -0 -r -n 1 $(PYTHON) -m json.tool >/dev/null

check-shell:
	@while IFS= read -r -d '' file; do \
		if head -n 1 "$$file" | grep -Eq '^#!.*bash([[:space:]]|$$)'; then \
			bash -n "$$file"; \
		elif head -n 1 "$$file" | grep -Eq '^#!.*sh([[:space:]]|$$)'; then \
			sh -n "$$file"; \
		fi; \
	done < <(find targets \
		-type d \( -name .pio -o -name build -o -name __pycache__ -o -name node_modules \) -prune \
		-o -type f -print0)

check-js:
	@command -v $(NODE) >/dev/null || { \
		echo "JavaScript syntax check requires Node.js (override with NODE=/path/to/node)." >&2; \
		exit 1; \
	}
	$(NODE) --check targets/linux-device/runtime/web-bridge/panel/panel.js

check-runtime-contract:
	$(PYTHON) tools/check_runtime_contract.py

check-i2c:
	$(MAKE) -C $(RUNTIME_DIR) check HOSTCC=$(HOSTCC)

clean:
	$(MAKE) -C $(RUNTIME_DIR) clean
