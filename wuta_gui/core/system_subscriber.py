"""系统状态订阅模块 - 直接订阅 ROS 2 话题

此模块使用延迟导入，使得 GUI 可以在没有 ROS 环境的情况下打开。
ROS 功能在 start() 时才初始化，如果导入失败会设置 available=False。
"""

from PyQt5.QtCore import QObject, pyqtSignal, QTimer


class SystemSubscriber(QObject):
    """订阅系统状态的模块"""

    mission_state_received = pyqtSignal(object)
    ground_truth_received = pyqtSignal(object)
    lap_count_received = pyqtSignal(object)
    lap_time_received = pyqtSignal(object)
    latency_received = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.node = None
        self._timer = None
        self._available = False

        # 延迟导入 ROS 消息（可能失败）
        try:
            import rclpy
            from rclpy.node import Node
            from nav_msgs.msg import Odometry
            from std_msgs.msg import Bool, Float64, UInt32
            from wuta_msgs.msg import MissionState
            self._ros_imports = {
                'rclpy': rclpy,
                'Node': Node,
                'Odometry': Odometry,
                'Bool': Bool,
                'Float64': Float64,
                'UInt32': UInt32,
                'MissionState': MissionState,
            }
            self._available = True
        except ImportError:
            self._available = False

    @property
    def available(self) -> bool:
        """ROS 功能是否可用"""
        return self._available

    def start(self, interval_ms=50):
        """启动订阅（如果 ROS 可用）"""
        if not self._available:
            return

        rclpy = self._ros_imports['rclpy']
        Node = self._ros_imports['Node']
        Odometry = self._ros_imports['Odometry']
        Bool = self._ros_imports['Bool']
        Float64 = self._ros_imports['Float64']
        UInt32 = self._ros_imports['UInt32']
        MissionState = self._ros_imports['MissionState']

        # GUI 进程内初始化 rclpy（仅一次），否则 Node 构造会抛 NotInitializedException。
        # args=[] 避免把 PyQt 命令行参数喂给 ROS 解析。
        if not rclpy.ok():
            rclpy.init(args=[])

        self.node = Node("wuta_gui_system_sub")

        # 创建发布者
        self._start_pub = self.node.create_publisher(Bool, "/system/start_command", 10)
        self._emergency_pub = self.node.create_publisher(Bool, "/system/emergency", 10)

        # 创建订阅
        self.node.create_subscription(
            MissionState, "/system/mission_state", self._on_mission_state, 10
        )
        self.node.create_subscription(
            Odometry, "/sim/ground_truth", self._on_ground_truth, 10
        )
        self.node.create_subscription(
            UInt32, "/system/lap_count", self._on_lap_count, 10
        )
        self.node.create_subscription(
            Float64, "/system/lap_time", self._on_lap_time, 10
        )
        self.node.create_subscription(
            Float64, "/system/simulator_latency", self._on_latency, 10
        )

        # 启动定时器
        self._timer = QTimer()
        self._timer.timeout.connect(self._spin)
        self._timer.start(interval_ms)

    def pause(self):
        """暂停订阅（仿真停止时调用，防止残留消息覆盖 UI）"""
        if self._timer and self._timer.isActive():
            self._timer.stop()

    def resume(self):
        """恢复订阅（仿真启动时调用）"""
        if self._timer and not self._timer.isActive():
            self._timer.start()

    def _spin(self):
        """定期调用 spin_once"""
        if self.node:
            self._ros_imports['rclpy'].spin_once(self.node, timeout_sec=0.01)

    def _on_mission_state(self, msg):
        self.mission_state_received.emit(msg)

    def _on_ground_truth(self, msg):
        self.ground_truth_received.emit(msg)

    def _on_lap_count(self, msg):
        self.lap_count_received.emit(msg)

    def _on_lap_time(self, msg):
        self.lap_time_received.emit(msg)

    def _on_latency(self, msg):
        self.latency_received.emit(msg)

    def publish_start(self):
        """发布发车命令（如果 ROS 可用）"""
        if not self._available or not self._start_pub:
            return

        msg = self._ros_imports['Bool']()
        msg.data = True
        self._start_pub.publish(msg)
        self._spin()

    def publish_emergency(self):
        """发布急停命令（多次确保送达）"""
        if not self._available or not self._emergency_pub:
            return

        msg = self._ros_imports['Bool']()
        msg.data = True
        for _ in range(5):
            self._emergency_pub.publish(msg)
            self._spin()

    def stop(self):
        """停止订阅"""
        if self._timer:
            self._timer.stop()
            self._timer = None
        if self.node:
            self.node.destroy_node()
            self.node = None
        if self._available:
            rclpy = self._ros_imports['rclpy']
            if rclpy.ok():
                rclpy.shutdown()
