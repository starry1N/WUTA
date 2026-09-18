#!/usr/bin/env bash
# Standalone image viewer; never start camera, LiDAR or inference again.
set -eo pipefail
export PATH="/usr/bin:${PATH}"
IMAGE_VIEW_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE_VIEW_TOPIC="${1:-/camera/yolo/image_annotated}"
if [[ "${IMAGE_VIEW_TOPIC}" == '--help' || "${IMAGE_VIEW_TOPIC}" == '-h' ]]; then
    echo 'Usage: bash view_yolo_image.sh [/absolute/image/topic]'
    echo 'Default: /camera/yolo/image_annotated (YOLO boxes and confidence)'
    echo 'Raw image: /zed/zed_node/rgb/image_rect_color'
    exit 0
fi
[[ $# -le 1 && "${IMAGE_VIEW_TOPIC}" == /* ]] || { echo 'Expected one absolute ROS image topic' >&2; exit 2; }
export ROS_LOG_DIR="${IMAGE_VIEW_ROOT}/logs/image_view"
source /opt/ros/humble/setup.bash
echo "Displaying ${IMAGE_VIEW_TOPIC}; close the image window to exit."
exec ros2 run rqt_image_view rqt_image_view "${IMAGE_VIEW_TOPIC}"
