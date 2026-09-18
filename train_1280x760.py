"""Train YOLOv8m on an already prepared 1280x760 YOLO detection dataset.

Linux example:
    python train_1280x760.py --data datasets/VOC2022_1280x760/data.yaml

The dataset must already contain 1280x760 letterboxed images and adjusted
YOLO labels. YOLOv8 pads the 760-pixel height to 768 during training.
"""

import argparse
import json
import subprocess
import time
from datetime import timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DEFAULT_DATA = ROOT / "datasets" / "VOC2022_1280x760" / "data.yaml"
TARGET_SIZE = (1280, 760)


def gpu_snapshot():
    """Read utilization, memory and temperature from nvidia-smi if available."""
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=index,utilization.gpu,memory.used,memory.total,temperature.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=3,
            check=True,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return []
    snapshots = []
    for line in result.stdout.splitlines():
        values = [value.strip() for value in line.split(",")]
        if len(values) == 5:
            try:
                index, utilization, used, total, temperature = map(int, values)
                snapshots.append({
                    "index": index,
                    "utilization_pct": utilization,
                    "memory_used_mib": used,
                    "memory_total_mib": total,
                    "temperature_c": temperature,
                })
            except ValueError:
                continue
    return snapshots


def make_epoch_monitor(total_epochs):
    started = time.monotonic()
    previous_epoch = -1

    def on_fit_epoch_end(trainer):
        nonlocal previous_epoch
        epoch = trainer.epoch + 1
        # Ultralytics may call this callback again during final validation.
        if epoch <= previous_epoch or epoch > total_epochs:
            return
        previous_epoch = epoch

        elapsed = time.monotonic() - started
        eta = elapsed / epoch * max(total_epochs - epoch, 0)
        losses = trainer.label_loss_items(trainer.tloss, prefix="train") if trainer.tloss is not None else {}
        metrics = trainer.metrics or {}
        rates = trainer.lr or {}
        record = {
            "epoch": epoch,
            "total_epochs": total_epochs,
            "elapsed_seconds": round(elapsed, 1),
            "eta_seconds": round(eta, 1),
            "train": {key: float(value) for key, value in losses.items()},
            "validation": {key: float(value) for key, value in metrics.items() if isinstance(value, (int, float))},
            "learning_rates": {key: float(value) for key, value in rates.items()},
            "gpus": gpu_snapshot(),
        }
        monitor_file = Path(trainer.save_dir) / "monitor.jsonl"
        with monitor_file.open("a", encoding="utf-8") as output:
            output.write(json.dumps(record, ensure_ascii=False) + "\n")

        values = {**record["train"], **record["validation"]}
        summary = " | ".join(f"{key}={value:.4f}" for key, value in values.items())
        gpu_text = " | ".join(
            f"GPU{gpu['index']} {gpu['utilization_pct']}%, "
            f"{gpu['memory_used_mib']}/{gpu['memory_total_mib']} MiB, {gpu['temperature_c']}°C"
            for gpu in record["gpus"]
        )
        print(
            f"\n[监控] Epoch {epoch}/{total_epochs} | 已运行 {timedelta(seconds=int(elapsed))} "
            f"| 预计剩余 {timedelta(seconds=int(eta))}\n"
            f"[指标] {summary}\n"
            f"[学习率] {record['learning_rates']}\n"
            f"[硬件] {gpu_text or 'nvidia-smi 不可用'}\n"
            f"[日志] {monitor_file}",
            flush=True,
        )

    return on_fit_epoch_end


def check_prepared_data(data_yaml):
    """Check source paths and one image per split without creating any dataset files."""
    import cv2
    import yaml

    config = yaml.safe_load(data_yaml.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError(f"Invalid dataset YAML: {data_yaml}")
    root = Path(config.get("path", data_yaml.parent))
    if not root.is_absolute():
        # Supports a path written relative to the project or to the YAML file.
        candidates = (ROOT / root, data_yaml.parent / root)
        root = next((candidate for candidate in candidates if candidate.is_dir()), candidates[0])

    for split in ("train", "val"):
        if split not in config:
            raise ValueError(f"Missing '{split}' in {data_yaml}")
        images = Path(config[split])
        if not images.is_absolute():
            images = root / images
        if not images.is_dir():
            raise FileNotFoundError(f"{split} images directory not found: {images}")
        first_image = next(
            (path for path in images.rglob("*") if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}),
            None,
        )
        if first_image is None:
            raise FileNotFoundError(f"No {split} images in {images}")
        image = cv2.imread(str(first_image))
        if image is None:
            raise RuntimeError(f"Cannot read image: {first_image}")
        height, width = image.shape[:2]
        if (width, height) != TARGET_SIZE:
            raise ValueError(
                f"{split} image {first_image} is {width}x{height}; expected 1280x760. "
                "Pass --data pointing to the already resized dataset YAML."
            )
        print(f"[数据集] {split}: {images}，抽查图像 {width}x{height}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA, help="YAML for the prepared 1280x760 dataset")
    parser.add_argument("--weights", type=Path, default=ROOT / "yolov8m.pt")
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--batch", type=int, default=16, help="RTX 5090 starting value; reduce to 8 if out of memory")
    parser.add_argument("--device", default="0")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    try:
        from ultralytics import YOLO
    except ImportError as exc:
        parser.error(f"Missing dependency: {exc}. Install ultralytics and a CUDA-compatible PyTorch build.")

    data_yaml = args.data.expanduser().resolve()
    weights = args.weights.expanduser().resolve()
    if not data_yaml.is_file():
        parser.error(f"Prepared dataset YAML not found: {data_yaml}. Pass its location with --data.")
    if not weights.is_file():
        parser.error(f"Pretrained weights not found: {weights}")
    check_prepared_data(data_yaml)

    model = YOLO(str(weights))
    model.add_callback("on_fit_epoch_end", make_epoch_monitor(args.epochs))
    print(
        f"[训练配置] 权重={weights} | 数据={data_yaml} | "
        f"图像=1280x760 | 训练张量=1280x768 | "
        f"epochs={args.epochs} | batch={args.batch} | device={args.device} | workers={args.workers}",
        flush=True,
    )
    model.train(
        data=str(data_yaml),
        imgsz=1280,
        rect=True,
        mosaic=0.0,
        multi_scale=0.0,
        epochs=args.epochs,
        batch=args.batch,
        device=args.device,
        workers=args.workers,
        amp=True,
        project=str(ROOT / "runs" / "detect"),
        name="yolov8m_1280x760",
    )


if __name__ == "__main__":
    main()
