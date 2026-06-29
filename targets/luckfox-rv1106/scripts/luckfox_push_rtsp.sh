#!/usr/bin/env bash
set -euo pipefail

# Push /dev/video0 stream to Raspberry Pi RTSP server.
# Requires ffmpeg on Luckfox image.

raspi_ip="${1:-${RASPI_IP:-192.168.0.20}}"
stream_name="${RTSP_STREAM_NAME:-luckfox}"
video_dev="${VIDEO_DEV:-/dev/video0}"
fps="${VIDEO_FPS:-15}"
size="${VIDEO_SIZE:-1280x720}"
bitrate="${VIDEO_BITRATE:-1500k}"

rtsp_url="${RTSP_URL:-rtsp://${raspi_ip}:8554/${stream_name}}"

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "ffmpeg not found on Luckfox"
  exit 1
fi

if [[ ! -e "$video_dev" ]]; then
  echo "video device not found: $video_dev"
  exit 1
fi

echo "[rtsp-push] source=$video_dev"
echo "[rtsp-push] url=$rtsp_url"
echo "[rtsp-push] fps=$fps size=$size bitrate=$bitrate"

exec ffmpeg -hide_banner -loglevel warning \
  -f v4l2 -framerate "$fps" -video_size "$size" -i "$video_dev" \
  -an -c:v libx264 -preset veryfast -tune zerolatency -b:v "$bitrate" \
  -f rtsp -rtsp_transport tcp "$rtsp_url"
