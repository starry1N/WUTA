#!/usr/bin/env bash
# Use the ROS-compatible system Python, and existing driver overlays from BiaoDing.
set -eo pipefail
export PATH="/usr/bin:${PATH}"
HARDWARE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WUTA_PROCESS_ROOT="${HARDWARE_ROOT}"
source "${HARDWARE_ROOT}/tools/wuta_process_manager.sh"
FSD_WS="${HARDWARE_ROOT}/WUTA-FSD/ros2_ws"
ZED_SETUP="${ZED_SETUP:-/home/wuta/WUTA/zed/install/setup.bash}"
RSLIDAR_SETUP="${RSLIDAR_SETUP:-/home/wuta/WUTA/rslidar_sdk/install/setup.bash}"
export ROS_LOG_DIR="${HARDWARE_ROOT}/logs/hardware"
export LD_LIBRARY_PATH="/usr/local/cuda-11.8/targets/x86_64-linux/lib:/home/wuta/WUTA/rslidar_sdk/install_msg/lib:${LD_LIBRARY_PATH:-}"
export PYTHONPATH="${HARDWARE_ROOT}/.hardware_deps:${PYTHONPATH:-}"
usage() {
    echo 'Usage: ./start_hardware_fusion.sh [options] [name:=value ...]'
    echo '  --rviz / --no-rviz       Enable / disable the live RViz view (default disabled)'
    echo '  --view-only             Open RViz for an existing pipeline; start no drivers/nodes'
    echo '  --image-view / --no-image-view  Open / disable image viewer in a separate terminal'
    echo '                                Default: open when RViz is requested'
    echo '  --image-view-topic TOPIC  Viewer image topic (default /camera/yolo/image_annotated)'
    echo '  --skip-build            Use already built perception packages'
    echo '  --build-only            Build perception packages without launching'
    echo '  --lightweight           Build C++ packages with one compiler job'
    echo '  --no-drivers            Use external camera/LiDAR drivers; start perception nodes'
    echo '  --model PATH            Override PT, ONNX, or engine weights (default best-new.engine)'
    echo '  --calibration PATH      Override camera-from-LiDAR YAML'
    echo '  --rviz-config PATH      Override live RViz configuration'
    echo '  --show-args             Print all ROS launch arguments without launching'
    echo 'ROS args: image_topic:=... lidar_topic:=... depth_topic:=... info_topic:=...'
    echo '  confidence_threshold:=0.5 inference_threads:=4 fusion_wait_sec:=1.2'
    echo '  model_input_width:=1280 model_input_height:=760 (best-new.engine defaults)'
    echo '  publish_annotated_image:=true red_color:=3 (red -> ORANGE)'
    echo '  device:=cuda gpu_device_id:=0 (CPU requires explicit device:=cpu)'
}
BUILD_ONLY=0
SKIP_BUILD=0
VIEW_ONLY=0
LIGHTWEIGHT=0
SHOW_ARGS=0
OPEN_IMAGE_VIEW=-1
IMAGE_VIEW_TOPIC=/camera/yolo/image_annotated
LIVE_RVIZ_CONFIG="${FSD_WS}/src/perception/detection_fusion/config/hardware.rviz"
LAUNCH_ARGS=("model_path:=${FSD_WS}/src/perception/camera_detection/models/best-new.engine"
    "calibration_path:=${FSD_WS}/src/perception/calibration/camera_lidar.yaml"
    "model_input_width:=1280" "model_input_height:=760")
set_launch_arg() {
    local name="${1%%:=*}" index
    for index in "${!LAUNCH_ARGS[@]}"; do
        if [[ "${LAUNCH_ARGS[index]}" == "${name}:="* ]]; then
            LAUNCH_ARGS[index]="$1"
            return
        fi
    done
    LAUNCH_ARGS+=("$1")
}
while [[ $# -gt 0 ]]; do
    case "$1" in
        --build-only) BUILD_ONLY=1; shift ;;
        --skip-build) SKIP_BUILD=1; shift ;;
        --lightweight) LIGHTWEIGHT=1; shift ;;
        --view-only) VIEW_ONLY=1; shift ;;
        --show-args) SHOW_ARGS=1; SKIP_BUILD=1; shift ;;
        --rviz) set_launch_arg launch_rviz:=true; shift ;;
        --no-rviz) set_launch_arg launch_rviz:=false; shift ;;
        --image-view) OPEN_IMAGE_VIEW=1; shift ;;
        --no-image-view) OPEN_IMAGE_VIEW=0; shift ;;
        --image-view-topic)
            [[ $# -ge 2 && "$2" == /* ]] || { echo '--image-view-topic requires an absolute ROS topic' >&2; exit 2; }
            IMAGE_VIEW_TOPIC="$2"; shift 2 ;;
        --no-drivers) set_launch_arg start_drivers:=false; shift ;;
        --model|--calibration|--rviz-config)
            [[ $# -ge 2 && "$2" != --* ]] || { echo "$1 requires a path" >&2; exit 2; }
            case "$1" in
                --model) set_launch_arg "model_path:=$(realpath -m -- "$2")" ;;
                --calibration) set_launch_arg "calibration_path:=$(realpath -m -- "$2")" ;;
                --rviz-config) LIVE_RVIZ_CONFIG="$(realpath -m -- "$2")" ;;
            esac
            shift 2 ;;
        --help|-h) usage; exit 0 ;;
        *:=*)
            if [[ "$1" == rviz_config:=* ]]; then
                LIVE_RVIZ_CONFIG="$(realpath -m -- "${1#rviz_config:=}")"
            else
                set_launch_arg "$1"
            fi
            shift ;;
        *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
    esac
done
set_launch_arg "rviz_config:=${LIVE_RVIZ_CONFIG}"
RVIZ_REQUESTED="${VIEW_ONLY}"
for arg in "${LAUNCH_ARGS[@]}"; do
    case "${arg}" in
        launch_rviz:=true) RVIZ_REQUESTED=1 ;;
        launch_rviz:=false) RVIZ_REQUESTED=0 ;;
    esac
