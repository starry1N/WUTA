"""Synthetic YOLO boxes/color and noisy stereo 3-D, independent of LiDAR detections.

This is a detection simulator, not a renderer, YOLO inference or stereo matcher.
Only this simulator reads track truth; detection_fusion never reads a track file.
"""
import math
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from nav_msgs.msg import Odometry
from sensor_msgs.msg import CameraInfo
from wuta_msgs.msg import CameraConeDetection, CameraConeDetectionArray
from simulator_bringup.simulated_cone_colorizer import _load_truth_cones, _yaw_from_odometry
from simulator_bringup.track_truth_map_publisher import _resolve_track_file


class SimulatedStereoDetections(Node):
    def __init__(self):
        super().__init__('simulated_stereo_detections')
        self.declare_parameter('track_file', 'trackdrive')
        self.declare_parameter('publish_rate_hz', 20.0)
        self.declare_parameter('max_range', 20.0)
        self.declare_parameter('seed', 7)
        self.declare_parameter('depth_dropout_probability', 0.05)
        self.declare_parameter('color_error_probability', 0.0)
        self.track = _load_truth_cones(_resolve_track_file(self.get_parameter('track_file').value))
        self.rng = np.random.default_rng(self.get_parameter('seed').value)
        self.last_stamp = -1.0
        self.pub = self.create_publisher(CameraConeDetectionArray, '/perception/camera/cones', 10)
        self.info_pub = self.create_publisher(CameraInfo, '/perception/camera/camera_info', 10)
        self.create_subscription(Odometry, '/sim/ground_truth', self.on_pose, qos_profile_sensor_data)

    def on_pose(self, pose):
        now = pose.header.stamp.sec + pose.header.stamp.nanosec*1e-9
        if now-self.last_stamp < 1.0/self.get_parameter('publish_rate_hz').value:
            return
        self.last_stamp = now
        result = CameraConeDetectionArray()
        result.header.stamp = pose.header.stamp
        result.header.frame_id = 'sim_camera_left_optical_frame'
        info = CameraInfo()
        info.header = result.header
        info.width, info.height = 1280, 720
        info.k = [700., 0., 640., 0., 700., 360., 0., 0., 1.]
        info.p = [700., 0., 640., 0., 0., 700., 360., 0., 0., 0., 1., 0.]
        info.r = [1., 0., 0., 0., 1., 0., 0., 0., 1.]
        self.info_pub.publish(info)
        yaw = _yaw_from_odometry(pose)
        c, s = math.cos(yaw), math.sin(yaw)
        visible = []
        for index, (x, y, color) in enumerate(self.track):
            dx, dy = x-pose.pose.pose.position.x, y-pose.pose.pose.position.y
            forward, lateral = c*dx+s*dy, -s*dx+c*dy
            if forward < 0.7 or math.hypot(forward, lateral) > self.get_parameter('max_range').value:
                continue
            # Optical frame: right/down/forward, camera mounted 0.5 m high.
            point = np.array([-lateral, 0.5-0.16, forward])
            u, v = 640.+700.*point[0]/forward, 360.+700.*point[1]/forward
            half_w, half_h = max(3., 700.*0.16/forward), max(4., 700.*0.18/forward)
            if u-half_w < 0 or u+half_w >= 1280 or v-half_h < 0 or v+half_h >= 720:
                continue
            visible.append((forward, index, color, point, [u-half_w, v-half_h, u+half_w, v+half_h]))
        accepted = []
        for distance, index, color, point, box in sorted(visible, key=lambda item: item[0]):
            # Conservative simple occlusion: suppress a farther box whose centre
            # is inside a nearer cone. Detailed rendering remains a driver task.
            u, v = (box[0]+box[2])/2, (box[1]+box[3])/2
            if any(b[0] <= u <= b[2] and b[1] <= v <= b[3] for b in accepted):
                continue
            accepted.append(box)
            detection = CameraConeDetection()
            detection.detection_id = index
            detection.bbox_xyxy = box
            detection.confidence = 0.95
            if color in (1, 2) and self.rng.random() < self.get_parameter('color_error_probability').value:
                color = 3-color
            probs = [0.02, 0.02, 0.02, 0.02]
            probs[color] = 0.94
            detection.color_probabilities = probs
            sigma = np.array([0.025, 0.025, 0.03+0.0015*distance**2])
            noisy = point+self.rng.normal(0., sigma)
            detection.position.x, detection.position.y, detection.position.z = map(float, noisy)
            detection.position_covariance = np.diag(sigma**2).flatten().tolist()
            detection.position_valid = self.rng.random() >= self.get_parameter('depth_dropout_probability').value
            result.detections.append(detection)
        self.pub.publish(result)


def main(args=None):
    rclpy.init(args=args)
    node = SimulatedStereoDetections()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
