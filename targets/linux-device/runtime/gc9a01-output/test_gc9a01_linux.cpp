// Exercise the real Linux driver without opening hardware. Only OS calls are
// intercepted; reset, initialization, frame encoding and cleanup are unchanged.
#include "gc9a01_linux.hpp"
#include <cassert>
#include <cstdarg>
#include <iostream>
#include <set>
#include <vector>

struct Command { uint8_t code; std::vector<uint8_t> data; };
static std::vector<Command> commands;
static std::vector<unsigned> delays;
static std::vector<bool> resetValues;
static std::set<int> opened;
static int nextFd, spiFd, dcFd, resetFd;
static bool dataPhase, failWrites, shortWrites;

static void fresh() {
    assert(opened.empty());
    commands.clear(); delays.clear(); resetValues.clear();
    nextFd = 10; spiFd = dcFd = resetFd = -1;
    dataPhase = failWrites = shortWrites = false;
}
extern "C" int __wrap_open(const char*, int flags, ...) {
    int fd = nextFd++;
    opened.insert(fd);
    if (flags & O_WRONLY) spiFd = fd;
    return fd;
}
extern "C" int __wrap_close(int fd) {
    assert(opened.erase(fd) == 1);
    return 0;
}
extern "C" int __wrap_ioctl(int fd, unsigned long operation, ...) {
    assert(opened.count(fd));
    va_list args; va_start(args, operation);
    void* argument = va_arg(args, void*); va_end(args);
    if (operation == GPIO_V2_GET_LINE_IOCTL) {
        auto* request = static_cast<gpio_v2_line_request*>(argument);
        request->fd = nextFd++;
        opened.insert(request->fd);
        if (dcFd < 0) dcFd = request->fd;
        else {
            resetFd = request->fd;
            assert(request->config.attrs[0].attr.values == 1);
        }
    } else if (operation == GPIO_V2_LINE_SET_VALUES_IOCTL) {
        auto* value = static_cast<gpio_v2_line_values*>(argument);
        if (fd == dcFd) dataPhase = value->bits != 0;
        else { assert(fd == resetFd); resetValues.push_back(value->bits != 0); }
    }
    return 0;
}
extern "C" ssize_t __wrap_write(int fd, const void* buffer, size_t size) {
    assert(fd == spiFd && opened.count(fd));
    if (failWrites) { errno = EIO; return -1; }
    const auto* bytes = static_cast<const uint8_t*>(buffer);
    if (shortWrites && size > 1) size = std::min(size, static_cast<size_t>(37));
    if (!dataPhase) { assert(size == 1); commands.push_back(Command{bytes[0], {}}); }
    else {
        assert(!commands.empty());
        commands.back().data.insert(commands.back().data.end(), bytes, bytes + size);
    }
    return static_cast<ssize_t>(size);
}
extern "C" int __wrap_nanosleep(const timespec* time, timespec*) {
    delays.push_back(static_cast<unsigned>(time->tv_sec * 1000 + time->tv_nsec / 1000000));
    return 0;
}

int main() {
    fresh();
    {
        gar::Gc9a01Linux lcd("/dev/spidev1.0", "/dev/gpiochip1", 228, 16000000, 262);
        assert((resetValues == std::vector<bool>{false, true}));
        assert((delays == std::vector<unsigned>{20, 20, 150, 150, 150}));
    }
    const auto hardwareInit = commands;
    assert(!hardwareInit.empty() && hardwareInit.back().code == 0x29);
    fresh();
    {
        gar::Gc9a01Linux lcd("/dev/spidev0.0", "/dev/gpiochip0", 16, 8000000);
        assert(resetFd == -1 && resetValues.empty());
        assert((delays == std::vector<unsigned>{150, 150, 150}));
        assert(commands.front().code == 0x01); // software reset, not bypass
        assert(commands.size() == hardwareInit.size() + 1);
        for (size_t i = 0; i < hardwareInit.size(); ++i) {
            assert(commands[i + 1].code == hardwareInit[i].code);
            assert(commands[i + 1].data == hardwareInit[i].data);
        }
        std::array<uint16_t, 240 * 240> pixels{};
        pixels[0] = 0xf800; pixels[1] = 0x07e0; pixels[2] = 0x001f;
        shortWrites = true;
        lcd.frame(pixels.data(), pixels.size());
        assert(commands.back().code == 0x2c);
        const auto& frame = commands.back().data;
        assert(frame.size() == pixels.size() * 2);
        assert(frame[0] == 0xf8 && frame[1] == 0 && frame[2] == 7 && frame[3] == 0xe0);
        assert(frame[4] == 0 && frame[5] == 0x1f);
    }
    fresh();
    failWrites = true;
    bool failed = false;
    try { gar::Gc9a01Linux lcd("/dev/spi", "/dev/gpio", 1, 8000000, 2); }
    catch (const std::runtime_error&) { failed = true; }
    assert(failed && opened.empty()); // failed constructor releases GPIO/SPI
    std::cout << "PASS: identical full init after either reset, frame stream, failure cleanup\n";
}
