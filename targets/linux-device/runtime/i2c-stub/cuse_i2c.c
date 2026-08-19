/*
 * cuse_i2c.c — CUSE-based I2C stub
 *
 * Creates /dev/i2c-1 (or the name given by --devname) as a userspace character
 * device.  Implements the minimal Linux i2c-dev operations needed by the
 * simulated devices:
 *
 *   I2C_SLAVE      – select the slave address for subsequent transfers
 *   I2C_RDWR       – combined read/write transaction (struct i2c_rdwr_ioctl_data)
 *   I2C_FUNCS      – reports plain I2C transfer support only
 *
 * SMBus transactions, ten-bit addresses, and protocol-mangling flags are not
 * implemented or advertised.
 *
 * Simulated devices (extend the sim_devices table):
 *   0x29  VL53L0X  ToF distance sensor
 */

#define FUSE_USE_VERSION 31

#include <fuse3/cuse_lowlevel.h>
#include <fuse3/fuse_opt.h>

#include <linux/i2c.h>
#include <linux/i2c-dev.h>

#include <errno.h>
#include <fcntl.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <stdint.h>

#include "i2c_rdwr_plan.h"
#include "pca9685_sim.h"
#include "vl53l0x_sim.h"
#include "ssd1306_sim.h"

/* ------------------------------------------------------------------ */
/* Per-open-file state                                                  */
/* ------------------------------------------------------------------ */

typedef struct {
    uint16_t slave_addr;   /* last I2C_SLAVE address */
    uint8_t  reg_ptr;      /* last written register pointer */
    int      reg_ptr_set;
} i2c_session_t;

/* ------------------------------------------------------------------ */
/* Simulated device dispatch                                            */
/* ------------------------------------------------------------------ */

typedef struct {
    uint16_t addr;
    uint8_t  (*read_reg)(uint8_t reg);
    void     (*write_reg)(uint8_t reg, uint8_t val);
    void     (*write_buf)(const uint8_t *buf, size_t len);  /* transaction-level (overrides write_reg) */
} sim_device_t;

static const sim_device_t sim_devices[] = {
    { PCA9685_SIM_ADDR, pca9685_sim_read_reg, pca9685_sim_write_reg, NULL },
    { VL53L0X_ADDR,    vl53l0x_sim_read_reg, vl53l0x_sim_write_reg, NULL },
    { SSD1306_SIM_ADDR, NULL,                NULL,                  ssd1306_sim_write },
    { 0, NULL, NULL, NULL }
};

static const sim_device_t *find_device(uint16_t addr) {
    for (int i = 0; sim_devices[i].addr != 0; i++) {
        if (sim_devices[i].addr == addr) return &sim_devices[i];
    }
    return NULL;
}

/* ------------------------------------------------------------------ */
/* CUSE open / release                                                  */
/* ------------------------------------------------------------------ */

static void i2c_open(fuse_req_t req, struct fuse_file_info *fi) {
    i2c_session_t *s = calloc(1, sizeof(*s));
    if (!s) { fuse_reply_err(req, ENOMEM); return; }
    fi->fh = (uint64_t)(uintptr_t)s;
    fuse_reply_open(req, fi);
}

static void i2c_release(fuse_req_t req, struct fuse_file_info *fi) {
    free((void *)(uintptr_t)fi->fh);
    fuse_reply_err(req, 0);
}

/* ------------------------------------------------------------------ */
/* read / write (register-pointer style)                               */
/* ------------------------------------------------------------------ */

static void i2c_read(fuse_req_t req, size_t size, off_t off,
                     struct fuse_file_info *fi) {
    (void)off;
    i2c_session_t *s = (i2c_session_t *)(uintptr_t)fi->fh;
    const sim_device_t *dev = find_device(s->slave_addr);

    if (!dev || !dev->read_reg) { fuse_reply_err(req, ENXIO); return; }

    uint8_t *buf = malloc(size);
    if (!buf) { fuse_reply_err(req, ENOMEM); return; }

    for (size_t i = 0; i < size; i++) {
        buf[i] = dev->read_reg((uint8_t)(s->reg_ptr + i));
    }
    fuse_reply_buf(req, (char *)buf, size);
    free(buf);
}

static void i2c_write(fuse_req_t req, const char *buf, size_t size, off_t off,
                      struct fuse_file_info *fi) {
    (void)off;
    i2c_session_t *s = (i2c_session_t *)(uintptr_t)fi->fh;
    const sim_device_t *dev = find_device(s->slave_addr);

    if (!dev || size == 0) { fuse_reply_err(req, ENXIO); return; }

    if (dev->write_buf) {
        /* Transaction-level write (e.g. SSD1306) */
        dev->write_buf((const uint8_t *)buf, size);
    } else if (dev->write_reg) {
        /* Register-pointer style: first byte = register address */
        s->reg_ptr = (uint8_t)buf[0];
        s->reg_ptr_set = 1;
        for (size_t i = 1; i < size; i++) {
            dev->write_reg((uint8_t)(s->reg_ptr + (i - 1)), (uint8_t)buf[i]);
        }
    }
    fuse_reply_write(req, size);
}