done
[[ "${OPEN_IMAGE_VIEW}" == -1 ]] && OPEN_IMAGE_VIEW="${RVIZ_REQUESTED}"
open_image_terminal() {
    if command -v gnome-terminal >/dev/null; then
        gnome-terminal --title='WUTA YOLO Image' -- bash "${HARDWARE_ROOT}/view_yolo_image.sh" "${IMAGE_VIEW_TOPIC}"
    else
        echo 'gnome-terminal is unavailable. Run the image viewer in another terminal:' >&2
        echo "bash ${HARDWARE_ROOT}/view_yolo_image.sh ${IMAGE_VIEW_TOPIC}" >&2
        return 1
    fi
}
source /opt/ros/humble/setup.bash
if [[ "${VIEW_ONLY}" == 1 ]]; then
    [[ "${BUILD_ONLY}" == 0 && "${SHOW_ARGS}" == 0 ]] || { echo '--view-only conflicts with --build-only/--show-args' >&2; exit 2; }
    [[ -f "${LIVE_RVIZ_CONFIG}" ]] || { echo "Missing RViz config: ${LIVE_RVIZ_CONFIG}" >&2; exit 1; }
    [[ "${OPEN_IMAGE_VIEW}" == 0 ]] || open_image_terminal
    if [[ "${RVIZ_REQUESTED}" == 1 ]]; then
        exec rviz2 -d "${LIVE_RVIZ_CONFIG}"
    fi
    exit 0
fi
if [[ "${BUILD_ONLY}" == 0 && "${SHOW_ARGS}" == 0 ]]; then
    wuta_stop_previous_stack
fi
if [[ "${SKIP_BUILD}" == 0 ]]; then
    HARDWARE_CMAKE_ARGS=(-DCMAKE_BUILD_TYPE=Release -DPython3_EXECUTABLE=/usr/bin/python3
        -DPYTHON_EXECUTABLE=/usr/bin/python3 -DPYTHON_INCLUDE_DIR=/usr/include/python3.10
        -DPYTHON_LIBRARY=/usr/lib/x86_64-linux-gnu/libpython3.10.so)
    if [[ "${LIGHTWEIGHT}" == 1 ]]; then
        export CMAKE_BUILD_PARALLEL_LEVEL=1
    fi
    (cd "${FSD_WS}" && colcon build --symlink-install --parallel-workers 1 \
        --packages-up-to detection_fusion --cmake-args "${HARDWARE_CMAKE_ARGS[@]}")
fi
[[ "${BUILD_ONLY}" == 1 ]] && exit 0
for setup in "${ZED_SETUP}" "${RSLIDAR_SETUP}" "${FSD_WS}/install/setup.bash"; do
    [[ -f "${setup}" ]] || { echo "Missing overlay: ${setup}" >&2; exit 1; }
    source "${setup}"
done
if [[ "${SHOW_ARGS}" == 1 ]]; then
    exec ros2 launch detection_fusion fusion_hardware.launch.py "${LAUNCH_ARGS[@]}" --show-args
fi
# A non-WUTA process may still own the sensor ports after the old stack is gone.
START_DRIVERS=1
for arg in "${LAUNCH_ARGS[@]}"; do
    [[ "${arg}" == start_drivers:=false ]] && START_DRIVERS=0
done
if [[ "${START_DRIVERS}" == 1 ]] && command -v ss >/dev/null; then
    DRIVER_PORTS="$(ss -H -uln 'sport = :6699 or sport = :7788')"
    if [[ -n "${DRIVER_PORTS}" ]]; then
        echo 'M1 UDP ports 6699/7788 are still owned by a process outside the previous WUTA launch.' >&2
        echo 'Stop that process, use --view-only, or use --no-drivers with one external driver pair.' >&2
        exit 1
    fi
fi
[[ "${OPEN_IMAGE_VIEW}" == 0 ]] || open_image_terminal
wuta_register_stack "$$" hardware_fusion
exec ros2 launch detection_fusion fusion_hardware.launch.py \
    "${LAUNCH_ARGS[@]}"
