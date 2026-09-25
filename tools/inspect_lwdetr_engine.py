#!/usr/bin/env python3
"""Smoke-test the LW-DETR TensorRT backend on a camera image."""
import argparse
import sys
import time
from pathlib import Path

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'WUTA-FSD/ros2_ws/src/perception/camera_detection'))
from camera_detection.yolo import YoloModel, annotate


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--image', type=Path, default=Path('/home/wuta/BiaoDing/data/camera/0001.png'))
    parser.add_argument('--engine', type=Path, default=ROOT / 'WUTA-FSD/ros2_ws/src/perception/camera_detection/models/lwdetr-int8.engine')
    parser.add_argument('--output', type=Path, default=ROOT / 'logs/yolo_gpu/lwdetr.png')
    parser.add_argument('--runs', type=int, default=20)
    args = parser.parse_args()
    image = cv2.imread(str(args.image), cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError(f'Cannot read {args.image}')
    model = YoloModel(args.engine, red_color=3)
    timings, predictions = [], []
    for i in range(args.runs + 3):
        start = time.perf_counter()
        predictions = model.predict(image)
        elapsed = (time.perf_counter() - start) * 1000
        if i >= 3:
            timings.append(elapsed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(args.output), annotate(image, predictions,
                                                  f'LW-DETR INT8 | {len(predictions)} cones')):
        raise RuntimeError(f'Cannot write {args.output}')
    print(f'backend={model.backend} providers={model.providers} input={model.size}')
    print(f'detections={len(predictions)} ms median={np.median(timings):.2f} '
          f'min={min(timings):.2f} max={max(timings):.2f}')
    print(f'classes={model.names} output={args.output}')
    for box, probabilities, score in predictions:
        print(f'  score={score:.3f} box={np.rint(box).astype(int).tolist()} '
              f'probabilities={np.round(probabilities, 3).tolist()}')


if __name__ == '__main__':
    main()
