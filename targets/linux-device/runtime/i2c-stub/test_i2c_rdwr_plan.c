#include "i2c_rdwr_plan.h"

#include <assert.h>
#include <stdio.h>

static size_t fixed_input_bytes(uint32_t nmsgs) {
    return sizeof(struct i2c_rdwr_ioctl_data)
         + nmsgs * sizeof(struct i2c_msg);
}

static void test_combined_write_read_plan(void) {
    uint8_t register_address = 0x14;
    uint8_t read_buffer[512];
    struct i2c_msg msgs[] = {
        { .addr = 0x29, .flags = 0,        .len = 1,   .buf = &register_address },
        { .addr = 0x29, .flags = I2C_M_RD, .len = 512, .buf = read_buffer },
    };
    i2c_rdwr_plan_t plan;

    assert(i2c_rdwr_make_plan(msgs, 2, &plan) == 0);
    assert(plan.input_bytes == fixed_input_bytes(2) + 1);
    assert(plan.output_bytes == sizeof(read_buffer));
    assert(plan.input_iov_count == 3);
    assert(plan.output_iov_count == 1);
}

static void test_multiple_buffers_are_counted_separately(void) {
    uint8_t write_a[2] = { 0 };
    uint8_t write_b[3] = { 0 };
    uint8_t read_a[4];
    uint8_t read_b[5];
    struct i2c_msg msgs[] = {
        { .addr = 0x29, .flags = 0,        .len = 2, .buf = write_a },
        { .addr = 0x29, .flags = I2C_M_RD, .len = 4, .buf = read_a },
        { .addr = 0x3c, .flags = 0,        .len = 3, .buf = write_b },
        { .addr = 0x29, .flags = I2C_M_RD, .len = 5, .buf = read_b },
    };
    i2c_rdwr_plan_t plan;

    assert(i2c_rdwr_make_plan(msgs, 4, &plan) == 0);
    assert(plan.input_bytes == fixed_input_bytes(4) + 5);
    assert(plan.output_bytes == 9);
    assert(plan.input_iov_count == 4);
    assert(plan.output_iov_count == 2);
}

static void test_linux_bounds_and_unsupported_flags(void) {
    uint8_t buffer[GAR_I2C_RDWR_MESSAGE_BYTES_MAX + 1];
    struct i2c_msg msg = {
        .addr = 0x29,
        .flags = 0,
        .len = GAR_I2C_RDWR_MESSAGE_BYTES_MAX,
        .buf = buffer,
    };
    i2c_rdwr_plan_t plan;

    assert(i2c_rdwr_make_plan(&msg, 1, &plan) == 0);

    msg.len = GAR_I2C_RDWR_MESSAGE_BYTES_MAX + 1;
    assert(i2c_rdwr_make_plan(&msg, 1, &plan) == EINVAL);

    msg.len = 1;
    msg.buf = NULL;
    assert(i2c_rdwr_make_plan(&msg, 1, &plan) == EFAULT);

    msg.buf = buffer;
    msg.flags = I2C_M_RECV_LEN | I2C_M_RD;
    assert(i2c_rdwr_make_plan(&msg, 1, &plan) == EOPNOTSUPP);

    msg.flags = 0;
    msg.addr = 0x80;
    assert(i2c_rdwr_make_plan(&msg, 1, &plan) == EINVAL);
}

static void test_message_count_bounds(void) {
    uint8_t byte = 0;
    struct i2c_msg msgs[I2C_RDWR_IOCTL_MAX_MSGS + 1];
    i2c_rdwr_plan_t plan;

    for (size_t i = 0; i < (size_t)I2C_RDWR_IOCTL_MAX_MSGS + 1; ++i) {
        msgs[i] = (struct i2c_msg) {
            .addr = 0x29,
            .flags = 0,
            .len = 1,
            .buf = &byte,
        };
    }

    assert(i2c_rdwr_make_plan(msgs, 0, &plan) == EINVAL);
    assert(i2c_rdwr_make_plan(msgs, I2C_RDWR_IOCTL_MAX_MSGS, &plan) == 0);
    assert(i2c_rdwr_make_plan(msgs, I2C_RDWR_IOCTL_MAX_MSGS + 1, &plan)
           == EINVAL);
}

int main(void) {
    test_combined_write_read_plan();
    test_multiple_buffers_are_counted_separately();
    test_linux_bounds_and_unsupported_flags();
    test_message_count_bounds();
    puts("i2c_rdwr_plan tests passed");
    return 0;
}
