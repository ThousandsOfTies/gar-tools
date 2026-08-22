#!/usr/bin/env bash
# Generate a read-only UUU script for inspecting FRDM-IMX91S SPI-NAND.
# This boots the manufacturing initramfs into RAM and never erases or writes MTD.
set -euo pipefail

uuu_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

config_file="${GAR_IMX91S_UUU_CONFIG:-${uuu_root}/imx91s-uuu.env.example}"
bundle_dir="${GAR_IMX91S_UUU_BUNDLE:-${PWD}}"
output="${GAR_IMX91S_LAYOUT_PROBE_OUTPUT:-${bundle_dir}/Inspect-imx91s-layout.lst}"
validate=0

usage() {
  cat <<'EOF'
Usage: generate-layout-probe.sh [options]

Generate a read-only UUU script which boots the manufacturing initramfs and
prints the SPI-NAND MTD/UBI information. It never erases, formats, mounts, or
writes persistent storage.

Options:
  --config FILE       UUU/layout environment file
  --bundle-dir DIR    directory containing the existing UUU components
  --output FILE       generated probe script path
  --validate          run `uuu -dry` after generation
  -h, --help          show this help
EOF
}

while (($#)); do
  case "$1" in
    --config)
      [[ $# -ge 2 ]] || { echo "--config requires a file" >&2; exit 2; }
      config_file="$2"
      shift 2
      ;;
    --bundle-dir)
      [[ $# -ge 2 ]] || { echo "--bundle-dir requires a directory" >&2; exit 2; }
      bundle_dir="$2"
      shift 2
      ;;
    --output)
      [[ $# -ge 2 ]] || { echo "--output requires a file" >&2; exit 2; }
      output="$2"
      shift 2
      ;;
    --validate)
      validate=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -f "$config_file" ]]; then
  # shellcheck disable=SC1090
  source "$config_file"
elif [[ "$config_file" != "${uuu_root}/imx91s-uuu.env.example" ]]; then
  echo "missing UUU config: $config_file" >&2
  exit 1
fi

: "${GAR_UUU_VERSION:=1.5.243}"
: "${GAR_UUU_TRANSFER_TIMEOUT_MS:=30000}"
: "${GAR_IMX91S_FASTBOOT_BUFFER:=0x82800000}"
: "${GAR_UUU_TRANSFER_CHUNK_SIZE:=0x100000}"
: "${GAR_IMX91S_INITRD_ADDR:=0x85000000}"
: "${GAR_IMX91S_DTB:=imx91-11x11-frdm-imx91s.dtb}"
: "${GAR_IMX91S_RAM_BOOT_IMAGE:=flash.bin}"

if [[ ! "$GAR_UUU_TRANSFER_TIMEOUT_MS" =~ ^[1-9][0-9]*$ ]]; then
  echo "GAR_UUU_TRANSFER_TIMEOUT_MS must be a positive integer: $GAR_UUU_TRANSFER_TIMEOUT_MS" >&2
  exit 1
fi
for hex_value_name in GAR_IMX91S_FASTBOOT_BUFFER GAR_UUU_TRANSFER_CHUNK_SIZE GAR_IMX91S_INITRD_ADDR; do
  if [[ ! "${!hex_value_name}" =~ ^0x[0-9A-Fa-f]+$ ]]; then
    echo "${hex_value_name} must be a hexadecimal UUU value: ${!hex_value_name}" >&2
    exit 1
  fi
done
transfer_chunk_size=$((GAR_UUU_TRANSFER_CHUNK_SIZE))
if ((transfer_chunk_size == 0 || transfer_chunk_size > 0x100000)); then
  echo "GAR_UUU_TRANSFER_CHUNK_SIZE must be between 0x1 and 0x100000: $GAR_UUU_TRANSFER_CHUNK_SIZE" >&2
  exit 1
fi

required_files=(
  "pub/u-boot/${GAR_IMX91S_RAM_BOOT_IMAGE}"
  "pub/kernel/Image"
  "pub/kernel/${GAR_IMX91S_DTB}"
  "pub/mfgtools/fsl-image-mfgtool-initramfs-imx_mfgtools.cpio.zst"
)

for relative in "${required_files[@]}"; do
  if [[ ! -f "${bundle_dir}/${relative}" ]]; then
    echo "missing UUU component: ${bundle_dir}/${relative}" >&2
    exit 1
  fi
done

file_size_hex() {
  printf '0x%X' "$(stat -c '%s' "$1")"
}

kernel_size="$(file_size_hex "${bundle_dir}/pub/kernel/Image")"
dtb_size="$(file_size_hex "${bundle_dir}/pub/kernel/${GAR_IMX91S_DTB}")"
initrd_size="$(file_size_hex "${bundle_dir}/pub/mfgtools/fsl-image-mfgtool-initramfs-imx_mfgtools.cpio.zst")"

kernel_transfer="pub/uuu-ram/Image.padded"
dtb_transfer="pub/uuu-ram/${GAR_IMX91S_DTB}.padded"
initrd_transfer="pub/uuu-ram/fsl-image-mfgtool-initramfs-imx_mfgtools.cpio.zst.padded"

prepare_padded_payload() {
  local source="$1"
  local relative_destination="$2"
  local size padded_size destination
  size="$(stat -c '%s' "$source")"
  padded_size=$(((size + transfer_chunk_size - 1) / transfer_chunk_size * transfer_chunk_size))
  destination="${bundle_dir}/${relative_destination}"
  install -D -m 0644 "$source" "$destination"
  truncate -s "$padded_size" "$destination"
  printf 'prepared UUU RAM payload: %s (original=0x%X padded=0x%X)\n' \
    "$relative_destination" "$size" "$padded_size"
}

prepare_padded_payload "${bundle_dir}/pub/kernel/Image" "$kernel_transfer"
prepare_padded_payload "${bundle_dir}/pub/kernel/${GAR_IMX91S_DTB}" "$dtb_transfer"
prepare_padded_payload \
  "${bundle_dir}/pub/mfgtools/fsl-image-mfgtool-initramfs-imx_mfgtools.cpio.zst" \
  "$initrd_transfer"

mkdir -p "$(dirname "$output")"
cat > "$output" <<EOF
uuu_version ${GAR_UUU_VERSION}

# Read-only FRDM-IMX91S SPI-NAND layout probe.
# This script boots Linux into RAM and only prints information. It does not
# erase, format, mount, or write the target SPI-NAND.

SDPS[-t 10000]: boot -scanterm -f pub/u-boot/${GAR_IMX91S_RAM_BOOT_IMAGE} -scanlimited 0x800000

FB: ucmd setenv gar_kernel_addr \${loadaddr}
FB: ucmd setenv fastboot_buffer ${GAR_IMX91S_FASTBOOT_BUFFER}
FB[-t ${GAR_UUU_TRANSFER_TIMEOUT_MS}]: write -f ${kernel_transfer} -format "setexpr gar_copy_dst \${loadaddr} + @off; cp.b \${fastboot_buffer} \${gar_copy_dst} @size" -blksz 1 -each ${GAR_UUU_TRANSFER_CHUNK_SIZE}
FB: ucmd setenv gar_kernel_size ${kernel_size}

FB: ucmd setenv gar_dtb_addr \${fdt_addr_r}
FB: ucmd setenv fastboot_buffer ${GAR_IMX91S_FASTBOOT_BUFFER}
FB[-t ${GAR_UUU_TRANSFER_TIMEOUT_MS}]: write -f ${dtb_transfer} -format "setexpr gar_copy_dst \${fdt_addr_r} + @off; cp.b \${fastboot_buffer} \${gar_copy_dst} @size" -blksz 1 -each ${GAR_UUU_TRANSFER_CHUNK_SIZE}
FB: ucmd setenv gar_dtb_size ${dtb_size}

FB: ucmd setenv gar_initrd_addr ${GAR_IMX91S_INITRD_ADDR}
FB: ucmd setenv fastboot_buffer ${GAR_IMX91S_FASTBOOT_BUFFER}
FB[-t ${GAR_UUU_TRANSFER_TIMEOUT_MS}]: write -f ${initrd_transfer} -format "setexpr gar_copy_dst \${gar_initrd_addr} + @off; cp.b \${fastboot_buffer} \${gar_copy_dst} @size" -blksz 1 -each ${GAR_UUU_TRANSFER_CHUNK_SIZE}
FB: ucmd setenv gar_initrd_size ${initrd_size}
FB: ucmd run mfgtool_args
FB: ucmd iminfo \${gar_initrd_addr}
FB: ucmd setenv gar_bootcmd booti \${gar_kernel_addr} \${gar_initrd_addr} \${gar_dtb_addr}
FB: acmd run gar_bootcmd

FBK: ucmd echo GAR_IMX91S_LAYOUT_PROBE_BEGIN
FBK: ucmd udevadm settle || true
FBK: ucmd cat /proc/mtd
FBK: ucmd ls -l /dev/mtd* || true
FBK: ucmd cat /sys/class/mtd/mtd0/name
FBK: ucmd cat /sys/class/mtd/mtd0/size
FBK: ucmd cat /sys/class/mtd/mtd0/erasesize
FBK: ucmd cat /sys/class/mtd/mtd0/writesize
FBK: ucmd cat /sys/class/mtd/mtd1/name
FBK: ucmd cat /sys/class/mtd/mtd1/size
FBK: ucmd cat /sys/class/mtd/mtd2/name
FBK: ucmd cat /sys/class/mtd/mtd2/size
FBK: ucmd cat /sys/class/mtd/mtd3/name
FBK: ucmd cat /sys/class/mtd/mtd3/size
FBK: ucmd cat /sys/class/mtd/mtd4/name
FBK: ucmd cat /sys/class/mtd/mtd4/size
FBK: ucmd ubinfo -a || true
# Keep block-device output as context: mmcblk1 is the removable microSD on the
# observed board, not the onboard target used by the NAND factory flow.
FBK: ucmd cat /proc/partitions
FBK: ucmd ls -l /dev/mmcblk1* || true
FBK: ucmd cat /sys/block/mmcblk1/size || true
FBK: ucmd blockdev --getsize64 /dev/mmcblk1 || true
FBK: ucmd sfdisk --dump /dev/mmcblk1 || true
FBK: ucmd cat /sys/block/mmcblk1/device/name || true
FBK: ucmd cat /sys/block/mmcblk1/device/type || true
FBK: ucmd echo GAR_IMX91S_LAYOUT_PROBE_END
EOF

if [[ "$(sed -n '1p' "$output")" != "uuu_version "* ]]; then
  echo "generated UUU command list must begin with uuu_version: $output" >&2
  exit 1
fi

if ((validate)); then
  uuu_bin="${GAR_UUU_BIN:-}"
  if [[ -z "$uuu_bin" ]]; then
    uuu_bin="$(command -v uuu || true)"
  fi
  if [[ -z "$uuu_bin" || ! -x "$uuu_bin" ]]; then
    echo "--validate requires uuu (set GAR_UUU_BIN if it is not on PATH)" >&2
    exit 1
  fi
  echo "validating layout probe syntax with $uuu_bin -dry"
  (cd "$(dirname "$output")" && "$uuu_bin" -dry "$(basename "$output")")
fi

echo "generated read-only layout probe: $output"
