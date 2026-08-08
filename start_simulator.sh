#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FSD_WS="${ROOT_DIR}/WUTA-FSD/ros2_ws"
SIM_WS="${ROOT_DIR}/WUTA-SIM"
FSD_BUILD_SCRIPT="${FSD_WS}/build_ws.sh"
DEFAULT_CONFIG_FILE="${ROOT_DIR}/config/simulator_defaults.yaml"

CLEAN=0
SKIP_BUILD=0
BUILD_ONLY=0
LIGHTWEIGHT=0
LAUNCH_ARGS=()
CONFIG_FILE="${DEFAULT_CONFIG_FILE}"
PARAMS_FILE=""

usage() {
  cat <<'EOF'
Usage: ./start_simulator.sh [options] [--] [ROS launch arguments]

Build WUTA-FSD, build the simulator overlay, then launch simulator_bringup.

Options:
  --clean       Clean both workspaces before building.
  --skip-build  Skip all builds and use the existing install spaces.
  --build-only  Build both workspaces without starting ROS nodes.
  --lightweight Limit parallel jobs (for systems with <=8GB RAM).
  --rviz        Start RViz2 with the default simulator visualization config.
  --config PATH Load build and launch defaults from a YAML config file.
  --params-file PATH Load node parameters from YAML file after launch.
  -h, --help    Show this help.

Examples:
  ./start_simulator.sh
  ./start_simulator.sh --rviz
  ./start_simulator.sh launch_fsd:=false
  ./start_simulator.sh track_file:=skidpad mission_mode:=skidpad
  ./start_simulator.sh --config config/simulator_defaults.yaml --rviz
  ./start_simulator.sh --clean --build-only
EOF
}

set_launch_arg() {
  local argument="$1"
  if [[ "${argument}" != *":="* ]]; then
    echo "Invalid ROS launch argument: ${argument} (expected name:=value)" >&2
    exit 2
  fi

  local name="${argument%%:=*}"
  local index
  for index in "${!LAUNCH_ARGS[@]}"; do
    if [[ "${LAUNCH_ARGS[index]}" == "${name}:="* ]]; then
      LAUNCH_ARGS[index]="${argument}"
      return
    fi
  done
  LAUNCH_ARGS+=("${argument}")
}

