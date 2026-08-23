#!/usr/bin/env bash
# Generate a guarded FRDM-IMX91S SPI-NAND DTB-only UUU command list.
set -euo pipefail

uuu_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
config_file="${GAR_IMX91S_UUU_CONFIG:-${uuu_root}/imx91s-uuu.env.example}"
template="${GAR_IMX91S_DTB_UPDATE_TEMPLATE:-${uuu_root}/update-dtb.lst.in}"
output="${GAR_IMX91S_DTB_UPDATE_OUTPUT:-${PWD}/Update-dtb-frdm-imx91s.lst}"
bundle_dir="${GAR_IMX91S_UUU_BUNDLE:-}"
validate=0
dry_run=0

usage() {
  cat <<'EOF'
Usage: generate-dtb-update.sh [options]

Options:
  --config FILE       UUU/layout environment file
  --template FILE     DTB-only .lst.in template
  --output FILE       generated .lst path
  --bundle-dir DIR    directory containing pub/ component files
  --validate          run `uuu -dry` after generation
  --dry-run           print resolved values without writing files
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
: "${GAR_IMX91S_NAND_DTB_MTD:=3}"
: "${GAR_IMX91S_NAND_LAYOUT_CONFIRMED:=0}"

if [[ -z "$bundle_dir" ]]; then
  bundle_dir="${GAR_IMX91S_UUU_BUNDLE:-$(cd "$(dirname "$output")" && pwd)}"
fi

if [[ "$GAR_IMX91S_NAND_LAYOUT_CONFIRMED" != "1" ]]; then
  echo "DTB update requires GAR_IMX91S_NAND_LAYOUT_CONFIRMED=1 after a live layout probe" >&2
  exit 1
fi
if [[ ! "$GAR_IMX91S_NAND_DTB_MTD" =~ ^[0-9]+$ ]]; then
  echo "GAR_IMX91S_NAND_DTB_MTD must be a non-negative MTD index" >&2
  exit 1
fi
if [[ ! "$GAR_UUU_TRANSFER_TIMEOUT_MS" =~ ^[1-9][0-9]*$ ]]; then
  echo "GAR_UUU_TRANSFER_TIMEOUT_MS must be a positive integer" >&2
  exit 1
fi
for value_name in GAR_IMX91S_FASTBOOT_BUFFER GAR_UUU_TRANSFER_CHUNK_SIZE GAR_IMX91S_INITRD_ADDR; do
  if [[ ! "${!value_name}" =~ ^0x[0-9A-Fa-f]+$ ]]; then
    echo "${value_name} must be hexadecimal: ${!value_name}" >&2
    exit 1
  fi
done
transfer_chunk_size=$((GAR_UUU_TRANSFER_CHUNK_SIZE))
if ((transfer_chunk_size == 0 || transfer_chunk_size > 0x100000)); then
  echo "GAR_UUU_TRANSFER_CHUNK_SIZE must be between 0x1 and 0x100000" >&2
  exit 1
fi
[[ -f "$template" ]] || { echo "missing DTB update template: $template" >&2; exit 1; }

required_files=(
  "pub/u-boot/${GAR_IMX91S_RAM_BOOT_IMAGE}"
  "pub/kernel/Image"
  "pub/kernel/${GAR_IMX91S_DTB}"
  "pub/mfgtools/fsl-image-mfgtool-initramfs-imx_mfgtools.cpio.zst"
)
for relative in "${required_files[@]}"; do
  [[ -f "${bundle_dir}/${relative}" ]] || {
    echo "missing UUU component: ${bundle_dir}/${relative}" >&2
    exit 1
  }
done

dtb_size_decimal="$(stat -c '%s' "${bundle_dir}/pub/kernel/${GAR_IMX91S_DTB}")"
if ((dtb_size_decimal > 0x20000)); then
  printf 'DTB exceeds the 128 KiB NAND partition: 0x%X\n' "$dtb_size_decimal" >&2
  exit 1
fi
initrd_size="$(printf '0x%X' "$(stat -c '%s' "${bundle_dir}/pub/mfgtools/fsl-image-mfgtool-initramfs-imx_mfgtools.cpio.zst")")"

echo "DTB:             $GAR_IMX91S_DTB"
echo "DTB MTD:         $GAR_IMX91S_NAND_DTB_MTD"
echo "RAM boot image:  $GAR_IMX91S_RAM_BOOT_IMAGE"
echo "NAND confirmed:  $GAR_IMX91S_NAND_LAYOUT_CONFIRMED"

if ((dry_run)); then
  echo "would generate: $output"
  exit 0
fi

prepare_padded_payload() {
  local source="$1"
  local relative_destination="$2"
  local size padded_size destination
  size="$(stat -c '%s' "$source")"
  padded_size=$(((size + transfer_chunk_size - 1) / transfer_chunk_size * transfer_chunk_size))
  destination="${bundle_dir}/${relative_destination}"
  install -D -m 0644 "$source" "$destination"
  truncate -s "$padded_size" "$destination"
}

kernel_transfer="pub/uuu-ram/Image.padded"
dtb_transfer="pub/uuu-ram/${GAR_IMX91S_DTB}.padded"
initrd_transfer="pub/uuu-ram/fsl-image-mfgtool-initramfs-imx_mfgtools.cpio.zst.padded"
prepare_padded_payload "${bundle_dir}/pub/kernel/Image" "$kernel_transfer"
prepare_padded_payload "${bundle_dir}/pub/kernel/${GAR_IMX91S_DTB}" "$dtb_transfer"
prepare_padded_payload \
  "${bundle_dir}/pub/mfgtools/fsl-image-mfgtool-initramfs-imx_mfgtools.cpio.zst" \
  "$initrd_transfer"

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
replace_token KERNEL_TRANSFER "$kernel_transfer"
replace_token DTB_TRANSFER "$dtb_transfer"
replace_token INITRD_TRANSFER "$initrd_transfer"
replace_token INITRD_SIZE "$initrd_size"
replace_token DTB "$GAR_IMX91S_DTB"
replace_token DTB_SIZE_DECIMAL "$dtb_size_decimal"
replace_token DTB_MTD "$GAR_IMX91S_NAND_DTB_MTD"

if grep -Eq '@@[A-Z0-9_]+@@' "$output"; then
  echo "unresolved placeholders remain in $output" >&2
  exit 1
fi

if ((validate)); then
  uuu_bin="${GAR_UUU_BIN:-$(command -v uuu || true)}"
  [[ -n "$uuu_bin" && -x "$uuu_bin" ]] || {
    echo "--validate requires uuu (set GAR_UUU_BIN if it is not on PATH)" >&2
    exit 1
  }
  (cd "$(dirname "$output")" && "$uuu_bin" -dry "$(basename "$output")")
fi

echo "generated DTB-only updater: $output"
