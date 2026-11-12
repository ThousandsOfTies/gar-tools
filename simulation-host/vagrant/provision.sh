#!/bin/sh
# Provider prerequisites only: never compile or deploy Product/App code here.
set -eu
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y ca-certificates python3 python3-aiohttp python3-gi python3-periphery \
  python3-spidev python3-websockets gpiod kmod libfuse3-3 fuse3 nodejs \
  gir1.2-gstreamer-1.0 gstreamer1.0-tools gstreamer1.0-plugins-base \
  gstreamer1.0-plugins-good
modprobe gpio-sim
modprobe cuse
mountpoint -q /sys/kernel/config || mount -t configfs configfs /sys/kernel/config
install -d -m 0755 /etc/modules-load.d /run/gar
printf '%s\n' gpio-sim cuse > /etc/modules-load.d/gar-simulation.conf
cat > /etc/systemd/system/gar-sim-host-devices.service <<'EOF'
[Unit]
Description=GAR virtual device prerequisites
Requires=sys-kernel-config.mount
After=sys-kernel-config.mount systemd-modules-load.service
[Service]
Type=oneshot
ExecStart=/sbin/modprobe gpio-sim
ExecStart=/sbin/modprobe cuse
ExecStart=/usr/bin/test -d /sys/kernel/config/gpio-sim
ExecStart=/usr/bin/test -c /dev/cuse
RemainAfterExit=yes
[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now gar-sim-host-devices.service
test -d /sys/kernel/config/gpio-sim
test -c /dev/cuse
install -d -m 0755 /var/lib/gar
printf '%s\n' 'gar-vagrant-2' > /var/lib/gar/simulation-host-ready
