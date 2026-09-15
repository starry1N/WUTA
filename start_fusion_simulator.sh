#!/usr/bin/env bash
# Independent entry; hardware drivers and YOLO inference are not started here.
set -euo pipefail
FUSION_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FUSION_SKIP_BUILD=0
FUSION_BUILD_ARGS=()
FUSION_LAUNCH_ARGS=()
for arg in "$@"; do
  case "$arg" in
    --skip-build) FUSION_SKIP_BUILD=1 ;;
    --lightweight) FUSION_BUILD_ARGS+=(--lightweight) ;;
    --rviz) FUSION_LAUNCH_ARGS+=(launch_rviz:=true) ;;
    --help|-h)
      echo 'Usage: ./start_fusion_simulator.sh [--skip-build] [--lightweight] [--rviz] [name:=value ...]'
      echo 'Examples: track_file:=track6 mission_mode:=trackdrive launch_rviz:=false'
      exit 0 ;;
    *:=*) FUSION_LAUNCH_ARGS+=("$arg") ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done
if (( ! FUSION_SKIP_BUILD )); then
  bash "${FUSION_ROOT}/start_simulator.sh" --build-only "${FUSION_BUILD_ARGS[@]}"
fi
set +u
source /opt/ros/humble/setup.bash
source "${FUSION_ROOT}/WUTA-FSD/ros2_ws/install/setup.bash"
source "${FUSION_ROOT}/WUTA-SIM/install/setup.bash"
set -u
# A GUI environment must not silently replace the dedicated mode's parameters.
unset WUTA_PARAMS_FILE
exec ros2 launch simulator_bringup fusion_simulator.launch.py "${FUSION_LAUNCH_ARGS[@]}"
