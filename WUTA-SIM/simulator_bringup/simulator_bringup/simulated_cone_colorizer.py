"""Assign simulator-known colors to LiDAR detections without bypassing mapping."""

from collections import deque
from math import atan2, cos, hypot, sin
from pathlib import Path
from typing import Any, Deque, Iterable, Optional, Tuple

import rclpy
import yaml
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from wuta_msgs.msg import Cone, ConeArray

from simulator_bringup.track_truth_map_publisher import _resolve_track_file


TruthCone = Tuple[float, float, int]
PoseSample = Tuple[int, float, float, float]


def _stamp_ns(stamp: Any) -> int:
    return int(stamp.sec) * 1_000_000_000 + int(stamp.nanosec)


def _yaw_from_odometry(msg: Odometry) -> float:
    q = msg.pose.pose.orientation
    return atan2(
        2.0 * (q.w * q.z + q.x * q.y),
        1.0 - 2.0 * (q.y * q.y + q.z * q.z),
    )


def _lidar_to_map_xy(
    lidar_x: float,
    lidar_y: float,
    pose_x: float,
    pose_y: float,
    pose_yaw: float,
    offset_x: float = 0.0,
    offset_y: float = 0.0,
) -> Tuple[float, float]:
    c = cos(pose_yaw)
    s = sin(pose_yaw)
    sensor_x = offset_x + lidar_x
    sensor_y = offset_y + lidar_y
    return (
        pose_x + c * sensor_x - s * sensor_y,
        pose_y + s * sensor_x + c * sensor_y,
    )


def _nearest_truth_color(
    map_x: float,
    map_y: float,
    truth_cones: Iterable[TruthCone],
    max_distance: float,
) -> Optional[int]:
    nearest_color: Optional[int] = None
    nearest_distance = max(0.0, max_distance)
    for truth_x, truth_y, color in truth_cones:
        distance = hypot(map_x - truth_x, map_y - truth_y)
        if distance <= nearest_distance:
            nearest_distance = distance
            nearest_color = color
    return nearest_color


def _entry_xy(entry: Any) -> Tuple[float, float]:
    if isinstance(entry, dict):
        return float(entry.get("x", 0.0)), float(entry.get("y", 0.0))
    values = list(entry)
    if len(values) < 2:
        raise ValueError("Cone position needs at least x and y")
    return float(values[0]), float(values[1])


def _load_truth_cones(track_file: Path) -> list[TruthCone]:
    with track_file.open("r", encoding="utf-8") as stream:
        data = yaml.safe_load(stream) or {}
    track = data.get("track", data)

    truth_cones: list[TruthCone] = []
    groups = (
        ("blue_cones", Cone.COLOR_BLUE),
        ("yellow_cones", Cone.COLOR_YELLOW),
        ("yellow_low_cones", Cone.COLOR_YELLOW),
        ("yellow_high_cones", Cone.COLOR_YELLOW),
        ("red_cones", Cone.COLOR_YELLOW),
        ("orange_cones", Cone.COLOR_ORANGE),
        ("unknown_cones", Cone.COLOR_UNKNOWN),
    )
    for key, color in groups:
        for entry in track.get(key, []) or []:
            x, y = _entry_xy(entry)
            truth_cones.append((x, y, color))
    return truth_cones


class SimulatedConeColorizer(Node):
    """Decorate detected cones with YAML truth colors using timestamped truth pose."""

    def __init__(self) -> None:
        super().__init__("simulated_cone_colorizer")
        self.declare_parameter("track_file", "trackdrive")
        self.declare_parameter("input_topic", "/perception/lidar/cones_raw")
        self.declare_parameter("output_topic", "/perception/lidar/cones")
        self.declare_parameter("ground_truth_topic", "/sim/ground_truth")
        self.declare_parameter("max_match_distance", 1.0)
        self.declare_parameter("max_pose_age_sec", 0.20)
        self.declare_parameter("lidar_offset_x", 0.0)
        self.declare_parameter("lidar_offset_y", 0.0)
        self.declare_parameter("pose_history_size", 400)

        track_file = _resolve_track_file(
            str(self.get_parameter("track_file").value)
        )
        self.truth_cones = _load_truth_cones(track_file)
        if not self.truth_cones:
            raise ValueError("Track has no cones: %s" % track_file)

        self.max_match_distance = float(
            self.get_parameter("max_match_distance").value
        )
        self.max_pose_age_ns = int(
            max(0.0, float(self.get_parameter("max_pose_age_sec").value))
            * 1_000_000_000
        )
        self.lidar_offset_x = float(
            self.get_parameter("lidar_offset_x").value
        )
        self.lidar_offset_y = float(
            self.get_parameter("lidar_offset_y").value
        )
        history_size = max(
            10, int(self.get_parameter("pose_history_size").value)
        )
        self.pose_history: Deque[PoseSample] = deque(maxlen=history_size)
        self.frames_received = 0
        self.last_status_log_ns = 0

        self.publisher = self.create_publisher(
            ConeArray, str(self.get_parameter("output_topic").value), 10
        )
        self.ground_truth_subscription = self.create_subscription(
            Odometry,
            str(self.get_parameter("ground_truth_topic").value),
            self._on_ground_truth,
            qos_profile_sensor_data,
        )
        self.detection_subscription = self.create_subscription(
            ConeArray,
            str(self.get_parameter("input_topic").value),
            self._on_detections,
            10,
        )
        self.get_logger().info(
            "Simulated camera colors ready: %d truth cones from %s"
            % (len(self.truth_cones), track_file)
        )

    def _on_ground_truth(self, msg: Odometry) -> None:
        self.pose_history.append(
            (
                _stamp_ns(msg.header.stamp),
                float(msg.pose.pose.position.x),
                float(msg.pose.pose.position.y),
                _yaw_from_odometry(msg),
            )
        )

    def _pose_for_stamp(self, stamp_ns: int) -> Optional[PoseSample]:
        if not self.pose_history:
            return None
        sample = min(
            self.pose_history, key=lambda item: abs(item[0] - stamp_ns)
        )
        if abs(sample[0] - stamp_ns) > self.max_pose_age_ns:
            return None
        return sample

    def _on_detections(self, msg: ConeArray) -> None:
        pose = self._pose_for_stamp(_stamp_ns(msg.header.stamp))
        if pose is None:
            self.get_logger().warning(
                "Dropping simulated color frame without matching ground truth pose."
            )
            return

        _, pose_x, pose_y, pose_yaw = pose
        matched = 0
        for cone in msg.cones:
            map_x, map_y = _lidar_to_map_xy(
                float(cone.position.x),
                float(cone.position.y),
                pose_x,
                pose_y,
                pose_yaw,
                self.lidar_offset_x,
                self.lidar_offset_y,
            )
            color = _nearest_truth_color(
                map_x,
                map_y,
                self.truth_cones,
                self.max_match_distance,
            )
            if color is not None:
                cone.color = color
                matched += 1
            else:
                cone.color = Cone.COLOR_UNKNOWN

        self.publisher.publish(msg)
        self.frames_received += 1
        now_ns = self.get_clock().now().nanoseconds
        if now_ns - self.last_status_log_ns >= 5_000_000_000:
            self.last_status_log_ns = now_ns
            match_rate = matched / max(1, len(msg.cones))
            self.get_logger().info(
                "Simulated camera color match: %d/%d (%.1f%%)"
                % (matched, len(msg.cones), 100.0 * match_rate)
            )


def main(args: Optional[list] = None) -> None:
    rclpy.init(args=args)
    node: Optional[SimulatedConeColorizer] = None
    try:
        node = SimulatedConeColorizer()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
