#!/usr/bin/env bash
set -euo pipefail

# View RTSP stream on Raspberry Pi.
# Default assumes MediaMTX runs on the same Raspberry Pi.

rtsp_host="${1:-${RTSP_HOST:-127.0.0.1}}"
stream_name="${RTSP_STREAM_NAME:-luckfox}"
rtsp_url="${RTSP_URL:-rtsp://${rtsp_host}:8554/${stream_name}}"

echo "[raspi-view] url=$rtsp_url"

if command -v gst-launch-1.0 >/dev/null 2>&1; then
  exec gst-launch-1.0 -v rtspsrc location="$rtsp_url" latency=100 ! \
    rtph264depay ! h264parse ! avdec_h264 ! autovideosink sync=false
fi

if command -v ffplay >/dev/null 2>&1; then
  exec ffplay -fflags nobuffer -flags low_delay -framedrop "$rtsp_url"
fi

echo "no viewer found. install gstreamer1.0-tools or ffmpeg/ffplay"
exit 1
