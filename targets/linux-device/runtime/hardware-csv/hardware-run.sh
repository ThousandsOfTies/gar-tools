#!/bin/sh
# Same authored CSVs on physical and virtual Linux devices; no Python required.
set -eu
hardware_dir=$1
shift
[ "$#" -gt 0 ] || { echo 'hardware-run: command required' >&2; exit 2; }
loader_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
set -- "$hardware_dir" "$@"
# All input validation completes before a command can run.
assignments=$(awk -v directory="$hardware_dir" -f "$loader_dir/hardware-env.awk" \
    "$hardware_dir/environment.csv" "$hardware_dir/gpio.csv" "$hardware_dir/spi.csv") || exit 2
eval "$assignments"
shift
exec "$@"
