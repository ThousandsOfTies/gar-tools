#pragma once

#include "gc9a01_init.h"
#include <algorithm>
#include <array>
#include <cerrno>
#include <cstring>
#include <fcntl.h>
#include <linux/gpio.h>
#include <linux/spi/spidev.h>
#include <stdexcept>
#include <string>
#include <sys/ioctl.h>
#include <time.h>
#include <unistd.h>

namespace gar {

// Linux device paths and line offsets are supplied by the caller's wiring.
// The same driver operates on kernel devices and CUSE/gpio-sim devices.
class Gc9a01Linux {
public:
    Gc9a01Linux(const std::string& spiPath, const std::string& chipPath,
                unsigned dcLine, unsigned hz, int resetLine = -1) {
        try {
            spi_ = open(spiPath.c_str(), O_WRONLY | O_CLOEXEC);
            check(spi_ >= 0, "open LCD SPI");
            uint8_t mode = 0, bits = 8;
            uint32_t speed = hz;
            check(ioctl(spi_, SPI_IOC_WR_MODE, &mode) >= 0, "SPI mode");
            check(ioctl(spi_, SPI_IOC_WR_BITS_PER_WORD, &bits) >= 0, "SPI bits");
            check(ioctl(spi_, SPI_IOC_WR_MAX_SPEED_HZ, &speed) >= 0, "SPI speed");
            chip_ = open(chipPath.c_str(), O_RDONLY | O_CLOEXEC);
            check(chip_ >= 0, "open LCD GPIO");
            dc_ = outputLine(dcLine, false, "GC9A01 DC");
            if (resetLine >= 0) {
                if (static_cast<unsigned>(resetLine) == dcLine)
                    throw std::invalid_argument("LCD reset and DC lines must differ");
                reset_ = outputLine(static_cast<unsigned>(resetLine), true, "GC9A01 RST");
                delay(20);
                pinValue(reset_, false);
                delay(20);
                pinValue(reset_, true);
                delay(150);
            } else {
                // A module without a connected reset pin uses the controller's
                // software reset. This is a wiring choice, not a simulator mode.
                command(0x01);
                delay(150);
            }
            // Always send the full controller initialization, on every device.
            if (gar_gc9a01_initialize(this, sendCommand, waitMilliseconds) != 0)
                throw std::runtime_error("GC9A01 initialization failed");
        } catch (...) {
            closeDevices();
            throw;
        }
    }

    ~Gc9a01Linux() { closeDevices(); }
    Gc9a01Linux(const Gc9a01Linux&) = delete;
    Gc9a01Linux& operator=(const Gc9a01Linux&) = delete;

    void frame(const uint16_t* pixels, size_t count) {
        if (!pixels || count != 240 * 240)
            throw std::invalid_argument("GC9A01 frame must contain 240x240 RGB565 pixels");
        const uint8_t window[4] = {0, 0, 0, 239};
        command(0x2a, window, sizeof(window));
        command(0x2b, window, sizeof(window));
        command(0x2c);
        pinValue(dc_, true);
        std::array<uint8_t, 240 * 240 * 2> bytes;
        for (size_t i = 0; i < count; ++i) {
            bytes[2 * i] = pixels[i] >> 8;
            bytes[2 * i + 1] = pixels[i] & 255;
        }
        transfer(bytes.data(), bytes.size());
    }

private:
    int spi_ = -1, chip_ = -1, dc_ = -1, reset_ = -1;

    static void check(bool ok, const char* operation) {
        if (!ok) throw std::runtime_error(std::string(operation) + ": " + strerror(errno));
    }
    void closeDevices() noexcept {
        for (int fd : {reset_, dc_, chip_, spi_}) if (fd >= 0) close(fd);
        reset_ = dc_ = chip_ = spi_ = -1;
    }
    int outputLine(unsigned line, bool high, const char* name) {
        gpio_v2_line_request request{};
        request.offsets[0] = line;
        request.num_lines = 1;
        request.config.flags = GPIO_V2_LINE_FLAG_OUTPUT;
        request.config.num_attrs = 1;
        request.config.attrs[0].attr.id = GPIO_V2_LINE_ATTR_ID_OUTPUT_VALUES;
        request.config.attrs[0].attr.values = high ? 1 : 0;
        request.config.attrs[0].mask = 1;
        std::strncpy(request.consumer, name, sizeof(request.consumer) - 1);
        check(ioctl(chip_, GPIO_V2_GET_LINE_IOCTL, &request) >= 0, "request LCD GPIO line");
        return request.fd;
    }
    static void pinValue(int fd, bool high) {
        gpio_v2_line_values values{};
        values.mask = 1;
        values.bits = high ? 1 : 0;
        check(ioctl(fd, GPIO_V2_LINE_SET_VALUES_IOCTL, &values) >= 0, "set LCD GPIO");
    }
    static void delay(unsigned milliseconds) {
        timespec remaining{static_cast<time_t>(milliseconds / 1000),
                           static_cast<long>(milliseconds % 1000) * 1000000L};
        while (nanosleep(&remaining, &remaining) < 0) {
            if (errno != EINTR) check(false, "LCD delay");
        }
    }
    void transfer(const uint8_t* bytes, size_t length) {
        while (length) {
            const size_t chunk = std::min(length, static_cast<size_t>(4096));
            const ssize_t result = write(spi_, bytes, chunk);
            if (result < 0 && errno == EINTR) continue;
            if (result == 0) throw std::runtime_error("LCD SPI write made no progress");
            check(result > 0, "write LCD SPI");
            bytes += result;
            length -= static_cast<size_t>(result);
        }
    }
    void command(uint8_t cmd, const uint8_t* data = nullptr, size_t length = 0) {
        pinValue(dc_, false);
        transfer(&cmd, 1);
        if (length) {
            pinValue(dc_, true);
            transfer(data, length);
        }
    }
    static int sendCommand(void* self, uint8_t cmd, const uint8_t* bytes, size_t length) {
        static_cast<Gc9a01Linux*>(self)->command(cmd, bytes, length);
        return 0;
    }
    static void waitMilliseconds(void*, unsigned milliseconds) { delay(milliseconds); }
};
} // namespace gar
