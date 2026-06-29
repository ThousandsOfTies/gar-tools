#!/usr/bin/env bash
set -euo pipefail

# Start MediaMTX RTSP server on Raspberry Pi.
# Uses Docker when available, otherwise prints install hint.

if command -v docker >/dev/null 2>&1; then
  echo "[raspi-mediatx] starting docker container on :8554"
  exec docker run --rm -it \
    -p 8554:8554 \
    --name gar-mediatx \
    bluenviron/mediamtx:latest
fi

echo "docker not found. install one of the following:"
echo "  1) docker + bluenviron/mediamtx"
echo "  2) native mediamtx binary"
exit 1
