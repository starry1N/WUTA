#!/usr/bin/env python3
"""Build a fixed 1280x768 TensorRT INT8 engine from the supplied YOLOv8s P2 weights."""
import argparse
import os
from pathlib import Path
import shutil
import tempfile


ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "WUTA-FSD/ros2_ws/src/perception/camera_detection/models"
DEFAULT_MODEL = MODEL_DIR / "yolov8sp2.pt"
DEFAULT_CALIBRATION = Path("/home/wuta/BiaoDing/data/camera")
IMAGE_SUFFIXES = {".bmp", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--calibration-dir", type=Path, default=DEFAULT_CALIBRATION)
    parser.add_argument("--workspace", type=float, default=2.0, help="TensorRT workspace limit in GiB")
    parser.add_argument("--force", action="store_true", help="Replace the existing INT8 engine")
    args = parser.parse_args()
    model_path = args.model.expanduser().resolve()
    calibration_dir = args.calibration_dir.expanduser().resolve()
    output_path = model_path.with_name(model_path.stem + "-int8.engine")
    if not model_path.is_file():
        parser.error(f"Model weights not found: {model_path}")
    if not calibration_dir.is_dir():
        parser.error(f"Calibration directory not found: {calibration_dir}")
    if args.workspace <= 0:
        parser.error("--workspace must be positive")
    if output_path.exists() and not args.force:
        parser.error(f"Engine already exists: {output_path}; pass --force to replace it")
    images = sorted(path for path in calibration_dir.iterdir()
                    if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES)
    if len(images) < 8:
        parser.error(f"Need at least 8 representative calibration images, found {len(images)}")

    os.environ.setdefault("MPLCONFIGDIR", "/tmp/wuta-mpl")
    import torch
    import tensorrt as trt
    from ultralytics import YOLO
    import yaml

    if not torch.cuda.is_available():
        parser.error("CUDA is not available in the TensorRT Python environment")
    model = YOLO(str(model_path), task="detect")
    print(f"Ultralytics: {__import__('ultralytics').__version__}")
    print(f"TensorRT: {trt.__version__}; CUDA: {torch.version.cuda}")
    print(f"GPU: {torch.cuda.get_device_name(0)}")
    print(f"Model task/classes: {model.task} / {model.names}")
    print(f"Model architecture: {model.model.yaml.get('yaml_file')}; stride={model.model.stride.tolist()}")
    print(f"Calibration images: {len(images)} from {calibration_dir}")
    if model.task != "detect" or len(model.names) != 3:
        parser.error("Expected a three-class object detection model")
    class_names = [model.names[index] for index in range(len(model.names))]
    if class_names != ["red", "yellow", "blue"]:
        parser.error(f"Unexpected class order {class_names}; expected red/yellow/blue")

    with tempfile.TemporaryDirectory(prefix="wuta-yolov8-calib-", dir="/tmp") as temporary:
        temp_dir = Path(temporary)
        image_dir = temp_dir / "images"
        image_dir.mkdir()
        for index, source in enumerate(images):
            (image_dir / f"{index:05d}{source.suffix.lower()}").symlink_to(source)
        data_path = temp_dir / "calibration.yaml"
        data_path.write_text(yaml.safe_dump({
            "path": str(temp_dir), "train": "images", "val": "images",
            "nc": len(class_names), "names": class_names,
        }, sort_keys=False), encoding="utf-8")
        result = model.export(
            format="engine", imgsz=(768, 1280), batch=1, dynamic=False,
            quantize=8, data=str(data_path), fraction=1.0,
            workspace=args.workspace, simplify=True, device=0,
        )
    built_path = Path(result).resolve()
    if not built_path.is_file() or built_path.stat().st_size < 10_000_000:
        raise RuntimeError(f"TensorRT export returned an invalid engine: {built_path}")
    if built_path != output_path:
        if output_path.exists():
            output_path.unlink()
        shutil.move(str(built_path), output_path)
    print(f"ENGINE_PATH={output_path}")
    print(f"ENGINE_SIZE_BYTES={output_path.stat().st_size}")


if __name__ == "__main__":
    main()
