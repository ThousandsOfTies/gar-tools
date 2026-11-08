#!/usr/bin/env bash
# Assemble the component files and generated UUU script into one GAR bundle.
set -euo pipefail

uuu_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

input_dir="${GAR_UUU_INPUT_DIR:-}"
output_dir="${GAR_IMX91S_OUTPUT_DIR:-${PWD}/frdm-imx91s-uuu-bundle}"
config_file="${GAR_IMX91S_UUU_CONFIG:-${uuu_root}/imx91s-uuu.env.example}"
allow_unconfirmed=0
validate=0
force=0

usage() {
  cat <<'EOF'
Usage: stage.sh --input-dir DIR [options]

DIR must contain the built component tree below:
  pub/u-boot/<RAM_BOOT_IMAGE>
  pub/u-boot/<NAND_BOOT_IMAGE>
  pub/kernel/Image
  pub/kernel/<DTB>
  pub/rootfs/rootfs.squashfs
  pub/rootfs/usr.local.tar.bz2
  pub/mfgtools/fsl-image-mfgtool-initramfs-imx_mfgtools.cpio.zst

Options:
  --input-dir DIR        component input tree (or GAR_UUU_INPUT_DIR)
  --output-dir DIR       output bundle (default: ./frdm-imx91s-uuu-bundle)
  --config FILE          UUU/layout environment file
  --allow-unconfirmed    stage a review bundle whose NAND write gate is off
  --validate             run `uuu -dry` against the staged bundle
  --force                replace an existing output directory
  -h, --help             show this help
EOF
}

while (($#)); do
  case "$1" in
    --input-dir)
      [[ $# -ge 2 ]] || { echo "--input-dir requires a directory" >&2; exit 2; }
      input_dir="$2"
      shift 2
      ;;
    --output-dir)
      [[ $# -ge 2 ]] || { echo "--output-dir requires a directory" >&2; exit 2; }
      output_dir="$2"
      shift 2
      ;;
    --config)
      [[ $# -ge 2 ]] || { echo "--config requires a file" >&2; exit 2; }
      config_file="$2"
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
    --force)
      force=1
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

if [[ -z "$input_dir" ]]; then
  echo "--input-dir (or GAR_UUU_INPUT_DIR) is required" >&2
  exit 2
fi
if [[ ! -d "$input_dir" ]]; then
  echo "missing component input directory: $input_dir" >&2
  exit 1
fi

input_abs="$(realpath -- "$input_dir")"
output_abs="$(realpath -m -- "$output_dir")"
case "$output_abs" in
  /|"$(pwd -P)")
    echo "refusing unsafe output directory: $output_abs" >&2
    exit 1
    ;;
esac
if [[ "$input_abs" == "$output_abs" || "$input_abs" == "$output_abs/"* ]]; then
  echo "output directory must not be the input directory or its parent: $output_abs" >&2
  exit 1
fi

if [[ -f "$config_file" ]]; then
  # shellcheck disable=SC1090
  source "$config_file"
elif [[ "$config_file" != "${uuu_root}/imx91s-uuu.env.example" ]]; then
  echo "missing UUU config: $config_file" >&2
  exit 1
fi

: "${GAR_IMX91S_DTB:=imx91-11x11-frdm-imx91s.dtb}"
: "${GAR_IMX91S_RAM_BOOT_IMAGE:=flash.bin}"
: "${GAR_IMX91S_NAND_BOOT_IMAGE:=flash_spinand.bin}"
: "${GAR_IMX91S_NAND_LAYOUT_CONFIRMED:=0}"
: "${GAR_IMX91S_FACTORY_SCRIPT_NAME:=Factory-uuu-frdm-imx91s.lst}"
: "${GAR_PRODUCT_NAME:=Product}"

if [[ ! "$GAR_IMX91S_NAND_LAYOUT_CONFIRMED" =~ ^[01]$ ]]; then
  echo "GAR_IMX91S_NAND_LAYOUT_CONFIRMED must be 0 or 1: $GAR_IMX91S_NAND_LAYOUT_CONFIRMED" >&2
  exit 1
fi

if [[ "$GAR_IMX91S_NAND_LAYOUT_CONFIRMED" != "1" && "$allow_unconfirmed" != "1" ]]; then
  echo "refusing to stage an unconfirmed FRDM-IMX91S NAND layout; use --allow-unconfirmed for review only" >&2
  exit 1
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
  if [[ ! -f "${input_dir}/${relative}" ]]; then
    echo "missing component: ${input_dir}/${relative}" >&2
    exit 1
  fi
done

if [[ -e "$output_abs" && -n "$(find "$output_abs" -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null)" ]]; then
  if (( ! force )); then
    echo "output directory is not empty (use --force): $output_abs" >&2
    exit 1
  fi
  rm -rf -- "$output_abs"
fi
output_dir="$output_abs"

tmp_dir="$(mktemp -d)"
trap 'rm -rf -- "$tmp_dir"' EXIT

for relative in "${required_files[@]}"; do
  install -D -m 0644 "${input_dir}/${relative}" "${tmp_dir}/${relative}"
done

generate_args=(
  --config "$config_file"
  --output "${tmp_dir}/${GAR_IMX91S_FACTORY_SCRIPT_NAME}"
  --bundle-dir "$tmp_dir"
)
if ((allow_unconfirmed)); then
  generate_args+=(--allow-unconfirmed)
fi
if ((validate)); then
  generate_args+=(--validate)
fi
"${uuu_root}/generate.sh" "${generate_args[@]}"

mkdir -p "$output_dir"
cp -a "${tmp_dir}/." "$output_dir/"
(
  cd "$output_dir"
  sha256sum \
    "${GAR_IMX91S_FACTORY_SCRIPT_NAME}" \
    "pub/u-boot/${GAR_IMX91S_RAM_BOOT_IMAGE}" \
    "pub/u-boot/${GAR_IMX91S_NAND_BOOT_IMAGE}" \
    pub/kernel/Image \
    "pub/kernel/${GAR_IMX91S_DTB}" \
    "pub/uuu-ram/${GAR_IMX91S_NAND_BOOT_IMAGE}.padded" \
    pub/uuu-ram/Image.padded \
    "pub/uuu-ram/${GAR_IMX91S_DTB}.padded" \
    pub/uuu-ram/fsl-image-mfgtool-initramfs-imx_mfgtools.cpio.zst.padded \
    pub/rootfs/rootfs.squashfs \
    pub/rootfs/usr.local.tar.bz2 \
    pub/mfgtools/fsl-image-mfgtool-initramfs-imx_mfgtools.cpio.zst > checksums.sha256
)

cat > "${output_dir}/bundle-info.txt" <<EOF
${GAR_PRODUCT_NAME} FRDM-IMX91S component UUU bundle
Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)
SPI-NAND layout confirmed: ${GAR_IMX91S_NAND_LAYOUT_CONFIRMED}
This bundle contains UUU components only; merge it with the Product app
artifact before invoking \`gar target deploy\`.
EOF

echo "staged UUU bundle: $output_dir"
