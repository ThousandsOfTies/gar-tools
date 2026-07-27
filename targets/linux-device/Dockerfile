# GAR simulation host as a local container.
#
# 注意: container は host kernel を共有します。GPIO(gpio-sim) を使うには
# host kernel が Linux 5.17 以降で CONFIG_GPIO_SIM を持っている必要があります。
# WSL2 および Ubuntu 24.04 以降が想定環境です。
# 導入後の確認: gar sim gpio check --json
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
ENV container=docker

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        systemd \
        systemd-sysv \
        dbus \
        sudo \
        kmod \
        ca-certificates \
        fuse3 \
        libfuse3-3 \
        gpiod \
        libgpiod2 \
        i2c-tools \
        python3 \
        python3-aiohttp \
        python3-websockets \
    && rm -rf /var/lib/apt/lists/*

# container 内で必ず失敗する unit を無効化する。
RUN systemctl mask \
        systemd-udevd.service \
        systemd-udev-trigger.service \
        systemd-modules-load.service \
        systemd-firstboot.service \
        sys-kernel-debug.mount \
        sys-kernel-tracing.mount

# gar sim runtime deploy の配置先。
RUN mkdir -p /etc/gar/hardware /usr/local/lib/gar /run/gar

STOPSIGNAL SIGRTMIN+3

CMD ["/sbin/init"]
