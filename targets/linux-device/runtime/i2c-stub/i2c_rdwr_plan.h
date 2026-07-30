#ifndef GAR_I2C_RDWR_PLAN_H
#define GAR_I2C_RDWR_PLAN_H

#include <errno.h>
#include <linux/i2c.h>
#include <linux/i2c-dev.h>
#include <stddef.h>
#include <stdint.h>

/* Match the limit used by Linux's i2c-dev implementation. */
#define GAR_I2C_RDWR_MESSAGE_BYTES_MAX 8192U

/*
 * CUSE flattens the requested input and output iovecs into two buffers.
 * This plan records the sizes and vector counts needed for one retry.
 */
typedef struct {
    size_t input_bytes;
    size_t output_bytes;
    size_t input_iov_count;
    size_t output_iov_count;
} i2c_rdwr_plan_t;

static inline int i2c_rdwr_make_plan(const struct i2c_msg *msgs,
                                     uint32_t nmsgs,
                                     i2c_rdwr_plan_t *plan) {
    if (!msgs || !plan || nmsgs == 0 || nmsgs > I2C_RDWR_IOCTL_MAX_MSGS) {
        return EINVAL;
    }

    plan->input_bytes = sizeof(struct i2c_rdwr_ioctl_data)
                      + nmsgs * sizeof(struct i2c_msg);
    plan->output_bytes = 0;
    plan->input_iov_count = 2;  /* ioctl header and message descriptors */
    plan->output_iov_count = 0;

    for (uint32_t i = 0; i < nmsgs; ++i) {
        const struct i2c_msg *msg = &msgs[i];

        if (msg->addr > 0x7f) {
            return EINVAL;
        }
        if (msg->flags & ~I2C_M_RD) {
            return EOPNOTSUPP;
        }
        if (msg->len > GAR_I2C_RDWR_MESSAGE_BYTES_MAX) {
            return EINVAL;
        }
        if (msg->len > 0 && !msg->buf) {
            return EFAULT;
        }

        if (msg->flags & I2C_M_RD) {
            plan->output_bytes += msg->len;
            if (msg->len > 0) {
                ++plan->output_iov_count;
            }
        } else {
            plan->input_bytes += msg->len;
            if (msg->len > 0) {
                ++plan->input_iov_count;
            }
        }
    }

    return 0;
}

#endif
