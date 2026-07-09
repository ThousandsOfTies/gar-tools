# Luckfox First Boot (No Ethernet)

This guide is for boards without RJ45 Ethernet.
Primary path:

1. Serial console for guaranteed first login.
2. USB gadget network for day-to-day SSH deploy.

## 1) Pre-flash checklist (host side)

Confirm image side settings before first boot.

- SSH server is enabled at boot.
- USB gadget network (ECM/RNDIS) is enabled at boot.
- Root login policy is known (password or public key).
- A static USB IP plan is decided (example: device 10.42.0.1, host 10.42.0.2).
- UART pins are accessible with USB-UART adapter as fallback.

Recommended host packages (Ubuntu/WSL):

sudo apt update
sudo apt install -y screen minicom openssh-client rsync

## 2) First login over serial

Find serial device:

ls -l /dev/ttyUSB* /dev/ttyACM* 2>/dev/null

Open console (115200 8N1 is common default):

screen /dev/ttyUSB0 115200

If boot logs do not appear, check wiring and baudrate.

## 3) Validate USB gadget networking on device

Run on Luckfox serial shell:

ip -br link
ip -br addr
ps | grep -E "sshd|dropbear" | grep -v grep

If USB network interface exists but no address, assign one (temporary):

ip addr add 10.42.0.1/24 dev usb0
ip link set usb0 up

Start SSH server if needed (command depends on image):

service ssh start || /etc/init.d/sshd start || /etc/init.d/dropbear start

## 4) Connect from host over USB network

On host, set peer IP on USB NIC if DHCP is not used:

sudo ip addr add 10.42.0.2/24 dev usb0
sudo ip link set usb0 up

Or use helper script (host side defaults to `.2`):

targets/luckfox-rv1106/scripts/host_usbnet_up.sh usb0

Test reachability:

ping -c 3 10.42.0.1

Test SSH:

ssh root@10.42.0.1

## 5) Deploy binary with existing GAR script

From this repository:

export LUCKFOX_HOST=root@10.42.0.1
export LUCKFOX_DEPLOY_DIR=/opt/gar/bin
cd targets/luckfox-rv1106/app-template
make deploy

Or call deploy directly:

targets/luckfox-rv1106/scripts/deploy_ssh.sh targets/luckfox-rv1106/app-template/build/gar_luckfox_streamer

## 6) Make it persistent (important)

Persist these in your Buildroot image or board init scripts:

- USB gadget mode on boot.
- usb0 static IP or DHCP client/server policy.
- SSH server autostart.
- Authorized keys for passwordless deploy.

See `docs/01_PERSISTENT_USB_SSH.md` and `initd/` for copy-ready examples.

## 7) Recovery path when SSH breaks

If USB SSH stops working:

1. Re-enter via serial console.
2. Fix network and SSH service.
3. Retry SSH over USB.

Keep serial access available until your image is stable.

## Notes

- Interface name may be `usb0`, `enx...`, or `eth1` depending on gadget and host.
- Some USB-C cables are power-only and cannot carry data.
- If your board exposes Ethernet later, the same deploy script still works by changing `LUCKFOX_HOST`.
