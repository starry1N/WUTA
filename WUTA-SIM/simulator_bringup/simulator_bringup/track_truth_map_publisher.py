"""Publish the LiDAR simulator's loaded YAML map as an algorithm-side ConeMap."""

import os
from pathlib import Path
from typing import Any, Optional

import rclpy
import yaml
from ament_index_python.packages import get_package_share_directory
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import UInt32
from visualization_msgs.msg import Marker, MarkerArray
from wuta_msgs.msg import Cone, ConeMap


def _resolve_track_file(value: str) -> Path:
    """Resolve the same installed-name or path forms accepted by lidar_sim."""
    candidate = Path(value).expanduser()
    if candidate.is_file():
        return candidate

    search_dirs = [
        Path(get_package_share_directory("lidar_sim")) / "tracks",
        Path.cwd() / "tracks",
    ]
    if os.environ.get("WUTA_ROOT"):
        search_dirs.insert(1, Path(os.environ["WUTA_ROOT"]) / "tracks")

    names = (value, f"{value}.yaml") if not Path(value).suffix else (value,)
    for tracks_dir in search_dirs:
        for name in names:
            candidate = tracks_dir / name
            if candidate.is_file():
                return candidate
    raise FileNotFoundError("Track file not found: %s" % value)


class TrackTruthMapPublisher(Node):
    """Adapt the static simulator YAML map to FSD's /mapping/cone_map input."""

    def __init__(self) -> None:
        super().__init__("track_truth_map_publisher")
        self.declare_parameter("track_file", "trackdrive")
        self.declare_parameter("map_topic", "/mapping/cone_map")
        self.declare_parameter("visualization_topic", "/mapping/cone_map_viz")
        self.declare_parameter("map_frame", "map")
        self.declare_parameter("mapping_laps", 1)
        # Match cone_map_builder's 5 Hz map cadence so online boundary and
        # speed planning refresh at the same rate in truth-shortcut mode.
        self.declare_parameter("publish_rate_hz", 5.0)

        track_file = _resolve_track_file(
            str(self.get_parameter("track_file").value)
        )
        self.map_frame = str(self.get_parameter("map_frame").value)
        self.mapping_laps = max(
            1, int(self.get_parameter("mapping_laps").value)
        )
        self.completed_laps = 0
        self.closed_logged = False
        self.cone_map = self._load_cone_map(track_file)

        qos = QoSProfile(
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )
        self.publisher = self.create_publisher(
            ConeMap, str(self.get_parameter("map_topic").value), qos
        )
        self.visualization_publisher = self.create_publisher(
            MarkerArray,
            str(self.get_parameter("visualization_topic").value),
            qos,
        )
        self.lap_count_subscription = self.create_subscription(
            UInt32, "/system/lap_count", self._on_lap_count, qos
        )
        rate_hz = float(self.get_parameter("publish_rate_hz").value)
        if rate_hz <= 0.0:
            raise ValueError("publish_rate_hz must be positive")
        self.timer = self.create_timer(1.0 / rate_hz, self._publish)
        self._publish()
        self.get_logger().info(
            "Publishing %d loaded track cones from %s directly to %s and %s"
            % (
                len(self.cone_map.blue_cones)
                + len(self.cone_map.yellow_cones)
                + len(self.cone_map.orange_cones)
                + len(self.cone_map.unknown_cones),
                track_file,
                self.get_parameter("map_topic").value,
                self.get_parameter("visualization_topic").value,
            )
        )

    @staticmethod
    def _cone(entry: Any, color: int) -> Cone:
        if isinstance(entry, dict):
            x = float(entry.get("x", 0.0))
            y = float(entry.get("y", 0.0))
            z = float(entry.get("z", 0.0))
        else:
            values = list(entry)
            if len(values) < 2:
                raise ValueError("Cone position needs at least x and y")
            x, y = float(values[0]), float(values[1])
            z = float(values[2]) if len(values) > 2 else 0.0

        cone = Cone()
        cone.position.x = x
        cone.position.y = y
        cone.position.z = z
        cone.color = color
        cone.confidence = 1.0
        return cone

    def _load_cone_map(self, track_file: Path) -> ConeMap:
        with track_file.open("r", encoding="utf-8") as stream:
            data = yaml.safe_load(stream) or {}
        track = data.get("track", data)

        cone_map = ConeMap()
        cone_map.header.frame_id = self.map_frame
        cone_map.blue_cones = [
            self._cone(entry, Cone.COLOR_BLUE)
            for entry in track.get("blue_cones", []) or []
        ]
        # FSD's ConeMap models its right boundary as yellow. Red route cones
        # therefore use that compatible bucket in truth-map shortcut mode.
        cone_map.yellow_cones = [
            self._cone(entry, Cone.COLOR_YELLOW)
            for key in ("yellow_cones", "yellow_low_cones", "yellow_high_cones", "red_cones")
            for entry in track.get(key, []) or []
        ]
        cone_map.orange_cones = [
            self._cone(entry, Cone.COLOR_ORANGE)
            for entry in track.get("orange_cones", []) or []
        ]
        cone_map.unknown_cones = [
            self._cone(entry, Cone.COLOR_UNKNOWN)
            for entry in track.get("unknown_cones", []) or []
        ]
        # Even though all simulated camera-equivalent colors are available,
        # lap one remains EXPLORE. The publisher marks this cone map closed
        # only after the formal localization-based lap counter completes the
        # configured mapping lap.
        cone_map.is_closed = False
        return cone_map

    def _on_lap_count(self, msg: UInt32) -> None:
        self.completed_laps = int(msg.data)

    def _make_visualization(self, stamp: Any) -> MarkerArray:
        """Render the algorithm input map for the existing RViz Cone Map view."""
        markers = MarkerArray()
        delete = Marker()
        delete.header.frame_id = self.map_frame
        delete.header.stamp = stamp
        delete.action = Marker.DELETEALL
        markers.markers.append(delete)

        color_rgba = {
            Cone.COLOR_BLUE: (0.0, 0.4, 1.0),
            Cone.COLOR_YELLOW: (1.0, 0.9, 0.0),
            Cone.COLOR_ORANGE: (1.0, 0.5, 0.0),
            Cone.COLOR_UNKNOWN: (1.0, 1.0, 1.0),
        }
        cones = (
            self.cone_map.blue_cones
            + self.cone_map.yellow_cones
            + self.cone_map.orange_cones
            + self.cone_map.unknown_cones
        )
        for marker_id, cone in enumerate(cones):
            marker = Marker()
            marker.header.frame_id = self.map_frame
            marker.header.stamp = stamp
            marker.ns = "cone_map"
            marker.id = marker_id
            marker.type = Marker.CYLINDER
            marker.action = Marker.ADD
            marker.pose.position = cone.position
            marker.pose.orientation.w = 1.0
            marker.scale.x = 0.3
            marker.scale.y = 0.3
            marker.scale.z = 0.5
            marker.color.r, marker.color.g, marker.color.b = color_rgba.get(
                cone.color, color_rgba[Cone.COLOR_UNKNOWN]
            )
            marker.color.a = 0.9
            markers.markers.append(marker)
        return markers

    def _publish(self) -> None:
        stamp = self.get_clock().now().to_msg()
        self.cone_map.is_closed = self.completed_laps >= self.mapping_laps
        if self.cone_map.is_closed and not self.closed_logged:
            self.closed_logged = True
            self.get_logger().info(
                "Truth-color cone map closed after formal lap %d/%d"
                % (self.completed_laps, self.mapping_laps)
            )
        self.cone_map.header.stamp = stamp
        self.publisher.publish(self.cone_map)
        self.visualization_publisher.publish(self._make_visualization(stamp))


def main(args: Optional[list] = None) -> None:
    rclpy.init(args=args)
    node: Optional[TrackTruthMapPublisher] = None
    try:
        node = TrackTruthMapPublisher()
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
