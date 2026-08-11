#!/bin/sh
# One-time preparation for RK3506 Buildroot targets.
set -eu

fail() {
    echo "gar target prepare: $*" >&2
    exit 2
}

[ "$#" -eq 5 ] || fail "usage: prepare.sh SSH_USER INSTALLER_SOURCE LAUNCHER_SOURCE LIFECYCLE_SOURCE IDENTITY_SOURCE"
ssh_user=$1
installer_source=$2
launcher_source=$3
lifecycle_source=$4
identity_source=$5

case "$ssh_user" in
    ""|*[!A-Za-z0-9_-]*) fail "invalid SSH user" ;;
esac
[ -f "$installer_source" ] || fail "installer payload is missing"
[ -f "$launcher_source" ] || fail "BusyBox launcher template is missing"
[ -f "$lifecycle_source" ] || fail "lifecycle helper payload is missing"
[ -f "$identity_source" ] || fail "recipe identity payload is missing"

arch=$(uname -m)
case "$arch" in
    armv7l|armv8l) ;;
    *) fail "this recipe requires a 32-bit ARM RK3506 target (detected architecture: $arch)" ;;
esac

compatible=$(tr '\000' ' ' </proc/device-tree/compatible 2>/dev/null || true)
case "$compatible" in
    *rk3506*) ;;
    *) fail "this recipe supports RK3506 only (compatible: ${compatible:-unknown})" ;;
esac

[ -r /etc/os-release ] || fail "/etc/os-release is missing"
# shellcheck disable=SC1091
. /etc/os-release
case "${ID:-}" in
    buildroot) ;;
    *) fail "this recipe supports Buildroot only (detected: ${ID:-unknown})" ;;
esac

[ "$(id -u)" -eq 0 ] || fail "RK3506 Buildroot preparation requires the root SSH account"

mkdir -p /opt/gar/apps /etc/gar /usr/local/lib/gar /var/log/gar \
    /var/lib/gar-target/state
cp "$installer_source" /usr/local/lib/gar/gar-target-install
chmod 0755 /usr/local/lib/gar/gar-target-install
cp "$lifecycle_source" /usr/local/lib/gar/gar-target-lifecycle
chmod 0755 /usr/local/lib/gar/gar-target-lifecycle
cp "$launcher_source" /usr/local/lib/gar/gar-app-init
chmod 0644 /usr/local/lib/gar/gar-app-init
identity_staging=/etc/gar/.recipe-version.gar-new.$$
cp "$identity_source" "$identity_staging"
chown 0:0 "$identity_staging"
chmod 0644 "$identity_staging"
mv "$identity_staging" /etc/gar/recipe-version
target_id_staging=/etc/gar/.target-id.gar-new.$$
printf '%s\n' luckfox-rk3506 >"$target_id_staging"
chown 0:0 "$target_id_staging"
chmod 0644 "$target_id_staging"
mv "$target_id_staging" /etc/gar/target-id

echo "GAR target preparation completed for RK3506 (${PRETTY_NAME:-Buildroot}, $arch)."
