#!/usr/bin/env python3
"""Collect TensorRT per-layer latency for the LW-DETR engine."""
import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np
import tensorrt as trt


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'WUTA-FSD/ros2_ws/src/perception/camera_detection'))
from camera_detection.yolo import YoloModel


class LayerProfiler(trt.IProfiler):
    def __init__(self):
        super().__init__()
        self.samples = []

    def report_layer_time(self, layer_name, ms):
        self.samples.append((str(layer_name), float(ms)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--image', type=Path, default=Path('/home/wuta/BiaoDing/data/camera/0001.png'))
    parser.add_argument('--engine', type=Path, default=ROOT / 'WUTA-FSD/ros2_ws/src/perception/camera_detection/models/lwdetr-int8.engine')
    parser.add_argument('--output', type=Path, default=ROOT / 'logs/yolo_gpu/lwdetr_layer_profile.csv')
    parser.add_argument('--runs', type=int, default=10)
    args = parser.parse_args()
    image = cv2.imread(str(args.image), cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError(f'Cannot read {args.image}')

    model = YoloModel(args.engine, red_color=3)
    profiler = LayerProfiler()
    model.context.profiler = profiler
    for _ in range(2):
        model.predict(image)
        model.context.report_to_profiler()
    profiler.samples.clear()

    per_layer = defaultdict(list)
    for _ in range(args.runs):
        model.predict(image)
        model.context.report_to_profiler()
        for name, ms in profiler.samples:
            per_layer[name].append(ms)
        profiler.samples.clear()

    rows = []
    for name, samples in per_layer.items():
        rows.append({'layer': name, 'avg_ms': float(np.mean(samples)),
                     'min_ms': float(np.min(samples)), 'max_ms': float(np.max(samples)),
                     'samples': len(samples)})
    rows.sort(key=lambda row: row['avg_ms'], reverse=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=['layer', 'avg_ms', 'min_ms', 'max_ms', 'samples'])
        writer.writeheader()
        writer.writerows(rows)

    inspector = model.engine.create_engine_inspector()
    inspector.execution_context = model.context
    details = inspector.get_engine_information(trt.LayerInformationFormat.JSON)
    detail_path = args.output.with_suffix('.json')
    detail_path.write_text(details, encoding='utf-8')
    total = sum(row['avg_ms'] for row in rows)
    print(f'TensorRT={trt.__version__} profiling_verbosity={model.engine.profiling_verbosity}')
    print(f'layers={len(rows)} measured_runs={args.runs} sum_layer_avg={total:.3f} ms')
    print(f'CSV={args.output}\nENGINE_INFO={detail_path}')
    print('Top 30 layers (avg ms):')
    for row in rows[:30]:
        print(f"{row['avg_ms']:8.4f}  {row['layer']}")


if __name__ == '__main__':
    main()
