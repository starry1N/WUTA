#!/usr/bin/env python3
"""Build a fixed-shape, calibrated TensorRT INT8 LW-DETR engine."""
import argparse
from pathlib import Path

import cv2
import numpy as np
import tensorrt as trt
import torch


ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / 'WUTA-FSD/ros2_ws/src/perception/camera_detection/models'


def tensorize(image, height, width):
    h, w = image.shape[:2]
    scale = min(width / w, height / h)
    rw, rh = round(w * scale), round(h * scale)
    left, top = (width - rw) // 2, (height - rh) // 2
    canvas = np.full((height, width, 3), 114, dtype=np.uint8)
    canvas[top:top + rh, left:left + rw] = cv2.resize(image, (rw, rh))
    rgb = canvas[:, :, ::-1].astype(np.float32) / 255.0
    rgb = (rgb - np.array([0.485, 0.456, 0.406], np.float32)) / np.array(
        [0.229, 0.224, 0.225], np.float32)
    return np.ascontiguousarray(rgb.transpose(2, 0, 1)[None])


class Calibrator(trt.IInt8EntropyCalibrator2):
    def __init__(self, images, height, width, cache):
        super().__init__()
        self.images = images
        self.height, self.width = height, width
        self.cache = cache
        self.index = 0
        self.batch = None

    def get_batch_size(self):
        return 1

    def get_batch(self, names):
        if self.index >= len(self.images):
            return None
        image = cv2.imread(str(self.images[self.index]), cv2.IMREAD_COLOR)
        if image is None:
            raise RuntimeError(f'Cannot read calibration image {self.images[self.index]}')
        values = tensorize(image, self.height, self.width)
        self.batch = torch.from_numpy(values).to('cuda:0')
        self.index += 1
        return [int(self.batch.data_ptr())]

    def read_calibration_cache(self):
        return self.cache.read_bytes() if self.cache.is_file() else None

    def write_calibration_cache(self, cache):
        self.cache.write_bytes(cache)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--onnx', type=Path, default=MODEL_DIR / 'lwdetr-fp16.onnx')
    parser.add_argument('--output', type=Path, default=MODEL_DIR / 'lwdetr-int8.engine')
    parser.add_argument('--calibration-dir', type=Path, default=Path('/home/wuta/BiaoDing/data/camera'))
    parser.add_argument('--height', type=int, default=768)
    parser.add_argument('--width', type=int, default=1280)
    parser.add_argument('--workspace-gib', type=int, default=3)
    parser.add_argument('--max-calibration-images', type=int, default=32)
    args = parser.parse_args()
    images = sorted(args.calibration_dir.glob('*.png'))[:args.max_calibration_images]
    if len(images) < 8:
        raise RuntimeError(f'Need at least 8 representative PNG images, found {len(images)}')

    logger = trt.Logger(trt.Logger.INFO)
    builder = trt.Builder(logger)
    network = builder.create_network(1 << int(trt.NetworkDefinitionCreationFlag.EXPLICIT_BATCH))
    onnx_parser = trt.OnnxParser(network, logger)
    if not onnx_parser.parse(args.onnx.read_bytes()):
        details = '\n'.join(str(onnx_parser.get_error(i))
                            for i in range(onnx_parser.num_errors))
        raise RuntimeError('TensorRT could not parse the LW-DETR ONNX graph:\n' + details)
    config = builder.create_builder_config()
    config.set_memory_pool_limit(trt.MemoryPoolType.WORKSPACE,
                                 args.workspace_gib * 1024 ** 3)
    config.set_flag(trt.BuilderFlag.FP16)
    config.set_flag(trt.BuilderFlag.INT8)
    config.int8_calibrator = Calibrator(
        images, args.height, args.width, args.output.with_suffix('.calib'))
    print(f'Calibrating with {len(images)} frames; TensorRT {trt.__version__}; '
          f'input 1x3x{args.height}x{args.width}', flush=True)
    serialized = builder.build_serialized_network(network, config)
    if serialized is None:
        raise RuntimeError('TensorRT failed to build calibrated INT8 engine')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(bytes(serialized))
    print(f'Wrote {args.output} ({args.output.stat().st_size / 1024**2:.1f} MiB)')


if __name__ == '__main__':
    main()
