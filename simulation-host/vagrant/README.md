# Shared Vagrant Sim Hosts

Copy this directory to a local project directory. `machines.csv` declares VM
names/resources and loopback panel ports. Every machine uses the same pinned
Ubuntu 24.04 box (202510.26.0) and provider bootstrap. Do not put Product wiring or App code here.

Vagrant owns create/boot/halt; GAR owns SIM_RUNTIME/SIM_APP build, deployment,
start, diagnostics and build identity. Guest provisioning does not compile Apps.
The CSV can contain any number of uniquely named machines and panel ports.
Private IPv4 addresses connect machines on a project-specific VirtualBox
internal network; each guest also retains its NAT SSH connection. This creates
no bridged physical NIC or host-only host adapter. GAR reads private IP/bridge
port from this CSV rather than copying them into workspace settings.
Always address a named machine (`vagrant up sim1 --provider virtualbox`);
unqualified `up` does not start all defined machines automatically.

The provider loads gpio-sim and CUSE against the real guest kernel. Products
read their common hardware CSVs through the normal GAR runtime. Each VM has
its own kernel device namespace. No physical target is attached.

Existing manually created VMs are not imported, renamed, destroyed or changed.
GAR configuration selects this provider explicitly; installed box version is
fixed and is not upgraded during normal starts. Camera loopback/DKMS and other
special devices need their provider prerequisites separately; gpio-sim/CUSE
success alone does not certify every Product.

The installed Debian 13 base was evaluated and rejected: its stock kernel did
not provide gpio-sim. A running VM without that device support is not a ready
GAR Linux simulator. Provisioning failure propagates to GAR; a subsequent
start retries incomplete prerequisites. Boot-time device checks also run via
`gar-sim-host-devices.service`.
