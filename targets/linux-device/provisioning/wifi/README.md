# Private Netplan Wi-Fi provisioning over a USB serial console

`setup.py` displays a masked Windows input form and provisions a Linux networkd
Target through its existing serial console. The Product supplies transport and
OS bindings (port, VID/PID, login user, Wi-Fi interface, managed USB profile and
an unauthenticated HTTPS reachability endpoint). There are no Product service
names, cloud credentials or application commands in this recipe.

The operator enters the Wi-Fi key and Linux login/sudo password in the form.
No saved Windows Wi-Fi key is exported. The current Windows SSID may be used as
a non-secret suggested network name. Credentials are never command arguments,
PC files, terminal history, result JSON or logs. The form clears password
widgets on submission. Console echo is disabled and acknowledged before setup
credentials are sent. Target machine-id must match the selected USB gadget's
serial number. The existing login prompt receives its password only after its
password prompt. The sudo password is sent only after its explicit prompt.

Only `configure.py` (source without secrets) is copied to a private temporary
Target directory. The process runs with explicit sudo authentication, clears
that authentication afterward, and removes temporary recipe source. Linux
retains credentials only in root-owned mode-0600 Netplan configuration and any
root-only rollback copy. They are never part of an App artifact.

The recipe requires existing Netplan, wpa_supplicant, networkctl, ip and curl.
It verifies the supplied USB profile identity, retains its fixed management
address, and removes that profile's default route and DNS ownership. Wi-Fi gets
DHCP and route metric 10. Setup checks the actual selected route and HTTPS
egress using the Wi-Fi interface, then performs one interface down/up cycle
and repeats the checks. This establishes network reconnection, not App-level
conversation or successful reboot. Reboot and actual voice checks remain
separate physical validations. Failed setup attempts restore the previous files.

The root-owned Netplan file contains credentials and stays mode 0600. The USB
`.network` file contains only management addressing and must be mode 0644 so
the systemd-network user can read it. The writer sets the exact mode with
fchmod, rather than relying on a permissive process umask.

SSH uses the existing private key and pinned host key. Linux sudo credentials
are sent only after its unique prompt; network data follows the recipe input
marker. For recovery after a management link loss, `wifi_recovery.py` first
matches the LAN server key to that same pinned Target key, then accepts an
owner-entered Linux password over SSH. It repairs the readable USB profile,
and runs the radio reconnect check over the restored USB path. This mode does
not export the existing Wi-Fi password to the PC or change Linux passwords.
Install the optional Windows-side dependencies from `requirements.txt`.

Run `python test_configure.py` for offline configuration and credential-handling
tests. Use the Product's `gar target wifi` binding for the physical operation.
