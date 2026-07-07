#!/usr/bin/env bash
set -euo pipefail

# Configure host-side USB network interface for Luckfox direct link.
# Defaults:
#   iface: usb0
#   host addr: 10.42.0.2/24

iface="${1:-${USB_HOST_IFACE:-usb0}}"
addr="${USB_HOST_ADDR:-10.42.0.2/24}"

echo "[usb-host] iface=$iface addr=$addr"

if ! ip link show "$iface" >/dev/null 2>&1; then
  echo "[usb-host] interface not found: $iface"
  echo "[usb-host] pass interface as first arg or set USB_HOST_IFACE"
  exit 1
fi

sudo ip link set "$iface" up
if ! ip -4 addr show dev "$iface" | grep -q "${addr%/*}"; then
  sudo ip addr add "$addr" dev "$iface"
fi

echo "[usb-host] done"
echo "[usb-host] test: ping -c 3 10.42.0.1"