# Resolve --config and --params-file before loading defaults so every later
# command-line launch argument can override the selected configuration.
for ((index = 1; index <= $#; ++index)); do
  case "${!index}" in
    --config)
      next_index=$((index + 1))
      if (( next_index > $# )); then
        echo "--config requires a YAML file path." >&2
        exit 2
      fi
      CONFIG_FILE="${!next_index}"
      ;;
    --config=*)
      CONFIG_FILE="${!index#--config=}"
      ;;
    --params-file)
      next_index=$((index + 1))
      if (( next_index > $# )); then
        echo "--params-file requires a YAML file path." >&2
        exit 2
      fi
      PARAMS_FILE="${!next_index}"
      ;;
    --params-file=*)
      PARAMS_FILE="${!index#--params-file=}"
      ;;
  esac
done

if [[ ! -f "${CONFIG_FILE}" ]]; then
  echo "Simulator defaults config not found: ${CONFIG_FILE}" >&2
  exit 1
fi

CONFIG_ENTRIES="$(python3 -c '
import re
import sys

with open(sys.argv[1], encoding="utf-8") as stream:
    lines = list(stream)

section = None
found_sections = set()
for number, raw in enumerate(lines, start=1):
    line = raw.rstrip()
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        continue
    section_match = re.fullmatch(r"(build|launch_arguments):\s*(?:#.*)?", stripped)
    if section_match:
        section = section_match.group(1)
        found_sections.add(section)
        continue
    item_match = re.fullmatch(r"  ([A-Za-z_][A-Za-z0-9_]*):\s*(.*?)\s*(?:#.*)?", line)
    if section is None or not item_match:
        raise ValueError(f"unsupported YAML at line {number}")
    name, value = item_match.groups()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("\"", chr(39)):
        value = value[1:-1]
    if not value:
        raise ValueError(f"empty value at line {number}")
    if value.lower() in {"true", "false"}:
        value = value.lower()
    if section == "build":
        print(f"build.{name}={value}")
    else:
        print(f"launch={name}:={value}")

if found_sections != {"build", "launch_arguments"}:
    raise ValueError("config requires build and launch_arguments sections")
' "${CONFIG_FILE}")" || {
  echo "Unable to parse simulator defaults config: ${CONFIG_FILE}" >&2
  exit 1
}

while IFS= read -r entry; do
  case "${entry}" in
    build.clean=*) CLEAN="${entry#*=}" ;;
    build.skip_build=*) SKIP_BUILD="${entry#*=}" ;;
    build.build_only=*) BUILD_ONLY="${entry#*=}" ;;
    launch=*)
      argument="${entry#launch=}"
      if [[ "${argument}" == rviz_config:=* && "${argument#rviz_config:=}" != /* ]]; then
        argument="rviz_config:=${ROOT_DIR}/${argument#rviz_config:=}"
      fi
      set_launch_arg "${argument}"
      ;;
    *)
      echo "Unsupported config key: ${entry%%=*}" >&2
      exit 1
      ;;
  esac
done <<< "${CONFIG_ENTRIES}"

for variable in CLEAN SKIP_BUILD BUILD_ONLY; do
  if [[ "${!variable}" != "0" && "${!variable}" != "1" &&
        "${!variable}" != "true" && "${!variable}" != "false" ]]; then
    echo "${variable} must be true/false in ${CONFIG_FILE}" >&2
    exit 1
  fi
  [[ "${!variable}" == "true" ]] && printf -v "${variable}" '%s' 1
  [[ "${!variable}" == "false" ]] && printf -v "${variable}" '%s' 0
done

while [[ $# -gt 0 ]]; do
  case "$1" in
    --clean)
      CLEAN=1
      shift
      ;;
    --skip-build)
      SKIP_BUILD=1
      shift
      ;;
    --build-only)
      BUILD_ONLY=1
      shift
      ;;
    --lightweight)
      LIGHTWEIGHT=1
      shift
      ;;
    --rviz)
      set_launch_arg "launch_rviz:=true"
      shift
      ;;
    --config)
      shift 2
      ;;
    --config=*)
      shift
      ;;
    --params-file)
      shift 2
      ;;
    --params-file=*)
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --)
      shift
      for argument in "$@"; do
        set_launch_arg "${argument}"
      done
      break
      ;;
    *)
      set_launch_arg "$1"
      shift
      ;;
  esac
done

if [[ ! -x "${FSD_BUILD_SCRIPT}" ]]; then
  echo "WUTA-FSD build script is missing or not executable:" >&2
  echo "  ${FSD_BUILD_SCRIPT}" >&2
  exit 1
fi

if [[ ! -f "/opt/ros/${ROS_DISTRO:-humble}/setup.bash" ]]; then
  echo "ROS 2 setup file not found for ROS_DISTRO=${ROS_DISTRO:-humble}." >&2
  exit 1
fi

if [[ "${SKIP_BUILD}" -eq 0 ]]; then
  echo "[1/2] Building the complete WUTA-FSD workspace..."
  
  # 构建 FSD 参数
  FSD_BUILD_ARGS=""
  if [[ "${CLEAN}" -eq 1 ]]; then
    FSD_BUILD_ARGS="--clean"
    rm -rf "${SIM_WS}/build" "${SIM_WS}/install" "${SIM_WS}/log"
    find "${SIM_WS}" -mindepth 2 -maxdepth 5 -type d \
      \( -name "build" -o -name "install" -o -name "log" -o -name "__pycache__" \) \
      -exec rm -rf {} + 2>/dev/null || true
    find "${FSD_WS}" -mindepth 3 -maxdepth 6 -type d -name "__pycache__" \
      -exec rm -rf {} + 2>/dev/null || true
  fi
  if [[ "${LIGHTWEIGHT}" -eq 1 ]]; then
    FSD_BUILD_ARGS="${FSD_BUILD_ARGS} --lightweight"
  fi
  
  (cd "${FSD_WS}" && ./build_ws.sh ${FSD_BUILD_ARGS})

  set +u
  source "${FSD_WS}/install/setup.bash"
  set -u

  echo "[2/2] Building the simulator overlay..."
  (
    cd "${SIM_WS}"
    if [[ "${LIGHTWEIGHT}" -eq 1 ]]; then
      colcon build \
        --base-paths . \
        --symlink-install \
        --parallel-workers 1 \
        --packages-up-to simulator_bringup
    else
      colcon build \
        --base-paths . \
        --symlink-install \
        --packages-up-to simulator_bringup
    fi
  )
fi

if [[ ! -f "${FSD_WS}/install/setup.bash" ]]; then
  echo "WUTA-FSD is not built: ${FSD_WS}/install/setup.bash is missing." >&2
  exit 1
fi

if [[ ! -f "${SIM_WS}/install/setup.bash" ]]; then
  echo "Simulator overlay is not built: ${SIM_WS}/install/setup.bash is missing." >&2
  exit 1
fi

set +u
source "${FSD_WS}/install/setup.bash"
source "${SIM_WS}/install/setup.bash"
set -u

if [[ "${BUILD_ONLY}" -eq 1 ]]; then
  echo "Build complete. Simulator launch skipped (--build-only)."
  exit 0
fi

# 通过环境变量把用户参数文件注入 launch：节点启动时即带参数，
# 无需启动后再逐个 ros2 param load（启动即生效，且不依赖 DDS 发现）。
if [[ -n "${PARAMS_FILE}" ]] && [[ -f "${PARAMS_FILE}" ]]; then
  export WUTA_PARAMS_FILE="${PARAMS_FILE}"
  echo "Injecting user parameters from ${PARAMS_FILE} at launch time"
fi

echo "Starting simulator_bringup..."
cd "${ROOT_DIR}"

# Launch simulator in background
ros2 launch simulator_bringup simulator.launch.py "${LAUNCH_ARGS[@]}" &
LAUNCH_PID=$!

# Wait for the launch process to finish
wait $LAUNCH_PID
exit $?
