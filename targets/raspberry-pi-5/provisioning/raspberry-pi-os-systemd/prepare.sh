#!/bin/sh
# One-time preparation for Raspberry Pi OS targets.
set -eu

fail() {
    echo "gar target prepare: $*" >&2
    exit 2
}

[ "$#" -eq 5 ] || fail "usage: prepare.sh SSH_USER INSTALLER_SOURCE SERVICE_SOURCE LIFECYCLE_SOURCE IDENTITY_SOURCE"
ssh_user=$1
installer_source=$2
service_source=$3
lifecycle_source=$4
identity_source=$5

case "$ssh_user" in
    ""|*[!A-Za-z0-9_-]*) fail "invalid SSH user" ;;
esac
[ -f "$installer_source" ] || fail "installer payload is missing"
[ -f "$service_source" ] || fail "systemd service template is missing"
[ -f "$lifecycle_source" ] || fail "lifecycle helper payload is missing"
[ -f "$identity_source" ] || fail "recipe identity payload is missing"

model=$(tr -d '\000' </proc/device-tree/model 2>/dev/null || true)
case "$model" in
    *"Raspberry Pi 5"*) ;;
    *) fail "this recipe supports Raspberry Pi 5 only (detected: ${model:-unknown})" ;;
esac

[ -r /etc/os-release ] || fail "/etc/os-release is missing"
# shellcheck disable=SC1091
. /etc/os-release
case "${ID:-}" in
    debian|raspbian) ;;
    *) fail "this recipe supports Raspberry Pi OS/Debian only (detected: ${ID:-unknown})" ;;
esac

command -v systemctl >/dev/null || fail "systemd is required"
command -v sudo >/dev/null || fail "sudo is required"
command -v runuser >/dev/null || fail "runuser is required"

runtime_packages="python3 python3-gi python3-spidev python3-periphery gir1.2-gstreamer-1.0 gir1.2-gst-plugins-base-1.0 gstreamer1.0-tools gstreamer1.0-plugins-good gstreamer1.0-plugins-bad v4l-utils"
missing_packages=""
for package in $runtime_packages; do
    if ! dpkg-query -W -f='${Status}' "$package" 2>/dev/null | grep -q 'ok installed'; then
        missing_packages="$missing_packages $package"
    fi
done
if [ -n "$missing_packages" ]; then
    sudo /usr/bin/apt-get update
    # shellcheck disable=SC2086
    sudo /usr/bin/env DEBIAN_FRONTEND=noninteractive /usr/bin/apt-get install -y $missing_packages
fi

if ! id -u gar >/dev/null 2>&1; then
    sudo /usr/sbin/useradd --system --create-home --home-dir /var/lib/gar \
        --shell /usr/sbin/nologin gar
fi
for group in gpio spi video i2c; do
    if getent group "$group" >/dev/null; then
        sudo /usr/sbin/usermod -aG "$group" gar
    fi
done

sudo /usr/bin/install -d -o root -g root -m 0755 \
    /opt/gar/apps /etc/gar /etc/gar/system /var/lib/gar-target /var/lib/gar-target/state

sudo /usr/bin/install -D -o root -g root -m 0755 "$installer_source" \
    /usr/local/lib/gar/gar-target-install
sudo /usr/bin/install -D -o root -g root -m 0755 "$lifecycle_source" \
    /usr/local/lib/gar/gar-target-lifecycle
sudo /usr/bin/install -D -o root -g root -m 0644 "$service_source" \
    /etc/systemd/system/gar-app@.service
identity_staging=/etc/gar/.recipe-version.gar-new.$$
sudo /usr/bin/install -o root -g root -m 0644 "$identity_source" "$identity_staging"
sudo /bin/mv "$identity_staging" /etc/gar/recipe-version
target_id_staging=/etc/gar/.target-id.gar-new.$$
printf '%s\n' raspberry-pi-5 | sudo /usr/bin/tee "$target_id_staging" >/dev/null
sudo /usr/bin/chown root:root "$target_id_staging"
sudo /usr/bin/chmod 0644 "$target_id_staging"
sudo /bin/mv "$target_id_staging" /etc/gar/target-id
sudoers_line="$ssh_user ALL=(root) NOPASSWD: /usr/local/lib/gar/gar-target-install, /usr/local/lib/gar/gar-target-lifecycle"
printf '%s\n' "$sudoers_line" | sudo /usr/bin/tee /etc/sudoers.d/90-gar-target >/dev/null
sudo /usr/bin/chmod 0440 /etc/sudoers.d/90-gar-target
sudo /usr/sbin/visudo -cf /etc/sudoers.d/90-gar-target
sudo /usr/bin/systemctl daemon-reload

# Migrate the unrestricted rule created by the earlier GAR SSH deploy spike.
# This filename belongs to GAR; unrelated administrator sudoers files are
# deliberately left untouched.
if [ -f /etc/sudoers.d/90-gar-deploy ]; then
    sudo /bin/rm -f /etc/sudoers.d/90-gar-deploy
fi

echo "GAR target preparation completed for $model (${PRETTY_NAME:-$ID})."
