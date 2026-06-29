#define _GNU_SOURCE

#include <dlfcn.h>
#include <fcntl.h>
#include <limits.h>
#include <stdlib.h>
#include <stdarg.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

typedef int (*open_fn_t)(const char *, int, ...);
typedef int (*openat_fn_t)(int, const char *, int, ...);

static open_fn_t real_open_fn;
static openat_fn_t real_openat_fn;

static const char *dev_root(void) {
    const char *v = getenv("GAR_DEV_ROOT");
    if (v && v[0]) {
        return v;
    }
    return "/tmp/gar-dev";
}

static bool should_redirect(const char *path) {
    return path && (
        strcmp(path, "/dev/video0") == 0 ||
        strcmp(path, "/dev/fb0") == 0 ||
        strcmp(path, "/dev/spidev0.0") == 0 ||
        strcmp(path, "/dev/i2c-3") == 0 ||
        strcmp(path, "/dev/gpiochip0") == 0
    );
}

static const char *map_path(const char *path, char *out, size_t out_size) {
    if (!should_redirect(path)) {
        return path;
    }

    const char *root = dev_root();
    int n = snprintf(out, out_size, "%s%s", root, path);
    if (n <= 0 || (size_t)n >= out_size) {
        return path;
    }

    if (getenv("GAR_DEVREDIR_DEBUG")) {
        fprintf(stderr, "[gar-devredir] %s -> %s\n", path, out);
    }
    return out;
}

static void ensure_resolved(void) {
    if (!real_open_fn) {
        real_open_fn = (open_fn_t)dlsym(RTLD_NEXT, "open");
    }
    if (!real_openat_fn) {
        real_openat_fn = (openat_fn_t)dlsym(RTLD_NEXT, "openat");
    }
}

int open(const char *pathname, int flags, ...) {
    mode_t mode = 0;
    if (flags & O_CREAT) {
        va_list ap;
        va_start(ap, flags);
        mode = (mode_t)va_arg(ap, int);
        va_end(ap);
    }

    ensure_resolved();
    char mapped[PATH_MAX];
    const char *final_path = map_path(pathname, mapped, sizeof(mapped));

    if (flags & O_CREAT) {
        return real_open_fn(final_path, flags, mode);
    }
    return real_open_fn(final_path, flags);
}

int openat(int dirfd, const char *pathname, int flags, ...) {
    mode_t mode = 0;
    if (flags & O_CREAT) {
        va_list ap;
        va_start(ap, flags);
        mode = (mode_t)va_arg(ap, int);
        va_end(ap);
    }

    ensure_resolved();
    char mapped[PATH_MAX];
    const char *final_path = map_path(pathname, mapped, sizeof(mapped));

    if (flags & O_CREAT) {
        return real_openat_fn(dirfd, final_path, flags, mode);
    }
    return real_openat_fn(dirfd, final_path, flags);
}
