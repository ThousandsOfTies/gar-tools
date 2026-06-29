#include <chrono>
#include <csignal>
#include <dlfcn.h>
#include <fcntl.h>
#include <string>
#include <sys/stat.h>
#include <sys/types.h>
#include <iostream>
#include <thread>
#include <vector>

namespace {
volatile std::sig_atomic_t g_running = 1;

void handle_signal(int) {
  g_running = 0;
}

bool device_exists(const std::string& path) {
  struct stat st;
  return stat(path.c_str(), &st) == 0;
}

void print_device_contract() {
  const std::vector<std::string> required = {
      "/dev/video0",
      "/dev/fb0",
      "/dev/i2c-3",
      "/dev/spidev0.0",
      "/dev/gpiochip0",
  };

  std::cout << "[gar-luckfox] device contract check" << std::endl;
  for (const auto& path : required) {
    std::cout << "  - " << path << ": " << (device_exists(path) ? "ok" : "missing") << std::endl;
  }
}

void print_runtime_capabilities() {
  void* rkmedia = dlopen("librkmedia.so", RTLD_LAZY | RTLD_LOCAL);
  void* rkaiq = dlopen("librkaiq.so", RTLD_LAZY | RTLD_LOCAL);

  std::cout << "[gar-luckfox] runtime capability check" << std::endl;
  std::cout << "  - librkmedia.so: " << (rkmedia ? "available" : "not found") << std::endl;
  std::cout << "  - librkaiq.so: " << (rkaiq ? "available" : "not found") << std::endl;

  if (rkmedia) {
    dlclose(rkmedia);
  }
  if (rkaiq) {
    dlclose(rkaiq);
  }
}
}  // namespace

int main() {
  std::signal(SIGINT, handle_signal);
  std::signal(SIGTERM, handle_signal);

  std::cout << "[gar-luckfox] bootstrap start" << std::endl;
  std::cout << "[gar-luckfox] policy: one binary, one device-path contract for real + sim" << std::endl;
  print_device_contract();
  print_runtime_capabilities();
  std::cout << "[gar-luckfox] TODO: initialize camera/encoder/ui/input using same code path" << std::endl;

  while (g_running) {
    std::this_thread::sleep_for(std::chrono::milliseconds(500));
  }

  std::cout << "[gar-luckfox] shutdown" << std::endl;
  return 0;
}
