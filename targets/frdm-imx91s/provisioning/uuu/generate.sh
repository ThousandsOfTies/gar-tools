#!/usr/bin/env bash
# Generate a product-configured FRDM-IMX91S component UUU script.
set -euo pipefail

uuu_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

config_file="${GAR_IMX91S_UUU_CONFIG:-${uuu_root}/imx91s-uuu.env.example}"
template="${GAR_IMX91S_TEMPLATE:-${uuu_root}/factory-spinand.lst.in}"
output="${GAR_IMX91S_OUTPUT:-${PWD}/Factory-uuu-frdm-imx91s.lst}"
bundle_dir="${GAR_IMX91S_UUU_BUNDLE:-}"
allow_unconfirmed=0
validate=0
dry_run=0

usage() {
  cat <<'EOF'
Usage: generate.sh [options]

Options:
  --config FILE          UUU/layout environment file
  --template FILE        .lst.in template (default: Target Pack factory template)
  --output FILE          generated .lst path
  --bundle-dir DIR       directory containing pub/ component files
  --allow-unconfirmed    generate a review script with NAND writes gated off
  --validate             run `uuu -dry` after generation
  --dry-run              print the resolved values without writing a file
  -h, --help             show this help
EOF
}

while (($#)); do
  case "$1" in
    --config)
      [[ $# -ge 2 ]] || { echo "--config requires a file" >&2; exit 2; }
      config_file="$2"
      shift 2
      ;;
    --template)
      [[ $# -ge 2 ]] || { echo "--template requires a file" >&2; exit 2; }
      template="$2"
      shift 2
      ;;
    --output)
      [[ $# -ge 2 ]] || { echo "--output requires a file" >&2; exit 2; }
      output="$2"
      shift 2
      ;;
    --bundle-dir)
      [[ $# -ge 2 ]] || { echo "--bundle-dir requires a directory" >&2; exit 2; }
      bundle_dir="$2"
      shift 2
      ;;
    --allow-unconfirmed)
      allow_unconfirmed=1
      shift
      ;;
    --validate)
      validate=1
      shift
      ;;
    --dry-run)
      dry_run=1
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
: "${GAR_IMX91S_NAND_BOOT_IMAGE:=flash_spinand.bin}"
: "${GAR_IMX91S_NAND_DEVICE:=spi-nand0}"
: "${GAR_IMX91S_NAND_BOOTLOADER_MTD:=0}"
: "${GAR_IMX91S_NAND_CONFIG_MTD:=1}"
: "${GAR_IMX91S_NAND_KERNEL_MTD:=2}"
: "${GAR_IMX91S_NAND_DTB_MTD:=3}"
: "${GAR_IMX91S_NAND_ROOTFS_MTD:=4}"
: "${GAR_IMX91S_NAND_LAYOUT_CONFIRMED:=0}"

if [[ -z "$bundle_dir" ]]; then
  bundle_dir="${GAR_IMX91S_UUU_BUNDLE:-$(cd "$(dirname "$output")" && pwd)}"
fi

for value_name in \
  GAR_UUU_VERSION \
  GAR_UUU_TRANSFER_TIMEOUT_MS \
  GAR_IMX91S_FASTBOOT_BUFFER \
  GAR_UUU_TRANSFER_CHUNK_SIZE \
  GAR_IMX91S_INITRD_ADDR \
  GAR_IMX91S_DTB \
  GAR_IMX91S_RAM_BOOT_IMAGE \
  GAR_IMX91S_NAND_BOOT_IMAGE \
  GAR_IMX91S_NAND_DEVICE \
  GAR_IMX91S_NAND_BOOTLOADER_MTD \
  GAR_IMX91S_NAND_CONFIG_MTD \
  GAR_IMX91S_NAND_KERNEL_MTD \
  GAR_IMX91S_NAND_DTB_MTD \
  GAR_IMX91S_NAND_ROOTFS_MTD; do
  if [[ -z "${!value_name}" ]]; then
    echo "${value_name} must not be empty" >&2
    exit 1
  fi
done

for mtd_value_name in \
  GAR_IMX91S_NAND_BOOTLOADER_MTD \
  GAR_IMX91S_NAND_CONFIG_MTD \
  GAR_IMX91S_NAND_KERNEL_MTD \
  GAR_IMX91S_NAND_DTB_MTD \
  GAR_IMX91S_NAND_ROOTFS_MTD; do
  if [[ ! "${!mtd_value_name}" =~ ^[0-9]+$ ]]; then
    echo "${mtd_value_name} must be a non-negative MTD index: ${!mtd_value_name}" >&2
    exit 1
  fi
done

if [[ ! "$GAR_IMX91S_NAND_LAYOUT_CONFIRMED" =~ ^[01]$ ]]; then
  echo "GAR_IMX91S_NAND_LAYOUT_CONFIRMED must be 0 or 1: $GAR_IMX91S_NAND_LAYOUT_CONFIRMED" >&2
  exit 1
fi

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

if [[ ! -f "$template" ]]; then
  echo "missing UUU template: $template" >&2
  exit 1
fi

if [[ "$GAR_IMX91S_NAND_LAYOUT_CONFIRMED" != "1" && "$allow_unconfirmed" != "1" ]]; then
  cat >&2 <<EOF
FRDM-IMX91S SPI-NAND layout is not confirmed.
Set GAR_IMX91S_NAND_LAYOUT_CONFIRMED=1 only after checking the real board, or
use --allow-unconfirmed to generate a review script whose first write gate fails.
EOF
  exit 1
fi

echo "UUU version:     $GAR_UUU_VERSION"
echo "Transfer timeout: ${GAR_UUU_TRANSFER_TIMEOUT_MS} ms"
echo "Fastboot buffer:  ${GAR_IMX91S_FASTBOOT_BUFFER}"
echo "Transfer chunk:   ${GAR_UUU_TRANSFER_CHUNK_SIZE}"
echo "Initrd address:    ${GAR_IMX91S_INITRD_ADDR}"
echo "DTB:             $GAR_IMX91S_DTB"
echo "RAM boot image:  $GAR_IMX91S_RAM_BOOT_IMAGE"
echo "NAND boot image: $GAR_IMX91S_NAND_BOOT_IMAGE"
echo "NAND device:     $GAR_IMX91S_NAND_DEVICE"
echo "MTD indices:     bootloader=$GAR_IMX91S_NAND_BOOTLOADER_MTD config=$GAR_IMX91S_NAND_CONFIG_MTD kernel=$GAR_IMX91S_NAND_KERNEL_MTD dtb=$GAR_IMX91S_NAND_DTB_MTD rootfs=$GAR_IMX91S_NAND_ROOTFS_MTD"
echo "NAND confirmed:  $GAR_IMX91S_NAND_LAYOUT_CONFIRMED"

if ((dry_run)); then
  echo "would generate: $output"
  exit 0
fi

required_files=(
  "pub/u-boot/${GAR_IMX91S_RAM_BOOT_IMAGE}"
  "pub/u-boot/${GAR_IMX91S_NAND_BOOT_IMAGE}"
  "pub/kernel/Image"
  "pub/kernel/${GAR_IMX91S_DTB}"
  "pub/rootfs/rootfs.squashfs"
  "pub/rootfs/usr.local.tar.bz2"
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
nand_boot_size="$(file_size_hex "${bundle_dir}/pub/u-boot/${GAR_IMX91S_NAND_BOOT_IMAGE}")"

if ((kernel_size > 0x2400000)); then
  echo "kernel exceeds the 36 MiB NAND partition: $kernel_size" >&2
  exit 1
fi
if ((dtb_size > 0x20000)); then
  echo "DTB exceeds the 128 KiB NAND partition: $dtb_size" >&2
  exit 1
fi
if ((nand_boot_size > 0x800000)); then
  echo "NAND boot image exceeds the 8 MiB bootloader partition: $nand_boot_size" >&2
  exit 1
fi

kernel_transfer="pub/uuu-ram/Image.padded"
dtb_transfer="pub/uuu-ram/${GAR_IMX91S_DTB}.padded"
initrd_transfer="pub/uuu-ram/fsl-image-mfgtool-initramfs-imx_mfgtools.cpio.zst.padded"
nand_boot_transfer="pub/uuu-ram/${GAR_IMX91S_NAND_BOOT_IMAGE}.padded"

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
prepare_padded_payload \
  "${bundle_dir}/pub/u-boot/${GAR_IMX91S_NAND_BOOT_IMAGE}" \
  "$nand_boot_transfer"

mkdir -p "$(dirname "$output")"
cp "$template" "$output"

replace_token() {
  local token="$1"
  local value="$2"
  local escaped
  escaped="$(printf '%s' "$value" | sed 's/[\\&|]/\\&/g')"
  sed -i "s|@@${token}@@|${escaped}|g" "$output"
}

replace_token UUU_VERSION "$GAR_UUU_VERSION"
replace_token TRANSFER_TIMEOUT_MS "$GAR_UUU_TRANSFER_TIMEOUT_MS"
replace_token FASTBOOT_BUFFER "$GAR_IMX91S_FASTBOOT_BUFFER"
replace_token TRANSFER_CHUNK_SIZE "$GAR_UUU_TRANSFER_CHUNK_SIZE"
replace_token INITRD_ADDR "$GAR_IMX91S_INITRD_ADDR"
replace_token RAM_BOOT_IMAGE "$GAR_IMX91S_RAM_BOOT_IMAGE"
replace_token NAND_BOOT_IMAGE "$GAR_IMX91S_NAND_BOOT_IMAGE"
replace_token NAND_BOOT_TRANSFER "$nand_boot_transfer"
replace_token NAND_BOOT_SIZE "$nand_boot_size"
replace_token NAND_DEVICE "$GAR_IMX91S_NAND_DEVICE"
replace_token NAND_LAYOUT_CONFIRMED "$GAR_IMX91S_NAND_LAYOUT_CONFIRMED"
replace_token KERNEL_TRANSFER "$kernel_transfer"
replace_token DTB_TRANSFER "$dtb_transfer"
replace_token INITRD_TRANSFER "$initrd_transfer"
replace_token KERNEL_SIZE "$kernel_size"
replace_token DTB_SIZE "$dtb_size"
replace_token INITRD_SIZE "$initrd_size"
replace_token DTB "$GAR_IMX91S_DTB"
replace_token BOOTLOADER_MTD "$GAR_IMX91S_NAND_BOOTLOADER_MTD"
replace_token CONFIG_MTD "$GAR_IMX91S_NAND_CONFIG_MTD"
replace_token KERNEL_MTD "$GAR_IMX91S_NAND_KERNEL_MTD"
replace_token DTB_MTD "$GAR_IMX91S_NAND_DTB_MTD"
replace_token ROOTFS_MTD "$GAR_IMX91S_NAND_ROOTFS_MTD"

if grep -Eq '@@[A-Z0-9_]+@@' "$output"; then
  echo "unresolved placeholders remain in $output" >&2
  exit 1
fi

if [[ "$(sed -n '1p' "$output")" != "uuu_version "* ]]; then
  echo "UUU command list must begin with uuu_version: $output" >&2
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
  echo "validating UUU syntax with $uuu_bin -dry"
  (cd "$(dirname "$output")" && "$uuu_bin" -dry "$(basename "$output")")
fi

echo "generated: $output"
