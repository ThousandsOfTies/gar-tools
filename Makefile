# Gapless Agent Runtime simulation tools

# gar sim runtime build が simulation host のアーキテクチャに応じて CC を渡す。
# 直接呼ぶ場合の既定は EC2 Graviton 向けのクロスコンパイル。
# CC は make の組込み変数なので ?= ではなく origin で判定する。
ifeq ($(origin CC),default)
CC = aarch64-linux-gnu-gcc
endif

.PHONY: all clean

all:
	$(MAKE) -C targets/linux-device/runtime CC=$(CC)

clean:
	$(MAKE) -C targets/linux-device/runtime clean
