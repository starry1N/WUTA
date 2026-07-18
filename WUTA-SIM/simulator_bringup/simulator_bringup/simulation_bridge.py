"""Bridge simulator ground truth into the Level A WUTA-FSD interfaces."""

from typing import Optional

import rclpy
from autoware_msgs.msg import Command
from geometry_msgs.msg import PointStamped, PoseStamped, TransformStamped
from nav_msgs.msg import Odometry
from rclpy.node import Node
from sensor_msgs.msg import PointCloud2
from std_msgs.msg import Bool, Float64
from tf2_ros import TransformBroadcaster
from visualization_msgs.msg import Marker, MarkerArray
from wuta_msgs.msg import MissionState


class SimulationBridge(Node):
    """Adapt simulator truth to the interfaces needed by WUTA-FSD."""

    def __init__(self) -> None:
        super().__init__("simulation_bridge")

        self.declare_parameter("ground_truth_topic", "/sim/ground_truth")
        self.declare_parameter("publish_start_command", True)
        self.declare_parameter("publish_truth_localization", False)
        self.declare_parameter("manual_ready", False)
        self.declare_parameter("map_frame", "map")
        self.declare_parameter("base_frame", "base_link")
        self.declare_parameter("timing_min_lap_duration", 1.0)

        ground_truth_topic = str(
            self.get_parameter("ground_truth_topic").value
        )
        self.publish_start_command = bool(
            self.get_parameter("publish_start_command").value
        )
        self.publish_truth_localization = bool(
            self.get_parameter("publish_truth_localization").value
        )
        self.manual_ready_enabled = bool(
            self.get_parameter("manual_ready").value
        )
        self.map_frame = str(self.get_parameter("map_frame").value)
        self.base_frame = str(self.get_parameter("base_frame").value)
        self.timing_min_lap_duration = float(
            self.get_parameter("timing_min_lap_duration").value
        )

        self.pose_pub = self.create_publisher(
            PoseStamped, "/localization/pose", 10
        )
        self.localization_ready_pub = self.create_publisher(
            Bool, "/system/localization_ready", 10
        )
        self.lidar_ready_pub = self.create_publisher(
            Bool, "/system/lidar_ready", 10
        )
        self.start_command_pub = self.create_publisher(
            Bool, "/system/start_command", 10
        )
        self.system_status_viz_pub = self.create_publisher(
            MarkerArray, "/system/status_viz", 10
        )
        self.lap_time_pub = self.create_publisher(Float64, "/system/lap_time", 10)
        self.latency_pub = self.create_publisher(
            Float64, "/system/simulator_latency", 10
        )
        self.tf_broadcaster = TransformBroadcaster(self)

        self.ground_truth_sub = self.create_subscription(
            Odometry, ground_truth_topic, self._on_ground_truth, 10
        )
        self.mission_state_sub = self.create_subscription(
            MissionState, "/system/mission_state", self._on_mission_state, 10
        )
        self.manual_ready_sub = self.create_subscription(
            PointStamped, "/clicked_point", self._on_manual_ready, 10
        )
        self.lidar_sub = self.create_subscription(
            PointCloud2, "/hesai/pandar", self._on_lidar, 10
        )
        self.command_sub = self.create_subscription(
            Command, "/control/command", self._on_command, 10
        )
        self.status_timer = self.create_timer(0.1, self._publish_status)
        self.received_ground_truth = False
        self.latest_mission_state: Optional[MissionState] = None
        self.latest_ground_truth: Optional[Odometry] = None
        self.manual_ready_confirmed = False
        self.latest_lidar_stamp_s: Optional[float] = None
        self.latest_latency_s: Optional[float] = None
        self.latest_lap_time_s: Optional[float] = None
        self.received_lidar = False
        self.received_command = False
        self.previous_ground_truth: Optional[Odometry] = None
        self.lap_started_at_s: Optional[float] = None
        self.last_timed_mode: Optional[int] = None
        self.timing_was_active = False

        self.get_logger().info(
            "Simulation bridge waiting for ground truth on %s; truth localization=%s"
            % (ground_truth_topic, self.publish_truth_localization)
        )

    def _on_ground_truth(self, msg: Odometry) -> None:
        self.received_ground_truth = True
        self.latest_ground_truth = msg

        self._update_lap_timer(msg)

        if not self.publish_truth_localization:
            return

        pose = PoseStamped()
        pose.header = msg.header
        pose.header.frame_id = self.map_frame
        pose.pose = msg.pose.pose
        self.pose_pub.publish(pose)

        transform = TransformStamped()
        transform.header = pose.header
        transform.child_frame_id = self.base_frame
        transform.transform.translation.x = pose.pose.position.x
        transform.transform.translation.y = pose.pose.position.y
        transform.transform.translation.z = pose.pose.position.z
        transform.transform.rotation = pose.pose.orientation
        self.tf_broadcaster.sendTransform(transform)

    def _on_mission_state(self, msg: MissionState) -> None:
        if self.last_timed_mode is not None and self.last_timed_mode != msg.mission_mode:
            self._reset_lap_timer(clear_last=True)
        self.latest_mission_state = msg
        self.last_timed_mode = msg.mission_mode

    @staticmethod
    def _stamp_to_seconds(stamp) -> float:
        return float(stamp.sec) + float(stamp.nanosec) * 1e-9

    def _on_lidar(self, msg: PointCloud2) -> None:
        """Keep the source timestamp for the next end-to-end delay sample."""
        stamp_s = self._stamp_to_seconds(msg.header.stamp)
        if stamp_s > 0.0:
            self.latest_lidar_stamp_s = stamp_s
            if not self.received_lidar:
                self.received_lidar = True
                self.get_logger().info("Received /hesai/pandar timestamps for latency metric")

    def _on_command(self, msg: Command) -> None:
        """Publish LiDAR-stamp to command-stamp delay in seconds.

        Command.header.stamp is assigned immediately before controller publish.
        Using it rather than this callback's receive time excludes DDS delivery
        delay and implements the simulator metric exactly at the two topics.
        """
        if not self.received_command:
            self.received_command = True
            self.get_logger().info("Received /control/command for latency metric")
        if self.latest_lidar_stamp_s is None:
            return
        command_stamp_s = self._stamp_to_seconds(msg.header.stamp)
        if command_stamp_s <= 0.0:
            self.get_logger().warn(
                "Ignoring /control/command without a Header timestamp",
                throttle_duration_sec=5.0,
            )
            return
        latency_s = command_stamp_s - self.latest_lidar_stamp_s
        if latency_s < 0.0:
            self.get_logger().warn(
                "Ignoring negative simulator latency %.3f ms; verify use_sim_time/clock"
                % (latency_s * 1000.0),
                throttle_duration_sec=5.0,
            )
            return
        self.latest_latency_s = latency_s
        out = Float64()
        out.data = latency_s
        self.latency_pub.publish(out)

    def _timing_spec(self, mission_mode: int) -> tuple[float, float, float]:
        """Return start-x, finish-x and half-width for the installed tracks."""
        if mission_mode == MissionState.MISSION_ACCELERATION:
            # acceleration.yaml timing_start/finish lines
            return 0.0, 75.0, 1.5
        if mission_mode == MissionState.MISSION_SKIDPAD:
            # skidpad.yaml: shared x=0 timing line between the high cones.
            return 0.0, 0.0, 1.5
        # trackdrive.yaml: orange cones at x=0, y=+-1.75 define the line.
        return 0.0, 0.0, 1.75

    def _reset_lap_timer(self, clear_last: bool = False) -> None:
        self.previous_ground_truth = None
        self.lap_started_at_s = None
        if clear_last:
            self.latest_lap_time_s = None

    def _is_timing_active(self) -> bool:
        current = self.latest_mission_state
        return current is not None and current.state in (
            MissionState.EXPLORE,
            MissionState.RACE,
        )

    @staticmethod
    def _crosses_positive_x_line(
        previous: Odometry, current: Odometry, line_x: float, half_width: float
    ) -> bool:
        """True if the vehicle reference point crosses a finite line along +X."""
        previous_position = previous.pose.pose.position
        current_position = current.pose.pose.position
        if not (previous_position.x <= line_x < current_position.x):
            return False
        # Linear interpolation gives the y coordinate at the physical line,
        # rather than accepting a sample that has already travelled past it.
        dx = current_position.x - previous_position.x
        ratio = 0.0 if abs(dx) < 1e-9 else (line_x - previous_position.x) / dx
        crossing_y = previous_position.y + ratio * (
            current_position.y - previous_position.y
        )
        return abs(crossing_y) <= half_width

    def _update_lap_timer(self, msg: Odometry) -> None:
        """Measure each lap from configured start line to finish line in truth."""
        if not self._is_timing_active():
            self.previous_ground_truth = None
            self.lap_started_at_s = None
            self.timing_was_active = False
            return

        if not self.timing_was_active:
            self._reset_lap_timer(clear_last=True)
            self.timing_was_active = True

        previous = self.previous_ground_truth
        self.previous_ground_truth = msg
        if previous is None:
            return

        current = self.latest_mission_state
        start_x, finish_x, half_width = self._timing_spec(current.mission_mode)
        stamp_s = self._stamp_to_seconds(msg.header.stamp)
        if stamp_s <= 0.0:
            return

        if self.lap_started_at_s is None:
            if self._crosses_positive_x_line(previous, msg, start_x, half_width):
                self.lap_started_at_s = stamp_s
                self.get_logger().info("Lap timer started at x=%.3f m" % start_x)
            return

        if not self._crosses_positive_x_line(previous, msg, finish_x, half_width):
            return

        lap_time_s = stamp_s - self.lap_started_at_s
        if lap_time_s < self.timing_min_lap_duration:
            return

        self.latest_lap_time_s = lap_time_s
        out = Float64()
        out.data = lap_time_s
        self.lap_time_pub.publish(out)
        self.get_logger().info(
            "Lap complete: %.3f s (start x=%.3f m, finish x=%.3f m)"
            % (lap_time_s, start_x, finish_x)
        )
        # Shared start/finish lines (trackdrive/skidpad) immediately start the
        # next lap. Acceleration uses different lines and remains disarmed.
        self.lap_started_at_s = stamp_s if start_x == finish_x else None

    def _on_manual_ready(self, _msg: PointStamped) -> None:
        """Latch a manual-ready confirmation from RViz Publish Point."""
        if not self.manual_ready_enabled or self.manual_ready_confirmed:
            return
        self.manual_ready_confirmed = True
        self.get_logger().info(
            "Manual ready confirmed from RViz /clicked_point; publishing readiness"
        )

    def _publish_status(self) -> None:
        ready = (
            self.manual_ready_confirmed
            if self.manual_ready_enabled
            else self.received_ground_truth
        )
        lidar_ready = Bool()
        lidar_ready.data = ready
        self.lidar_ready_pub.publish(lidar_ready)

        if self.publish_truth_localization or self.manual_ready_enabled:
            localization_ready = Bool()
            localization_ready.data = ready
            self.localization_ready_pub.publish(localization_ready)

        if self.publish_start_command:
            start = Bool()
            start.data = True
            self.start_command_pub.publish(start)

        self._publish_status_visualization()

    def _publish_status_visualization(self) -> None:
        """Publish simulator runtime state as an RViz text marker."""
        mode_names = {
            MissionState.MISSION_TRACKDRIVE: "TRACKDRIVE",
            MissionState.MISSION_SKIDPAD: "SKIDPAD",
            MissionState.MISSION_ACCELERATION: "ACCELERATION",
        }
        current = self.latest_mission_state
        mission_state = (
            "FINISH" if current is not None and current.state == MissionState.FINISH
            else "EXPLORE" if current is not None and current.state == MissionState.EXPLORE
            else "READY" if current is not None and current.state == MissionState.READY
            else "IDLE"
        )
        mode_name = mode_names.get(
            current.mission_mode if current is not None else -1, "UNKNOWN"
        )
        completed = current is not None and current.state == MissionState.FINISH

        marker = Marker()
        marker.header.frame_id = self.map_frame
        marker.header.stamp = self.get_clock().now().to_msg()
        marker.ns = "simulator_status"
        marker.id = 0
        marker.type = Marker.TEXT_VIEW_FACING
        marker.action = Marker.ADD
        marker.pose.orientation.w = 1.0
        marker.pose.position.z = 2.5
        marker.scale.z = 0.45
        marker.color.r = 0.2 if completed else 1.0
        marker.color.g = 1.0
        marker.color.b = 0.2
        marker.color.a = 1.0

        lines = [
            "Mission: %s" % mode_name,
            "State: %s" % mission_state,
            "Complete: %s" % str(completed).lower(),
            "Ready: %s" % (
                "manual confirmed" if self.manual_ready_confirmed
                else "click RViz map" if self.manual_ready_enabled
                else "automatic"
            ),
        ]
        if self.latest_lap_time_s is None:
            lines.append("Lap time: waiting for start/finish")
        else:
            lines.append("Last lap: %.3f s" % self.latest_lap_time_s)
        if self.latest_latency_s is None:
            lines.append("LiDAR -> command: waiting")
        else:
            lines.append("LiDAR -> command: %.1f ms" % (self.latest_latency_s * 1000.0))
        if self.latest_ground_truth is not None:
            position = self.latest_ground_truth.pose.pose.position
            velocity = self.latest_ground_truth.twist.twist.linear
            speed = (velocity.x * velocity.x + velocity.y * velocity.y) ** 0.5
            marker.pose.position.x = position.x + 1.0
            marker.pose.position.y = position.y + 1.0
            lines.extend(
                [
                    "GT speed: %.2f m/s" % speed,
                    "GT pose: (%.2f, %.2f) m" % (position.x, position.y),
                ]
            )
        else:
            lines.append("GT: waiting")
        marker.text = "\n".join(lines)

        markers = MarkerArray()
        markers.markers.append(marker)
        self.system_status_viz_pub.publish(markers)


def main(args: Optional[list] = None) -> None:
    rclpy.init(args=args)
    node: Optional[SimulationBridge] = None
    try:
        node = SimulationBridge()
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
