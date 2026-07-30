# Persistent USB Network + SSH (Buildroot)

This guide provides BusyBox init script examples for Luckfox RV1106 images.

Use these files:

- `initd/S40usbnet`: bring up usb0 with static IP.
- `initd/S50sshd`: start Dropbear or OpenSSH automatically.

## 1) Copy scripts to target

Run from your host:

scp targets/luckfox-rv1106/initd/S40usbnet root@10.42.0.1:/etc/init.d/S40usbnet
scp targets/luckfox-rv1106/initd/S50sshd root@10.42.0.1:/etc/init.d/S50sshd
ssh root@10.42.0.1 'chmod +x /etc/init.d/S40usbnet /etc/init.d/S50sshd'

If your USB IP is different, replace `10.42.0.1`.

## 2) Tune interface name and IP

Edit `/etc/init.d/S40usbnet` on target as needed:

- `USB_IFACE` default: `usb0`
- `USB_ADDR` default: `10.42.0.1/24`

For host side, keep a matching peer IP (example: `10.42.0.2/24`).

Host helper script:

targets/luckfox-rv1106/scripts/host_usbnet_up.sh usb0

## 3) Verify service start

Reboot target, then check from serial shell:

ip -br addr show
ps | grep -E "dropbear|sshd" | grep -v grep

Check from host:

ping -c 3 10.42.0.1
ssh root@10.42.0.1

## 4) Optional hardening

- Add public key to `/root/.ssh/authorized_keys`.
- Disable password login if your image policy allows it.
- Restrict root login per your security policy.

## Notes

- Some images have only Dropbear, some have OpenSSH, and some have both.
- Script order matters: network script uses `S40`, SSH uses `S50`.
- If your image already has vendor init scripts for USB, merge carefully to avoid conflicts.
