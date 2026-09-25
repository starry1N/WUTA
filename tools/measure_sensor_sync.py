#!/usr/bin/env python3
"""Measure ROS header-time rates and nearest camera/LiDAR timestamp offsets."""

import argparse
import json
import time
from collections import Counter, defaultdict

import rclpy
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image, PointCloud2
from std_msgs.msg import String
from wuta_msgs.msg import CameraConeDetectionArray, ConeArray


def stamp_ns(message):
    stamp = message.header.stamp
    return stamp.sec * 1_000_000_000 + stamp.nanosec


def summarize(label, stamps):
    ordered = sorted(stamps)
    deltas = [(b - a) / 1e6 for a, b in zip(ordered, ordered[1:]) if b > a]
    if not deltas:
        print(f"{label}: messages={len(stamps)}, no positive timestamp intervals")
        return
    import numpy as np
    values = np.asarray(deltas)
    print(f"{label}: messages={len(stamps)}, rate={1000 / np.median(values):.2f} Hz, "
          f"interval_ms median/p95/p99/max="
          f"{np.percentile(values, 50):.2f}/{np.percentile(values, 95):.2f}/"
          f"{np.percentile(values, 99):.2f}/{np.max(values):.2f}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration", type=float, default=20.0)
    parser.add_argument("--image-topic", default="/zed/zed_node/rgb/image_rect_color")
    parser.add_argument("--cloud-topic", default="/rslidar_points")
    parser.add_argument("--yolo-topic", default="/camera/yolo/cones")
    parser.add_argument("--camera-topic", default="/perception/camera/cones")
    parser.add_argument("--lidar-topic", default="/perception/lidar/cones_raw")
    parser.add_argument("--status-topic", default="/perception/camera/yolo/status")
    parser.add_argument("--fusion-status-topic", default="/perception/fusion/status")
    args = parser.parse_args()

    rclpy.init()
    node = rclpy.create_node("sensor_sync_measurement")
    stamps = defaultdict(list)
    callbacks = {
        "image": lambda msg: stamps["image"].append(stamp_ns(msg)),
        "cloud": lambda msg: stamps["cloud"].append(stamp_ns(msg)),
        "yolo": lambda msg: stamps["yolo"].append(stamp_ns(msg)),
        "camera": lambda msg: stamps["camera"].append(stamp_ns(msg)),
        "lidar": lambda msg: stamps["lidar"].append(stamp_ns(msg)),
    }
    def on_status(message):
        try:
            payload = json.loads(message.data)
            if isinstance(payload.get("inference_ms"), (int, float)):
                stamps["inference_ms"].append(float(payload["inference_ms"]))
        except (TypeError, ValueError, json.JSONDecodeError):
            pass

    fusion_records = []

    def on_fusion_status(message):
        try:
            fusion_records.append(json.loads(message.data))
        except (TypeError, ValueError, json.JSONDecodeError):
            pass

    subscriptions = [
        node.create_subscription(Image, args.image_topic, callbacks["image"], qos_profile_sensor_data),
        node.create_subscription(PointCloud2, args.cloud_topic, callbacks["cloud"], qos_profile_sensor_data),
        node.create_subscription(CameraConeDetectionArray, args.yolo_topic, callbacks["yolo"], qos_profile_sensor_data),
        node.create_subscription(CameraConeDetectionArray, args.camera_topic, callbacks["camera"], qos_profile_sensor_data),
        node.create_subscription(ConeArray, args.lidar_topic, callbacks["lidar"], qos_profile_sensor_data),
        node.create_subscription(String, args.status_topic, on_status, qos_profile_sensor_data),
        node.create_subscription(String, args.fusion_status_topic, on_fusion_status, qos_profile_sensor_data),
    ]
    print(f"Sampling {args.duration:.1f}s: image={args.image_topic}, cloud={args.cloud_topic}, "
          f"yolo={args.yolo_topic}, camera={args.camera_topic}, lidar={args.lidar_topic}, "
          f"status={args.status_topic}, fusion_status={args.fusion_status_topic}", flush=True)
    end = time.monotonic() + args.duration
    try:
        while time.monotonic() < end:
            rclpy.spin_once(node, timeout_sec=0.001)
    finally:
        node.destroy_node()
        rclpy.shutdown()

    for key in ("image", "cloud", "yolo", "camera", "lidar"):
        summarize(key, stamps[key])
    if stamps["inference_ms"]:
        import numpy as np
        values = np.asarray(stamps["inference_ms"])
        print(f"YOLO inference_ms: n={len(values)}, "
              f"median/p95/max={np.percentile(values, 50):.2f}/"
              f"{np.percentile(values, 95):.2f}/{np.max(values):.2f}")
    if fusion_records:
        import numpy as np
        print(f"fusion status: messages={len(fusion_records)}, "
              f"reasons={dict(Counter(record.get('reason', 'unknown') for record in fusion_records))}, "
              f"lidar_cones median={np.median([record.get('lidar_cones', 0) for record in fusion_records]):.1f}, "
              f"matches total={sum(record.get('matches', 0) for record in fusion_records)}")
        offsets = [record["camera_delta_ms"] for record in fusion_records
                   if isinstance(record.get("camera_delta_ms"), (int, float))]
        costs = [record["association_ms"] for record in fusion_records
                 if isinstance(record.get("association_ms"), (int, float))]
        if offsets:
            print(f"accepted camera/LiDAR delta ms: min/median/max="
                  f"{min(offsets):.2f}/{np.median(offsets):.2f}/{max(offsets):.2f}")
        if costs:
            print(f"association ms: median/p95/max="
                  f"{np.median(costs):.4f}/{np.percentile(costs, 95):.4f}/{max(costs):.4f}")
    lidar = stamps["lidar"]
    for camera_key, label in (("image", "image/cloud acquisition"),
                              ("yolo", "YOLO/LiDAR detection"),
                              ("camera", "adapted camera/LiDAR detection")):
        camera = sorted(stamps[camera_key])
        offsets_ms = []
        if camera and lidar:
            for lidar_stamp in lidar:
                nearest = min(camera, key=lambda camera_stamp: abs(camera_stamp - lidar_stamp))
                offsets_ms.append((nearest - lidar_stamp) / 1e6)
        if not offsets_ms:
            print(f"No {label} timestamp pairs received")
            continue
        import numpy as np
        absolute = np.abs(offsets_ms)
        print(f"nearest {label} offset (camera/image minus LiDAR, ms): "
              f"signed median={np.median(offsets_ms):.2f}, "
              f"abs median/p95/p99/max="
              f"{np.percentile(absolute, 50):.2f}/{np.percentile(absolute, 95):.2f}/"
              f"{np.percentile(absolute, 99):.2f}/{np.max(absolute):.2f}")
        for limit in (10, 15, 20, 25, 30, 60):
            count = sum(value <= limit for value in absolute)
            print(f"within_{limit}ms={count}/{len(absolute)} ({100*count/len(absolute):.1f}%)")


if __name__ == "__main__":
    main()
