"""主窗口 - 常驻顶栏 + 侧边栏 + 页面切换（Apple 风格）"""

from pathlib import Path

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QPushButton, QLabel, QFrame, QMessageBox
)
from PyQt5.QtCore import Qt

from wuta_gui.core.launcher import Launcher
from wuta_gui.core.system_subscriber import SystemSubscriber
from wuta_gui.ui.status_bar import StatusBar
from wuta_gui.ui.timing_panel import TimingPanel
from wuta_gui.ui.pages.build_page import BuildPage
from wuta_gui.ui.pages.launch_page import LaunchPage
from wuta_gui.ui.pages.params_page import ParamsPage
from wuta_gui.ui.pages.log_page import LogPage
from wuta_gui.ui.theme import (
    COLORS, FONT_DISPLAY, FONT_LARGE, FONT_SMALL,
    font, sidebar_button_style
)


class MainWindow(QMainWindow):
    """主窗口：常驻顶栏 + 侧边栏 + 页面切换"""

    # 任务模式显示名称映射（使用整数常量，避免依赖 ROS 消息导入）
    MODE_DISPLAY_NAMES = {
        0: "TRACKDRIVE",     # MISSION_TRACKDRIVE
        1: "SKIDPAD",        # MISSION_SKIDPAD
        2: "ACCELERATION",   # MISSION_ACCELERATION
    }

    # 运行状态显示名称映射
    STATE_DISPLAY_NAMES = {
        0: "IDLE",           # 空闲
        1: "READY",          # 就绪
        2: "INSPECTION",     # 检查
        3: "EXPLORE",        # 探索
        4: "MAPPING_DONE",   # 建图完成
        5: "RACE",           # 比赛
        6: "FINISH",         # 完成
        7: "EMERGENCY",      # 急停
    }

    # 任务模式常量
    MISSION_TRACKDRIVE = 0
    MISSION_SKIDPAD = 1
    MISSION_ACCELERATION = 2

    def __init__(self, wuta_root: str, parent=None):
        super().__init__(parent)
        self.wuta_root = Path(wuta_root)

        self.setWindowTitle("WUTA SIM Panel")
        self.setMinimumSize(1000, 680)
        self.resize(1200, 780)

        # 核心组件
        self.launcher = Launcher(wuta_root)
        self.system_subscriber = SystemSubscriber()

        # 计时数据缓存
        self._lap_times_cache = []
        self._current_lap_count = 0

        # 直线加速实时状态（距离/速度来自真值，用时来自 lap_time）
        self._accel_elapsed = 0.0
        self._accel_finished = False
        self._accel_last_distance = 0.0
        self._accel_last_speed = 0.0
        self._accel_track_length = 75.0  # 赛道长度（米），可从参数动态读取

        # 构建 UI
        self._setup_ui()
        self._connect_signals()

        # 启动状态订阅
        self.system_subscriber.start(interval_ms=50)

        # 检查 ROS 是否可用
        if not self.system_subscriber.available:
            self._set_bottom("  ⚠ 未检测到 ROS 环境，请先 source ROS 2 环境", 'warning')

        # 检查是否已构建
        self._check_build_status()

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        central.setStyleSheet(f"background-color: {COLORS['bg_primary']};")
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 顶栏：左侧车辆状态 + 右侧比赛计时
        top_bar = QWidget()
        top_bar.setFixedHeight(160)
        top_bar.setStyleSheet(f"""
            background-color: {COLORS['top_bar']};
            border-bottom: 1px solid {COLORS['separator']};
        """)
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(16, 12, 16, 12)
        top_layout.setSpacing(16)

        # 左侧：车辆状态
        self.status_bar = StatusBar()
        top_layout.addWidget(self.status_bar, 1)

        # 分隔线
        vline = QFrame()
        vline.setFrameShape(QFrame.VLine)
        vline.setStyleSheet(f"background-color: {COLORS['separator']};")
        vline.setFixedWidth(1)
        top_layout.addWidget(vline)

        # 右侧：比赛计时
        self.timing_panel = TimingPanel()
        top_layout.addWidget(self.timing_panel, 1)

        layout.addWidget(top_bar)

        # 侧边栏 + 页面区域
        content = QHBoxLayout()
        content.setSpacing(0)

        sidebar = self._create_sidebar()
        content.addWidget(sidebar)

        # 页面堆栈
        self.pages = QStackedWidget()
        self.pages.setStyleSheet(f"background-color: {COLORS['bg_primary']};")

        self.build_page = BuildPage(str(self.wuta_root))
        self.launch_page = LaunchPage()
        self.launch_page.set_wuta_root(str(self.wuta_root))
        self.params_page = ParamsPage(str(self.wuta_root))
        self.log_page = LogPage()

        self.pages.addWidget(self.build_page)    # 0
        self.pages.addWidget(self.launch_page)   # 1
        self.pages.addWidget(self.params_page)   # 2
        self.pages.addWidget(self.log_page)      # 3

        content.addWidget(self.pages, 1)
        layout.addLayout(content)

        # 底栏
        self.bottom_bar = QLabel("  就绪")
        self.bottom_bar.setFont(font(FONT_SMALL))
        self.bottom_bar.setStyleSheet(f"""
            color: {COLORS['text_secondary']};
            padding: 8px 20px;
            background-color: {COLORS['bg_secondary']};
            border-top: 1px solid {COLORS['separator']};
        """)
        self.bottom_bar.setFixedHeight(32)
        layout.addWidget(self.bottom_bar)

    def _create_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setFixedWidth(140)
        sidebar.setStyleSheet(f"""
            background-color: {COLORS['bg_sidebar']};
            border-right: 1px solid {COLORS['separator']};
        """)
        layout = QVBoxLayout(sidebar)
        layout.setSpacing(4)
        layout.setContentsMargins(10, 16, 10, 10)

        # Logo 区域
        logo_label = QLabel()
        logo_label.setAlignment(Qt.AlignCenter)
        logo_label.setStyleSheet("padding: 8px 8px 12px 8px;")

        logo_path = Path(__file__).parent.parent / "assets" / "logo.png"
        if logo_path.exists():
            from PyQt5.QtGui import QPixmap
            pixmap = QPixmap(str(logo_path))
            pixmap = pixmap.scaledToHeight(40, Qt.SmoothTransformation)
            logo_label.setPixmap(pixmap)
        else:
            logo_label.setText("WUTA")
            logo_label.setFont(font(FONT_DISPLAY, bold=True))
            logo_label.setStyleSheet(f"color: {COLORS['accent']}; padding: 8px 8px 12px 8px;")

        layout.addWidget(logo_label)

        # 分隔
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"background-color: {COLORS['separator']}; max-height: 1px;")
        layout.addWidget(sep)
        layout.addSpacing(8)

        buttons = [
            ("🔨  构建", 0),
            ("📋  启动", 1),
            ("⚙️  调参", 2),
            ("📝  日志", 3),
        ]

        self.sidebar_buttons = []
        for text, index in buttons:
            btn = QPushButton(text)
            btn.setFixedHeight(42)
            btn.setCheckable(True)
            btn.setFont(font(FONT_LARGE, bold=False))
            btn.setStyleSheet(sidebar_button_style())
            btn.clicked.connect(lambda checked, i=index: self._on_sidebar_clicked(i))
            self.sidebar_buttons.append(btn)
            layout.addWidget(btn)

        layout.addStretch()

        # 底部版本信息
        version_label = QLabel("v1.0.0")
        version_label.setFont(font(FONT_SMALL))
        version_label.setStyleSheet(f"color: {COLORS['text_tertiary']}; padding: 4px;")
        version_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(version_label)

        return sidebar

    def _on_sidebar_clicked(self, index: int):
        if index == 0 and self._is_built():
            reply = QMessageBox.question(
                self, "已构建",
                "检测到已有构建产物。\n是否重新构建？\n（选择否将跳转到启动页面）",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
            )
            if reply == QMessageBox.No:
                index = 1
            elif reply == QMessageBox.Cancel:
                return

        self.pages.setCurrentIndex(index)
        for i, btn in enumerate(self.sidebar_buttons):
            btn.setChecked(i == index)

    def _check_build_status(self):
        if self._is_built():
            self.pages.setCurrentIndex(1)
            self.sidebar_buttons[1].setChecked(True)
            self._set_bottom("检测到历史构建，已跳过构建步骤", 'normal')
        else:
            self.pages.setCurrentIndex(0)
            self.sidebar_buttons[0].setChecked(True)
            self._set_bottom("请先完成首次构建", 'normal')
            self.sidebar_buttons[1].setEnabled(False)
            self.sidebar_buttons[2].setEnabled(False)

    def _is_built(self) -> bool:
        fsd_install = self.wuta_root / "WUTA-FSD/ros2_ws/install/setup.bash"
        sim_install = self.wuta_root / "WUTA-SIM/install/setup.bash"
        return fsd_install.exists() and sim_install.exists()

    def _connect_signals(self):
        self.build_page.request_switch_to_launch.connect(self._switch_to_launch)
        self.build_page.build_finished.connect(self._on_build_finished)
        self.system_subscriber.mission_state_received.connect(self._on_mission_state_received)
        self.system_subscriber.ground_truth_received.connect(self._on_ground_truth_received)
        self.system_subscriber.lap_count_received.connect(self._on_lap_count_received)
        self.system_subscriber.lap_time_received.connect(self._on_lap_time_received)
        self.system_subscriber.latency_received.connect(self._on_latency_received)
        self.launcher.process_started.connect(self._on_simulation_started)
        self.launcher.process_finished.connect(self._on_simulation_finished)
        self.launcher.log_line.connect(self._on_log_line)
        self.launch_page.launch_requested.connect(self._on_launch_requested)
        self.launch_page.stop_requested.connect(self._on_stop_requested)
        self.launch_page.manual_start_requested.connect(self._on_manual_start_requested)
        self.params_page.feedback.connect(self._on_param_feedback)

    def _on_build_finished(self, success: bool, message: str):
        if success:
            self.sidebar_buttons[1].setEnabled(True)
            self.sidebar_buttons[2].setEnabled(True)
            self._set_bottom("构建完成，可以启动仿真", 'success')

    def _switch_to_launch(self):
        self.pages.setCurrentIndex(1)
        for i, btn in enumerate(self.sidebar_buttons):
            btn.setChecked(i == 1)

    def _on_mission_state_received(self, msg):
        """处理 mission_state 消息"""
        mode_name = self.MODE_DISPLAY_NAMES.get(msg.mission_mode, "未知")
        self.status_bar.set_mode(mode_name)
        self.timing_panel.set_mode(self._mode_to_string(msg.mission_mode))

        state_name = self.STATE_DISPLAY_NAMES.get(msg.state, "未知")
        self.status_bar.set_state(state_name)

        if hasattr(self, '_last_mission_mode') and self._last_mission_mode != msg.mission_mode:
            self._lap_times_cache.clear()
            self._current_lap_count = 0
            self._accel_elapsed = 0.0
            self._accel_finished = False
            self._accel_last_distance = 0.0
            self._accel_last_speed = 0.0
        self._last_mission_mode = msg.mission_mode

        # 直线加速模式：动态读取赛道长度配置
        if msg.mission_mode == self.MISSION_ACCELERATION:
            self._load_track_length_from_config()

    def _on_ground_truth_received(self, msg):
        """处理 ground_truth 消息"""
        position = msg.pose.pose.position
        velocity = msg.twist.twist.linear
        speed = (velocity.x * velocity.x + velocity.y * velocity.y) ** 0.5

        import math
        orientation = msg.pose.pose.orientation
        yaw = math.atan2(
            2.0 * (orientation.w * orientation.z + orientation.x * orientation.y),
            1.0 - 2.0 * (orientation.y * orientation.y + orientation.z * orientation.z)
        )
        yaw_deg = math.degrees(yaw)

        self.status_bar.set_velocity(speed)
        self.status_bar.set_pose(position.x, position.y, yaw_deg)

        # 直线加速：从真值实时更新距离/速度
        mission_mode = getattr(self, '_last_mission_mode', None)
        if mission_mode == self.MISSION_ACCELERATION:
            track_length = getattr(self, '_accel_track_length', 75.0)
            distance = max(0.0, min(track_length, position.x))
            self._accel_last_distance = distance
            self._accel_last_speed = speed
            self.timing_panel.update_acceleration(
                distance=distance,
                speed=speed,
                elapsed=self._accel_elapsed,
                finished=self._accel_finished,
                track_length=track_length
            )

    def _on_latency_received(self, msg):
        """处理 simulator_latency 消息（单位 s → ms）"""
        self.status_bar.set_latency(msg.data * 1000.0)

    def _on_lap_count_received(self, msg):
        """处理 lap_count 消息（mission_manager 仅对 trackdrive 发布正式圈次）"""
        self._current_lap_count = msg.data
        mission_mode = getattr(self, '_last_mission_mode', self.MISSION_TRACKDRIVE)
        if mission_mode != self.MISSION_TRACKDRIVE:
            return
        self.timing_panel.update_trackdrive_lap(
            current_lap=msg.data,
            total_laps=3,
            last_lap_time=self._lap_times_cache[-1] if self._lap_times_cache else None,
            all_times=self._lap_times_cache.copy()
        )

    def _on_lap_time_received(self, msg):
        """处理 lap_time 消息"""
        lap_time = msg.data
        if lap_time not in self._lap_times_cache:
            self._lap_times_cache.append(lap_time)

        mission_mode = getattr(self, '_last_mission_mode', self.MISSION_TRACKDRIVE)
        if mission_mode == self.MISSION_TRACKDRIVE:
            self.timing_panel.update_trackdrive_lap(
                current_lap=self._current_lap_count,
                total_laps=3,
                last_lap_time=lap_time,
                all_times=self._lap_times_cache.copy()
            )
        elif mission_mode == self.MISSION_SKIDPAD:
            self.timing_panel.update_skidpad(
                segment=len(self._lap_times_cache),
                total_segments=4,
                segment_time=lap_time,
                all_segments=self._lap_times_cache.copy()
            )
        elif mission_mode == self.MISSION_ACCELERATION:
            self._accel_elapsed = lap_time
            self._accel_finished = True
            track_length = getattr(self, '_accel_track_length', 75.0)
            self.timing_panel.update_acceleration(
                distance=self._accel_last_distance,
                speed=self._accel_last_speed,
                elapsed=lap_time,
                finished=True,
                track_length=track_length
            )

    def _mode_to_string(self, mission_mode: int) -> str:
        mode_map = {
            self.MISSION_TRACKDRIVE: "TRACKDRIVE",
            self.MISSION_SKIDPAD: "SKIDPAD",
            self.MISSION_ACCELERATION: "ACCELERATION",
        }
        return mode_map.get(mission_mode, "TRACKDRIVE")

    def set_accel_track_length(self, length: float):
        """设置直线加速赛道长度（动态更新 GUI 进度条范围）

        Args:
            length: 赛道长度（米）
        """
        self._accel_track_length = max(1.0, float(length))

    def _load_track_length_from_config(self):
        """从赛道配置文件中读取直线加速赛道长度"""
        try:
            import yaml
            track_file = getattr(self, '_last_track_file', None)
            if track_file is None:
                # 默认读取 acceleration.yaml
                track_path = Path(self.wuta_root) / "WUTA-SIM" / "perception_simulation" / "tracks" / "acceleration.yaml"
            else:
                track_path = Path(self.wuta_root) / "WUTA-SIM" / "perception_simulation" / "tracks" / f"{track_file}.yaml"

            if track_path.exists():
                with open(track_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                if config and 'track' in config and 'geometry' in config['track']:
                    geo = config['track']['geometry']
                    # 优先使用 finish_line_x，其次 acceleration_distance
                    finish_x = geo.get('finish_line_x', geo.get('acceleration_distance', 75.0))
                    self.set_accel_track_length(finish_x)
        except Exception:
            pass  # 读取失败时使用默认值 75m

    def _on_launch_requested(self, params: dict):
        success = self.launcher.launch(params)
        if success:
            self.log_page.set_log_file(self.launcher.get_log_file())
        else:
            self._set_bottom("启动失败", 'danger')

    def _on_stop_requested(self):
        self.launcher.stop()

    def _on_manual_start_requested(self):
        """处理手动发车请求"""
        self.system_subscriber.publish_start()
        self._set_bottom("手动发车信号已发送", 'success')

    def _on_simulation_started(self, pid: int):
        self._set_bottom(f"  仿真运行中  (PID: {pid})", 'success')
        # 恢复 ROS 订阅
        self.system_subscriber.resume()
        self.timing_panel.start_race()

    def _on_simulation_finished(self, exit_code: int):
        self._set_bottom(f"  仿真已停止  (退出码: {exit_code})", 'warning')
        # 暂停 ROS 订阅，防止残留消息覆盖重置后的显示
        self.system_subscriber.pause()
        self.timing_panel.stop_race()
        self.status_bar.reset_all()
        self.timing_panel.reset_race(show_waiting=True)
        self._lap_times_cache.clear()
        self._current_lap_count = 0
        self._accel_elapsed = 0.0
        self._accel_finished = False
        self._accel_last_distance = 0.0
        self._accel_last_speed = 0.0
        self._last_mission_mode = None

    def _on_log_line(self, level, message):
        self.log_page.append_log(level, message)

    def _on_param_feedback(self, level: str, message: str):
        if level == "success":
            self._set_bottom(f"  ✓ {message}", 'success')
        elif level == "warning":
            self._set_bottom(f"  ⚠ {message}", 'warning')
        elif level == "error":
            self._set_bottom(f"  ✗ {message}", 'danger')
        else:
            self._set_bottom(f"  {message}", 'normal')

    def _set_bottom(self, text: str, status: str = 'normal'):
        color_map = {
            'success': COLORS['success'],
            'warning': COLORS['warning'],
            'danger': COLORS['danger'],
            'normal': COLORS['text_secondary'],
        }
        color = color_map.get(status, COLORS['text_secondary'])
        self.bottom_bar.setText(text)
        self.bottom_bar.setStyleSheet(f"""
            color: {color};
            padding: 8px 20px;
            background-color: {COLORS['bg_secondary']};
            border-top: 1px solid {COLORS['separator']};
            font-size: {FONT_SMALL}px;
        """)

    def closeEvent(self, event):
        self.system_subscriber.stop()
        if self.launcher.is_running():
            self.launcher.stop()
        event.accept()
