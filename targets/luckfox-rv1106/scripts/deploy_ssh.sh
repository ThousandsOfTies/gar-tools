#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: $0 <local-binary>"
  exit 1
fi

local_bin="$1"
host="${LUCKFOX_HOST:-root@10.42.0.1}"
deploy_dir="${LUCKFOX_DEPLOY_DIR:-/opt/gar/bin}"

if [[ ! -f "$local_bin" ]]; then
  echo "binary not found: $local_bin"
  exit 1
fi

echo "[deploy] target: $host"
echo "[deploy] dir: $deploy_dir"

ssh "$host" "mkdir -p '$deploy_dir'"
scp "$local_bin" "$host:$deploy_dir/gar_luckfox_streamer"

echo "[deploy] done"
