#!/usr/bin/python3
"""Capture one hardware scene and project raw LiDAR detections into the camera."""
import argparse
import json
from pathlib import Path
import time

import cv2
import numpy as np
import rclpy
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import CameraInfo, Image, PointCloud2
from sensor_msgs_py import point_cloud2
from wuta_msgs.msg import ConeArray

from camera_detection.yolo import image_bgr


def stamp_ns(msg):
    return msg.header.stamp.sec * 1_000_000_000 + msg.header.stamp.nanosec


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='logs/lidar_camera/current_overlay.png')
    parser.add_argument('--seconds', type=float, default=15)
    args = parser.parse_args()
    rclpy.init()
    node = rclpy.create_node('inspect_lidar_camera')
    samples = {}
    node.create_subscription(Image, '/zed/zed_node/rgb/image_rect_color',
                             lambda msg: samples.__setitem__('image', msg), qos_profile_sensor_data)
    node.create_subscription(CameraInfo, '/zed/zed_node/rgb/camera_info',
                             lambda msg: samples.__setitem__('info', msg), qos_profile_sensor_data)
    node.create_subscription(PointCloud2, '/rslidar_points',
                             lambda msg: samples.__setitem__('cloud', msg), qos_profile_sensor_data)
    node.create_subscription(ConeArray, '/perception/lidar/cones_raw',
                             lambda msg: samples.__setitem__('cones', msg), qos_profile_sensor_data)
    deadline = time.monotonic() + args.seconds
    while len(samples) < 4 and time.monotonic() < deadline:
        rclpy.spin_once(node, timeout_sec=0.1)
    node.destroy_node()
    rclpy.shutdown()
    if len(samples) < 4:
        raise RuntimeError('Missing topics: ' + ', '.join(sorted({'image', 'info', 'cloud', 'cones'} - samples.keys())))

    image = image_bgr(samples['image'])
    cloud = point_cloud2.read_points_numpy(samples['cloud'], field_names=['x', 'y', 'z'], skip_nans=True)
    cloud = np.asarray(cloud, dtype=np.float64).reshape(-1, 3)
    rotation = np.array([[0.0106084145794527, -0.9996151424057500, -0.0256325693843221],
                         [0.0191546763256897, 0.0258324536958275, -0.9994827575855980],
                         [0.9997602512177450, 0.0101119438875302, 0.0194213458814503]])
    translation = np.array([0.0424115576688025, 1.0792997325922, 1.64729536709387])
    intrinsics = np.asarray(samples['info'].k, dtype=float).reshape(3, 3)

    def project(points):
        camera = points @ rotation.T + translation
        pixels = camera[:, :2] / camera[:, 2:3]
        pixels = pixels @ np.diag([intrinsics[0, 0], intrinsics[1, 1]])
        pixels += [intrinsics[0, 2], intrinsics[1, 2]]
        return camera, pixels

    camera_cloud, pixels = project(cloud)
    valid = ((camera_cloud[:, 2] > 0.3) & (camera_cloud[:, 2] < 25.0)
             & (pixels[:, 0] >= 0) & (pixels[:, 0] < image.shape[1])
             & (pixels[:, 1] >= 0) & (pixels[:, 1] < image.shape[0]))
    indices = np.flatnonzero(valid)[::4]
    for index in indices:
        u, v = np.rint(pixels[index]).astype(int)
        depth_color = int(np.clip(255 - camera_cloud[index, 2] * 10, 20, 255))
        cv2.circle(image, (u, v), 1, (depth_color, 60, 255 - depth_color), -1)

    cones = np.array([[c.position.x, c.position.y, c.position.z] for c in samples['cones'].cones], float)
    projected_cones = []
    if len(cones):
        camera_cones, cone_pixels = project(cones)
        for index, (camera, pixel) in enumerate(zip(camera_cones, cone_pixels)):
            projected_cones.append({'id': index, 'lidar_xyz': cones[index].tolist(),
                                    'camera_z': float(camera[2]), 'pixel_uv': pixel.tolist()})
            if camera[2] > 0:
                u, v = np.rint(pixel).astype(int)
                cv2.circle(image, (u, v), 8, (0, 0, 255), 2)
                cv2.putText(image, f'L{index}', (u + 7, v - 7), cv2.FONT_HERSHEY_SIMPLEX,
                            .45, (0, 0, 255), 1, cv2.LINE_AA)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output), image)
    np.savez_compressed(output.with_suffix('.npz'), cloud_xyz=cloud, lidar_detections=cones,
                        camera_k=intrinsics)
    report = {'image': str(output), 'cloud_points': int(len(cloud)),
              'visible_projected_points': int(valid.sum()), 'lidar_detections': len(cones),
              'stamp_delta_cloud_image_ms': (stamp_ns(samples['cloud']) - stamp_ns(samples['image'])) / 1e6,
              'detections': projected_cones}
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