/* ------------------------------------------------------------------ */
/* ioctl                                                               */
/* ------------------------------------------------------------------ */

static void request_rdwr_header(fuse_req_t req, const void *arg) {
    struct iovec header_iov = {
        .iov_base = (void *)arg,
        .iov_len = sizeof(struct i2c_rdwr_ioctl_data),
    };
    fuse_reply_ioctl_retry(req, &header_iov, 1, NULL, 0);
}

static void request_rdwr_descriptors(
        fuse_req_t req, const void *arg,
        const struct i2c_rdwr_ioctl_data *header) {
    struct iovec input_iov[2] = {
        {
            .iov_base = (void *)arg,
            .iov_len = sizeof(*header),
        },
        {
            .iov_base = header->msgs,
            .iov_len = header->nmsgs * sizeof(struct i2c_msg),
        },
    };
    fuse_reply_ioctl_retry(req, input_iov, 2, NULL, 0);
}

static void request_rdwr_buffers(
        fuse_req_t req, const void *arg,
        const struct i2c_rdwr_ioctl_data *header,
        const struct i2c_msg *msgs) {
    struct iovec input_iov[2 + I2C_RDWR_IOCTL_MAX_MSGS];
    struct iovec output_iov[I2C_RDWR_IOCTL_MAX_MSGS];
    size_t input_count = 0;
    size_t output_count = 0;

    input_iov[input_count++] = (struct iovec) {
        .iov_base = (void *)arg,
        .iov_len = sizeof(*header),
    };
    input_iov[input_count++] = (struct iovec) {
        .iov_base = header->msgs,
        .iov_len = header->nmsgs * sizeof(struct i2c_msg),
    };

    for (uint32_t i = 0; i < header->nmsgs; ++i) {
        if (msgs[i].len == 0) {
            continue;
        }

        if (msgs[i].flags & I2C_M_RD) {
            output_iov[output_count++] = (struct iovec) {
                .iov_base = msgs[i].buf,
                .iov_len = msgs[i].len,
            };
        } else {
            input_iov[input_count++] = (struct iovec) {
                .iov_base = msgs[i].buf,
                .iov_len = msgs[i].len,
            };
        }
    }

    fuse_reply_ioctl_retry(req, input_iov, input_count,
                           output_count ? output_iov : NULL, output_count);
}

static int validate_simulated_devices(const struct i2c_msg *msgs,
                                      uint32_t nmsgs) {
    for (uint32_t i = 0; i < nmsgs; ++i) {
        const sim_device_t *device = find_device(msgs[i].addr);

        if (!device) {
            return ENXIO;
        }
        if (msgs[i].len == 0) {
            continue;
        }
        if ((msgs[i].flags & I2C_M_RD) && !device->read_reg) {
            return EOPNOTSUPP;
        }
        if (!(msgs[i].flags & I2C_M_RD)
                && !device->write_buf && !device->write_reg) {
            return EOPNOTSUPP;
        }
    }
    return 0;
}

static void execute_rdwr(i2c_session_t *session,
                         const struct i2c_msg *msgs, uint32_t nmsgs,
                         const uint8_t *write_data, uint8_t *read_data) {
    size_t read_offset = 0;

    for (uint32_t i = 0; i < nmsgs; ++i) {
        const struct i2c_msg *msg = &msgs[i];
        const sim_device_t *device = find_device(msg->addr);

        session->slave_addr = msg->addr;
        if (msg->flags & I2C_M_RD) {
            for (size_t byte = 0; byte < msg->len; ++byte) {
                read_data[read_offset + byte] =
                    device->read_reg((uint8_t)(session->reg_ptr + byte));
            }
            read_offset += msg->len;
            continue;
        }

        if (msg->len > 0 && device->write_buf) {
            device->write_buf(write_data, msg->len);
        } else if (msg->len > 0 && device->write_reg) {
            session->reg_ptr = write_data[0];
            session->reg_ptr_set = 1;
            for (size_t byte = 1; byte < msg->len; ++byte) {
                device->write_reg(
                    (uint8_t)(session->reg_ptr + byte - 1), write_data[byte]);
            }
        }
        write_data += msg->len;
    }
}

