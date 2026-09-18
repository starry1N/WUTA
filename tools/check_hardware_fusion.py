#!/usr/bin/python3
"""Observe the actual ROS graph and acquisition headers for a bounded interval."""
import argparse
from collections import Counter
import json
import time

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from rclpy.time import Time
from sensor_msgs.msg import Image, CameraInfo, PointCloud2
from std_msgs.msg import String
from tf2_ros import Buffer, TransformListener, TransformException
from wuta_msgs.msg import CameraConeDetectionArray, ConeArray, ConeMap


def key(msg):
    h = msg.header
    return h.frame_id, h.stamp.sec * 1000000000 + h.stamp.nanosec


class Check(Node):
    def __init__(self):
        super().__init__('hardware_fusion_check')
        self.counts = Counter()
        self.reasons = Counter()
        self.samples = {}
        self.headers = {name: set() for name in ('image', 'boxes', 'camera', 'lidar', 'fused', 'annotated')}
        self.matches = self.colored = self.depth_valid = 0
        self.guided_clusters = self.published_cones = self.unmatched_filtered = 0
        self.camera_detections = 0
        self.tf = Buffer()
        self.listener = TransformListener(self.tf, self)
        topics = {
            'image': ('/zed/zed_node/rgb/image_rect_color', Image),
            'depth': ('/zed/zed_node/depth/depth_registered', Image),
            'info': ('/zed/zed_node/rgb/camera_info', CameraInfo),
            'cloud': ('/rslidar_points', PointCloud2),
            'boxes': ('/camera/yolo/cones', CameraConeDetectionArray),
            'annotated': ('/camera/yolo/image_annotated', Image),
            'camera': ('/perception/camera/cones', CameraConeDetectionArray),
            'lidar': ('/perception/lidar/cones_raw', ConeArray),
            'fused': ('/perception/fused/cones', ConeArray),
            'map': ('/mapping/cone_map', ConeMap),
        }
        for name, (topic, message_type) in topics.items():
            self.create_subscription(message_type, topic,
                lambda msg, name=name: self.observe(name, msg), qos_profile_sensor_data)
        self.create_subscription(String, '/perception/fusion/status', self.status, qos_profile_sensor_data)
        self.create_subscription(String, '/perception/camera/yolo/status', self.yolo_status, qos_profile_sensor_data)

    def observe(self, name, msg):
        self.counts[name] += 1
        self.samples[name] = {'frame': msg.header.frame_id, 'stamp_ns': key(msg)[1]}
        if name in self.headers:
            self.headers[name].add(key(msg))
        if name in ('image', 'depth', 'cloud', 'info', 'annotated'):
            self.samples[name].update(width=msg.width, height=msg.height)
        if name in ('image', 'depth', 'annotated'):
            self.samples[name]['encoding'] = msg.encoding
        if name == 'boxes':
            self.samples[name]['detections'] = len(msg.detections)
            self.camera_detections += len(msg.detections)
        elif name == 'camera':
            self.depth_valid += sum(d.position_valid for d in msg.detections)
        elif name == 'lidar':
            self.samples[name]['cones'] = len(msg.cones)
        elif name == 'fused':
            self.samples[name]['cones'] = len(msg.cones)
        elif name == 'map':
            self.samples[name]['cones'] = sum(len(getattr(msg, color + '_cones'))
                for color in ('blue', 'yellow', 'orange', 'unknown'))

    def status(self, msg):
        status = json.loads(msg.data)
        self.reasons[status['reason']] += 1
        self.matches += status['matches']
        self.colored += status['colored']
        self.guided_clusters += status.get('guided_clusters', 0)
        self.published_cones += status.get('published_cones', 0)
        self.unmatched_filtered += status.get('unmatched_filtered', 0)

    def yolo_status(self, msg):
        self.samples['yolo_performance'] = json.loads(msg.data)

    def report(self):
        # Best-effort observations may be lost or arrive in different callback order.
        # Missing source headers are inconclusive, not proof of altered timestamps.
        header_checks = {}
        for output, source in [('boxes', 'image'), ('annotated', 'image'), ('camera', 'boxes'), ('fused', 'lidar')]:
            header_checks[output] = {'matched': len(self.headers[output] & self.headers[source]),
                'source_not_observed': len(self.headers[output] - self.headers[source])}
        transforms = {}
        for target, source in [('zed_left_camera_optical_frame', 'rslidar'), ('map', 'rslidar'), ('odom', 'rslidar')]:
            try:
                self.tf.lookup_transform(target, source, Time())
                transforms[target + '<-' + source] = True
            except TransformException:
                transforms[target + '<-' + source] = False
        return dict(counts=dict(self.counts), samples=self.samples, reasons=dict(self.reasons),
            matches=self.matches, colored=self.colored, guided_clusters=self.guided_clusters,
            published_cones=self.published_cones, unmatched_filtered=self.unmatched_filtered,
            stereo_valid_detections=self.depth_valid,
            camera_detections=self.camera_detections, observed_header_checks=header_checks,
            transforms=transforms,
            map_publishers=len(self.get_publishers_info_by_topic('/mapping/cone_map')),
            cloud_publishers=len(self.get_publishers_info_by_topic('/rslidar_points')))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--seconds', type=float, default=20)
    args = parser.parse_args()
    rclpy.init()
    node = Check()
    deadline = time.monotonic() + args.seconds
    try:
        while time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.05)
        print(json.dumps(node.report(), indent=2))
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
