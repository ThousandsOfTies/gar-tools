BUILD_DIR ?= build
TOOLCHAIN_FILE ?= ../toolchain/rv1106-buildroot-toolchain.cmake
CMAKE_BUILD_TYPE ?= Release
CMAKE_GENERATOR ?= Ninja
DEPLOY_SCRIPT ?= ../scripts/deploy_ssh.sh

.PHONY: all configure build install clean deploy

all: build

configure:
	cmake -S . -B $(BUILD_DIR) -G "$(CMAKE_GENERATOR)" \
		-DCMAKE_TOOLCHAIN_FILE=$(TOOLCHAIN_FILE) \
		-DCMAKE_BUILD_TYPE=$(CMAKE_BUILD_TYPE)

build: configure
	cmake --build $(BUILD_DIR) -- -j

install: build
	cmake --install $(BUILD_DIR) --prefix $(PWD)/$(BUILD_DIR)/stage

deploy: build
	"$(DEPLOY_SCRIPT)" "$(PWD)/$(BUILD_DIR)/gar_luckfox_streamer"

clean:
	rm -rf $(BUILD_DIR)