static void handle_i2c_rdwr(fuse_req_t req, struct fuse_file_info *fi,
                            const void *arg, const void *in_buf,
                            size_t in_bufsz, size_t out_bufsz) {
    if (in_bufsz < sizeof(struct i2c_rdwr_ioctl_data)) {
        request_rdwr_header(req, arg);
        return;
    }

    const struct i2c_rdwr_ioctl_data *header = in_buf;
    if (!header->msgs || header->nmsgs == 0
            || header->nmsgs > I2C_RDWR_IOCTL_MAX_MSGS) {
        fuse_reply_err(req, EINVAL);
        return;
    }

    size_t descriptor_bytes = header->nmsgs * sizeof(struct i2c_msg);
    size_t fixed_input_bytes = sizeof(*header) + descriptor_bytes;
    if (in_bufsz < fixed_input_bytes) {
        request_rdwr_descriptors(req, arg, header);
        return;
    }

    const struct i2c_msg *msgs = (const struct i2c_msg *)
        ((const uint8_t *)in_buf + sizeof(*header));
    i2c_rdwr_plan_t plan;
    int error = i2c_rdwr_make_plan(msgs, header->nmsgs, &plan);
    if (error) {
        fuse_reply_err(req, error);
        return;
    }

    if (in_bufsz < plan.input_bytes || out_bufsz < plan.output_bytes) {
        request_rdwr_buffers(req, arg, header, msgs);
        return;
    }

    error = validate_simulated_devices(msgs, header->nmsgs);
    if (error) {
        fuse_reply_err(req, error);
        return;
    }

    uint8_t *read_data = plan.output_bytes ? malloc(plan.output_bytes) : NULL;
    if (plan.output_bytes && !read_data) {
        fuse_reply_err(req, ENOMEM);
        return;
    }

    i2c_session_t *session = (i2c_session_t *)(uintptr_t)fi->fh;
    const uint8_t *write_data = (const uint8_t *)in_buf + fixed_input_bytes;
    execute_rdwr(session, msgs, header->nmsgs, write_data, read_data);
    fuse_reply_ioctl(req, (int)header->nmsgs, read_data, plan.output_bytes);
    free(read_data);
}

static void i2c_ioctl(fuse_req_t req, int cmd, void *arg,
                      struct fuse_file_info *fi, unsigned flags,
                      const void *in_buf, size_t in_bufsz, size_t out_bufsz) {
    if (flags & FUSE_IOCTL_COMPAT) {
        fuse_reply_err(req, ENOSYS);
        return;
    }

    i2c_session_t *s = (i2c_session_t *)(uintptr_t)fi->fh;

    switch ((unsigned long)cmd) {

    case I2C_SLAVE:
    case I2C_SLAVE_FORCE:
        if ((uintptr_t)arg > 0x7f) {
            fuse_reply_err(req, EINVAL);
            break;
        }
        s->slave_addr = (uint16_t)(uintptr_t)arg;
        fprintf(stderr, "[cuse_i2c] I2C_SLAVE addr=0x%02x\n", s->slave_addr);
        fuse_reply_ioctl(req, 0, NULL, 0);
        break;

    case I2C_RDWR:
        handle_i2c_rdwr(req, fi, arg, in_buf, in_bufsz, out_bufsz);
        break;

    case I2C_FUNCS: {
        const unsigned long funcs = I2C_FUNC_I2C;
        if (out_bufsz < sizeof(funcs)) {
            struct iovec out_iov = { arg, sizeof(funcs) };
            fuse_reply_ioctl_retry(req, NULL, 0, &out_iov, 1);
        } else {
            fuse_reply_ioctl(req, 0, &funcs, sizeof(funcs));
        }
        break;
    }

    case I2C_SMBUS:
        fuse_reply_err(req, EOPNOTSUPP);
        break;

    default:
        fprintf(stderr, "[cuse_i2c] unknown ioctl 0x%x\n", cmd);
        fuse_reply_err(req, ENOTTY);
        break;
    }
}

/* ------------------------------------------------------------------ */
/* CUSE ops table                                                       */
/* ------------------------------------------------------------------ */

static const struct cuse_lowlevel_ops i2c_clops = {
    .open    = i2c_open,
    .release = i2c_release,
    .read    = i2c_read,
    .write   = i2c_write,
    .ioctl   = i2c_ioctl,
};

/* ------------------------------------------------------------------ */
/* main                                                                 */
/* ------------------------------------------------------------------ */

int main(int argc, char *argv[]) {
    const char *devname = "i2c-1";

    /* Parse --devname= manually to avoid fuse_opt_parse heap issues */
    char **fuse_argv = malloc((argc + 1) * sizeof(char *));
    if (!fuse_argv) return 1;
    int fuse_argc = 0;
    fuse_argv[fuse_argc++] = argv[0];
    for (int i = 1; i < argc; i++) {
        if (strncmp(argv[i], "--devname=", 10) == 0) {
            devname = argv[i] + 10;
        } else {
            fuse_argv[fuse_argc++] = argv[i];
        }
    }
    fuse_argv[fuse_argc] = NULL;

    struct fuse_args args = FUSE_ARGS_INIT(fuse_argc, fuse_argv);

    pca9685_sim_init();
    vl53l0x_sim_init();
    ssd1306_sim_init();

    char dev_name_buf[64];
    snprintf(dev_name_buf, sizeof(dev_name_buf), "DEVNAME=%s", devname);
    const char *dev_info_argv[] = { dev_name_buf };

    struct cuse_info ci = {
        .dev_major      = 0,
        .dev_minor      = 0,
        .dev_info_argc  = 1,
        .dev_info_argv  = dev_info_argv,
        .flags          = CUSE_UNRESTRICTED_IOCTL,
    };

    fprintf(stderr, "[cuse_i2c] starting /dev/%s stub\n", devname);
    int ret = cuse_lowlevel_main(args.argc, args.argv, &ci, &i2c_clops, NULL);
    free(fuse_argv);
    return ret;
}
