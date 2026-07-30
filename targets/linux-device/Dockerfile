# GAR simulation host as a local container.
#
# 注意: container は host kernel を共有します。GPIO(gpio-sim) を使うには
# host kernel が Linux 5.17 以降で CONFIG_GPIO_SIM を持っている必要があります。
# WSL2 および Ubuntu 24.04 以降が想定環境です。
# 導入後の確認: gar sim gpio check --json
# Keep the Noble release name readable while pinning the multi-platform image
# index so amd64 and arm64 builds resolve to the same reviewed release.
# Review updates with: docker buildx imagetools inspect ubuntu:24.04
FROM ubuntu:24.04@sha256:4fbb8e6a8395de5a7550b33509421a2bafbc0aab6c06ba2cef9ebffbc7092d90

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
        python3-venv \
    && rm -rf /var/lib/apt/lists/*

COPY runtime/web-bridge/requirements.txt /tmp/gar-web-bridge-requirements.txt

RUN python3 -m venv /usr/local/lib/gar/venv \
    && /usr/local/lib/gar/venv/bin/pip install --no-cache-dir \
        -r /tmp/gar-web-bridge-requirements.txt \
    && rm /tmp/gar-web-bridge-requirements.txt

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
