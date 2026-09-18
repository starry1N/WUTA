#!/usr/bin/python3
"""Benchmark CUDA inference and save the matching annotated camera frame."""
import argparse
from collections import Counter
import json
from pathlib import Path
import time

import cv2
import numpy as np

from camera_detection.yolo import YoloModel, annotate, image_bgr, letterbox


def capture(topic):
    import rclpy
    from rclpy.qos import qos_profile_sensor_data
    from sensor_msgs.msg import Image
    rclpy.init()
    node = rclpy.create_node('yolo_gpu_snapshot')
    frames = []
    node.create_subscription(Image, topic, frames.append, qos_profile_sensor_data)
    deadline = time.monotonic() + 20
    try:
        while not frames and time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.1)
        if not frames:
            raise RuntimeError('No image received on ' + topic)
        return image_bgr(frames[0])
    finally:
        node.destroy_node()
        rclpy.shutdown()


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument('--image')
    parser.add_argument('--topic', default='/zed/zed_node/rgb/image_rect_color')
    parser.add_argument('--capture-only', action='store_true', help='Save the source image before testing GPU')
    parser.add_argument('--device', choices=['cuda', 'cpu'], default='cuda')
    parser.add_argument('--output', default=str(root / 'logs/yolo_gpu/live.png'))
    parser.add_argument('--model', default=str(root / 'WUTA-FSD/ros2_ws/src/perception/camera_detection/models/best-new.engine'))
    parser.add_argument('--input-width', type=int, default=1280)
    parser.add_argument('--input-height', type=int, default=760)
    args = parser.parse_args()
    image = cv2.imread(args.image) if args.image else capture(args.topic)
    if image is None:
        raise ValueError('Failed to read image')
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if args.capture_only:
        if not cv2.imwrite(str(output_path), image):
            raise RuntimeError('Failed to save source image')
        print(str(output_path))
        return
    if min(args.input_width, args.input_height) < 0 or ((args.input_width == 0) != (args.input_height == 0)):
        raise ValueError('--input-width and --input-height must both be zero or positive')
    input_size = (args.input_height, args.input_width) if args.input_height else None
    model = YoloModel(args.model, red_color=3, device=args.device,
                      profile_prefix=output_path.parent / ('ort_' + args.device),
                      input_size=input_size)
    model.predict(image)  # Warm up CUDA kernels and allocations.
    durations = []
    for _ in range(10):
        started = time.monotonic()
        predictions = model.predict(image)
        durations.append((time.monotonic() - started) * 1000)
    if model.backend in ('pytorch', 'tensorrt'):
        raw, _, _ = model.raw_output(image)
    else:
        tensor, _, _ = letterbox(image, model.size)
        raw = model.session.run(None, {model.input_name: tensor})[0]
    best_scores = raw[0, 4:].max(axis=1).tolist()
    median = float(np.median(durations))
    device_label = 'CUDA GPU 0' if args.device == 'cuda' else 'CPU'
    rendered = annotate(image, predictions, f'YOLO {device_label} | cones: {len(predictions)} | {median:.0f} ms')
    if not cv2.imwrite(str(output_path), rendered):
        raise RuntimeError('Failed to save visualization')
    profile_path = None
    events = []
    if model.backend == 'onnxruntime':
        profile_path = model.session.end_profiling()
        with open(profile_path, encoding='utf-8') as stream:
            events = json.load(stream)
    kernel_providers = Counter(event.get('args', {}).get('provider') for event in events
        if event.get('cat') == 'Node' and event.get('args', {}).get('provider'))
    if model.backend == 'onnxruntime' and args.device == 'cuda' and not kernel_providers['CUDAExecutionProvider']:
        raise RuntimeError('Profile contains no CUDA kernel events')
    print(json.dumps(dict(device=args.device, backend=model.backend, providers=model.providers,
        input_size=list(model.size), median_ms=median,
        min_ms=min(durations), max_ms=max(durations), detections=len(predictions),
        max_class_scores=dict(zip(model.names.values(), best_scores)),
        kernel_events=dict(kernel_providers),
        image=str(output_path), profile=profile_path), indent=2))


if __name__ == '__main__':
    main()
