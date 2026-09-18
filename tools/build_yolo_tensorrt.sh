#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="/home/wuta/miniconda3/envs/tensorrt/bin/python"
MODEL_PATH="$ROOT_DIR/WUTA-FSD/ros2_ws/src/perception/camera_detection/models/best-new.pt"
WORKSPACE_GB=4
MONITOR_INTERVAL=5
FORCE=0
CHECK_ONLY=0

usage() {
    cat <<'EOF'
Build a fixed-shape TensorRT FP16 engine for the WUTA camera model.

Usage:
  tools/build_yolo_tensorrt.sh [options]

Options:
  --model PATH             PT model (default: best-new.pt)
  --workspace GB           TensorRT workspace limit (default: 4)
  --monitor-interval SEC   GPU status interval (default: 5)
  --force                  Replace an existing .engine file
  --check-only             Check the environment without building
  -h, --help               Show this help

The input is fixed at batch 1, 3 channels, 768x1280 (the stride-aligned
representation of the 1280x760 training/camera input). The script writes:
  logs/tensorrt/<timestamp>/build.log
  logs/tensorrt/<timestamp>/gpu.csv
EOF
}

while (($#)); do
    case "$1" in
        --model)
            MODEL_PATH="$2"
            shift 2
            ;;
        --workspace)
            WORKSPACE_GB="$2"
            shift 2
            ;;
        --monitor-interval)
            MONITOR_INTERVAL="$2"
            shift 2
            ;;
        --force)
            FORCE=1
            shift
            ;;
        --check-only)
            CHECK_ONLY=1
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

if [[ ! -x "$PYTHON_BIN" ]]; then
    echo "TensorRT Python environment not found: $PYTHON_BIN" >&2
    exit 1
fi
if [[ ! -f "$MODEL_PATH" ]]; then
    echo "Model not found: $MODEL_PATH" >&2
    exit 1
fi
if ! [[ "$WORKSPACE_GB" =~ ^[0-9]+([.][0-9]+)?$ ]] || ! [[ "$MONITOR_INTERVAL" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
    echo "--workspace and --monitor-interval must be positive numbers" >&2
    exit 2
fi

MODEL_PATH="$(realpath "$MODEL_PATH")"
ENGINE_PATH="${MODEL_PATH%.pt}.engine"
if [[ "$ENGINE_PATH" == "$MODEL_PATH" ]]; then
    echo "Model must have a .pt suffix: $MODEL_PATH" >&2
    exit 2
fi

export PYTHONNOUSERSITE=1

echo "Checking TensorRT and CUDA..."
"$PYTHON_BIN" - "$MODEL_PATH" <<'PY'
import sys
from pathlib import Path

import tensorrt as trt
import torch
from ultralytics import YOLO

model_path = Path(sys.argv[1])
print(f"  Python:     {sys.executable}")
print(f"  TensorRT:   {trt.__version__}")
print(f"  PyTorch:    {torch.__version__} (CUDA {torch.version.cuda})")
print(f"  CUDA ready: {torch.cuda.is_available()}")
if not torch.cuda.is_available():
    raise SystemExit("CUDA is unavailable in the TensorRT environment")
print(f"  GPU:        {torch.cuda.get_device_name(0)}")
loaded = YOLO(str(model_path), task="detect")
print(f"  Classes:    {loaded.names}")
PY

if ((CHECK_ONLY)); then
    exit 0
fi
if [[ -e "$ENGINE_PATH" && "$FORCE" -ne 1 ]]; then
    echo "Engine already exists: $ENGINE_PATH" >&2
    echo "Use --force to rebuild it." >&2
    exit 1
fi

RUN_STAMP="$(date +%Y%m%d-%H%M%S)"
RUN_DIR="$ROOT_DIR/logs/tensorrt/$RUN_STAMP"
BUILD_LOG="$RUN_DIR/build.log"
GPU_LOG="$RUN_DIR/gpu.csv"
mkdir -p "$RUN_DIR"
printf '%s\n' 'wall_time,elapsed_s,gpu_util,memory_used,memory_total,temperature,power_draw' > "$GPU_LOG"

BUILD_STARTED=$SECONDS
monitor_gpu() {
    while true; do
        local elapsed sample
        elapsed=$((SECONDS - BUILD_STARTED))
        if sample="$(nvidia-smi --query-gpu=timestamp,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw --format=csv,noheader,nounits 2>/dev/null | head -n 1)"; then
            printf '%s,%s\n' "$sample" "$elapsed" | awk -F, 'BEGIN {OFS=","} {print $1,$7,$2,$3,$4,$5,$6}' >> "$GPU_LOG"
            printf '[monitor] elapsed=%4ss | GPU=%s | memory=%s/%s MiB | temp=%s C | power=%s W\n' \
                "$elapsed" \
                "$(cut -d, -f2 <<<"$sample" | xargs)" \
                "$(cut -d, -f3 <<<"$sample" | xargs)" \
                "$(cut -d, -f4 <<<"$sample" | xargs)" \
                "$(cut -d, -f5 <<<"$sample" | xargs)" \
                "$(cut -d, -f6 <<<"$sample" | xargs)"
        else
            printf '[monitor] elapsed=%4ss | nvidia-smi unavailable\n' "$elapsed"
        fi
        sleep "$MONITOR_INTERVAL"
    done
}

MONITOR_PID=''
cleanup() {
    if [[ -n "$MONITOR_PID" ]]; then
        kill "$MONITOR_PID" 2>/dev/null || true
        wait "$MONITOR_PID" 2>/dev/null || true
    fi
}
trap cleanup EXIT INT TERM

echo "Building TensorRT FP16 engine"
echo "  Model:      $MODEL_PATH"
echo "  Input:      1x3x768x1280"
echo "  Workspace:  ${WORKSPACE_GB} GiB"
echo "  Engine:     $ENGINE_PATH"
echo "  Build log:  $BUILD_LOG"
echo "  GPU log:    $GPU_LOG"
echo "The first build can spend several minutes selecting TensorRT tactics."

monitor_gpu &
MONITOR_PID=$!

export WUTA_TRT_MODEL="$MODEL_PATH"
export WUTA_TRT_WORKSPACE="$WORKSPACE_GB"
set +e
"$PYTHON_BIN" -u - <<'PY' 2>&1 | tee "$BUILD_LOG"
import os
from pathlib import Path

from ultralytics import YOLO

model_path = Path(os.environ["WUTA_TRT_MODEL"])
workspace = float(os.environ["WUTA_TRT_WORKSPACE"])
result = YOLO(str(model_path), task="detect").export(
    format="engine",
    imgsz=(768, 1280),
    batch=1,
    dynamic=False,
    half=True,
    workspace=workspace,
    simplify=True,
    device=0,
)
print(f"ENGINE_PATH={Path(result).resolve()}")
PY
BUILD_STATUS=${PIPESTATUS[0]}
set -e

cleanup
MONITOR_PID=''

if ((BUILD_STATUS != 0)); then
    echo "TensorRT build failed with status $BUILD_STATUS. See: $BUILD_LOG" >&2
    exit "$BUILD_STATUS"
fi
if [[ ! -s "$ENGINE_PATH" ]]; then
    echo "Build returned success but engine is missing: $ENGINE_PATH" >&2
    exit 1
fi

echo "Build complete in $((SECONDS - BUILD_STARTED)) seconds"
ls -lh "$ENGINE_PATH"
echo "Build log: $BUILD_LOG"
echo "GPU log:   $GPU_LOG"
