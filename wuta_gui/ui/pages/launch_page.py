"""启动页面 - 仿真启动和手动控制"""

from pathlib import Path

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QComboBox, QCheckBox, QRadioButton,
    QButtonGroup, QGroupBox, QMessageBox, QFrame, QScrollArea
)
from PyQt5.QtCore import Qt, pyqtSignal

from wuta_gui.core import modes, workspace
from wuta_gui.ui.theme import (
    COLORS, FONT_DISPLAY, FONT_LARGE, FONT_SMALL, FONT_NORMAL,
    font, groupbox_style, radio_check_style, button_style,
    combo_style, scroll_style
)


class LaunchPage(QWidget):
    """启动页面：控制仿真运行"""

    # 信号
    launch_requested = pyqtSignal(dict)  # 启动仿真请求
    stop_requested = pyqtSignal()       # 停止仿真请求
    manual_start_requested = pyqtSignal()  # 手动发车请求

    # 任务模式常量（集中定义于 core/modes.py）
    MODE_TRACKDRIVE = modes.MODE_TRACKDRIVE
    MODE_SKIDPAD = modes.MODE_SKIDPAD
    MODE_ACCELERATION = modes.MODE_ACCELERATION
    MODE_NAMES = modes.MODE_NAMES
    MODE_TRACK_PREFIX = modes.MODE_TRACK_PREFIX

    def __init__(self, wuta_root: str = None, parent=None):
        super().__init__(parent)
        self.wuta_root = Path(wuta_root) if wuta_root else None
        self._setup_ui()
        if self.wuta_root:
            self._load_tracks()

    def set_wuta_root(self, path: str):
        self.wuta_root = Path(path)
        self._load_tracks()
        self._load_params_files()

    def _setup_ui(self):
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(scroll_style())

        content = QWidget()
        content.setStyleSheet(f"background-color: {COLORS['bg_primary']};")
        layout = QVBoxLayout(content)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 16, 20, 16)

        # 标题
        title = QLabel("启动仿真")
        title.setFont(font(FONT_DISPLAY, bold=True))
        title.setStyleSheet(f"color: {COLORS['text_primary']};")
        layout.addWidget(title)

        # 任务模式选择
        mode_group = self._create_mode_group()
        layout.addWidget(mode_group)

        # 赛道选择
        track_group = self._create_track_group()
        layout.addWidget(track_group)

        # 参数配置选择
        params_group = self._create_params_group()
        layout.addWidget(params_group)

        # 选项区域
        options_group = self._create_options_group()
        layout.addWidget(options_group)

        # 控制按钮
        control_group = self._create_control_group()
        layout.addWidget(control_group)

        layout.addStretch()
        scroll.setWidget(content)
        main_layout.addWidget(scroll)

    def _create_mode_group(self) -> QGroupBox:
        group = QGroupBox("任务模式")
        group.setStyleSheet(groupbox_style())

        layout = QHBoxLayout(group)
        layout.setSpacing(12)

        self.mode_group = QButtonGroup()

        modes = [
            ("Trackdrive", self.MODE_TRACKDRIVE),
            ("Skidpad", self.MODE_SKIDPAD),
            ("Acceleration", self.MODE_ACCELERATION),
        ]

        for name, value in modes:
            rb = QRadioButton(name)
            rb.setStyleSheet(radio_check_style())
            rb.setProperty("mode_value", value)
            self.mode_group.addButton(rb, value)
            layout.addWidget(rb)

        # 默认选中 Trackdrive
        self.mode_group.button(self.MODE_TRACKDRIVE).setChecked(True)

        layout.addStretch()

        return group

    def _create_track_group(self) -> QGroupBox:
        group = QGroupBox("赛道选择")
        group.setStyleSheet(groupbox_style())

        # 外层垂直布局
        outer_layout = QVBoxLayout()
        outer_layout.setSpacing(6)

        # 第一行：赛道选择
        row_layout = QHBoxLayout()
        row_layout.setSpacing(12)

        track_label = QLabel("赛道文件:")
        track_label.setFont(font(FONT_NORMAL))
        track_label.setStyleSheet(f"color: {COLORS['text_primary']};")
        row_layout.addWidget(track_label)

        self.track_combo = QComboBox()
        self.track_combo.setMinimumWidth(240)
        self.track_combo.setStyleSheet(combo_style())
        row_layout.addWidget(self.track_combo)

        refresh_btn = QPushButton("刷新")
        refresh_btn.setFixedWidth(70)
        refresh_btn.setStyleSheet(button_style('default'))
        refresh_btn.clicked.connect(self._load_tracks)
        row_layout.addWidget(refresh_btn)

        row_layout.addStretch()
        outer_layout.addLayout(row_layout)

        # 第二行：警告标签
        self.track_warning_label = QLabel("")
        self.track_warning_label.setFont(font(FONT_SMALL))
        self.track_warning_label.setStyleSheet(f"color: {COLORS['warning']};")
        self.track_warning_label.hide()
        outer_layout.addWidget(self.track_warning_label)

        group.setLayout(outer_layout)

        return group

    def _create_params_group(self) -> QGroupBox:
        group = QGroupBox("参数配置")
        group.setStyleSheet(groupbox_style())

        layout = QHBoxLayout(group)
        layout.setSpacing(12)

        params_label = QLabel("参数文件:")
        params_label.setFont(font(FONT_NORMAL))
        params_label.setStyleSheet(f"color: {COLORS['text_primary']};")
        layout.addWidget(params_label)

        self.params_combo = QComboBox()
        self.params_combo.setMinimumWidth(240)
        self.params_combo.setStyleSheet(combo_style())
        layout.addWidget(self.params_combo)

        refresh_params_btn = QPushButton("刷新")
        refresh_params_btn.setFixedWidth(70)
        refresh_params_btn.setStyleSheet(button_style('default'))
        refresh_params_btn.clicked.connect(self._load_params_files)
        layout.addWidget(refresh_params_btn)

        layout.addStretch()

        return group

    def _load_params_files(self):
        """加载可用参数配置文件"""
        self.params_combo.clear()

        if self.wuta_root is None:
            self.params_combo.addItem("默认配置", "default")
            return

        params_dir = self.wuta_root / "wuta_gui" / "params"

        if not params_dir.exists():
            self.params_combo.addItem("默认配置", "default")
            return

        # 查找所有 YAML 参数文件
        param_files = sorted(params_dir.glob("*.yaml"))

        if not param_files:
            self.params_combo.addItem("默认配置", "default")
            return

        # 默认参数文件名
        default_file = "default_params.yaml"
        default_index = 0

        for i, param_path in enumerate(param_files):
            display_name = param_path.stem
            self.params_combo.addItem(display_name, str(param_path))
            if param_path.name == default_file:
                default_index = i

        # 默认选中 default_params.yaml
        self.params_combo.setCurrentIndex(default_index)

    def _load_tracks(self):
        """加载可用赛道文件"""
        self.track_combo.clear()

        if self.wuta_root is None:
            self.track_combo.addItem("默认赛道", "default")
            return

        tracks_dir = workspace.tracks_dir(self.wuta_root)

        if not tracks_dir.exists():
            self.track_combo.addItem("默认赛道", "default")
            return

        # 查找所有 YAML 赛道文件
        track_files = sorted(tracks_dir.glob("*.yaml"))

        if not track_files:
            self.track_combo.addItem("默认赛道", "default")
            return

        for track_path in track_files:
            display_name = track_path.stem
            self.track_combo.addItem(display_name, str(track_path))

        # 根据当前任务模式选择默认赛道
        self._select_default_track()

        # 连接信号进行校验
        self.mode_group.buttonClicked.connect(self._on_mode_changed)
        self.track_combo.currentTextChanged.connect(self._validate_track)

    def _select_default_track(self):
        """根据当前任务模式选择默认赛道"""
        current_mode = self.mode_group.checkedId()
        prefix = self.MODE_TRACK_PREFIX.get(current_mode, "")

        for i in range(self.track_combo.count()):
            track_name = self.track_combo.itemText(i)
            if track_name.startswith(prefix):
                self.track_combo.setCurrentIndex(i)
                return

        # 如果没有匹配的，选中第一个
        if self.track_combo.count() > 0:
            self.track_combo.setCurrentIndex(0)

    def _on_mode_changed(self):
        """任务模式改变时，更新默认赛道并校验"""
        self._select_default_track()
        self._validate_track()

    def _validate_track(self):
        """校验赛道是否与任务模式匹配"""
        current_mode = self.mode_group.checkedId()
        prefix = self.MODE_TRACK_PREFIX.get(current_mode, "")
        track_name = self.track_combo.currentText()

        if track_name == "默认赛道" or not prefix:
            self.track_warning_label.hide()
            return

        if not track_name.lower().startswith(prefix.lower()):
            mode_name = self.MODE_NAMES.get(current_mode, "")
            self.track_warning_label.setText(
                f"⚠ 当前赛道 '{track_name}' 可能不匹配 {mode_name} 模式"
            )
            self.track_warning_label.show()
        else:
            self.track_warning_label.hide()

    def _create_options_group(self) -> QGroupBox:
        group = QGroupBox("启动选项")
        group.setStyleSheet(groupbox_style())

        layout = QHBoxLayout(group)
        layout.setSpacing(16)

        # RViz 选项（默认启用）
        self.rviz_check = QCheckBox("启动 RViz 可视化")
        self.rviz_check.setStyleSheet(radio_check_style())
        self.rviz_check.setChecked(True)
        layout.addWidget(self.rviz_check)

        # 自动发车选项（默认启用）
        self.auto_start_check = QCheckBox("自动发车")
        self.auto_start_check.setStyleSheet(radio_check_style())
        self.auto_start_check.setChecked(True)
        self.auto_start_check.toggled.connect(self._on_auto_start_toggled)
        layout.addWidget(self.auto_start_check)

        layout.addStretch()

        return group

    def _on_auto_start_toggled(self, checked: bool):
        """自动发车选项切换时，更新发车按钮状态"""
        if hasattr(self, 'start_button'):
            self.start_button.setVisible(not checked)

    def _create_control_group(self) -> QGroupBox:
        group = QGroupBox("仿真控制")
        group.setStyleSheet(groupbox_style())

        layout = QHBoxLayout(group)
        layout.setSpacing(10)

        # 启动按钮
        self.launch_button = QPushButton("▶  启动仿真")
        self.launch_button.setMinimumHeight(44)
        self.launch_button.setFont(font(FONT_LARGE, bold=True))
        self.launch_button.setStyleSheet(button_style('success'))
        self.launch_button.clicked.connect(self._on_launch_clicked)
        layout.addWidget(self.launch_button)

        # 手动发车按钮（默认隐藏，因为自动发车默认启用）
        self.start_button = QPushButton("发车")
        self.start_button.setMinimumHeight(44)
        self.start_button.setFont(font(FONT_LARGE, bold=True))
        self.start_button.setStyleSheet(button_style('warning'))
        self.start_button.clicked.connect(self.manual_start_requested.emit)
        self.start_button.hide()
        layout.addWidget(self.start_button)

        # 停止按钮
        self.stop_button = QPushButton("■  停止仿真")
        self.stop_button.setMinimumHeight(44)
        self.stop_button.setFont(font(FONT_LARGE, bold=True))
        self.stop_button.setStyleSheet(button_style('danger'))
        self.stop_button.clicked.connect(self._on_stop_clicked)
        self.stop_button.setEnabled(False)
        layout.addWidget(self.stop_button)

        # 急停按钮
        self.emergency_button = QPushButton("🛑 急停")
        self.emergency_button.setMinimumHeight(44)
        self.emergency_button.setFont(font(FONT_LARGE, bold=True))
        self.emergency_button.setStyleSheet(button_style('danger'))
        self.emergency_button.clicked.connect(self._on_emergency_clicked)
        layout.addWidget(self.emergency_button)

        layout.addStretch()

        return group

    def _on_launch_clicked(self):
        """启动仿真"""
        mode = self.mode_group.checkedId()

        # 获取选中的赛道文件
        track_file = self.track_combo.currentData() if hasattr(self, 'track_combo') else "default"
        if track_file is None:
            track_file = "default"

        # 获取选中的参数配置文件
        params_file = self.params_combo.currentData() if hasattr(self, 'params_combo') else "default"
        if params_file is None:
            params_file = "default"

        params = {
            "mission_mode": mode,
            "track_file": track_file,
            "params_file": params_file,
            "launch_rviz": self.rviz_check.isChecked(),
            "auto_start": self.auto_start_check.isChecked(),
        }

        # 检查是否需要先构建
        if self.wuta_root and not workspace.is_built(self.wuta_root):
            QMessageBox.warning(
                self,
                "未构建",
                "检测到项目尚未构建，请先完成构建再启动仿真。"
            )
            return

        # 发射信号
        self.launch_requested.emit(params)

        # 更新按钮状态
        self.launch_button.setEnabled(False)
        self.stop_button.setEnabled(True)

    def _is_track_mode_matched(self, mode: int, track_name: str) -> bool:
        """检查赛道是否与任务模式匹配"""
        if track_name == "默认赛道":
            return True
        prefix = self.MODE_TRACK_PREFIX.get(mode, "")
        if not prefix:
            return True
        return track_name.lower().startswith(prefix.lower())

    def _on_stop_clicked(self):
        """停止仿真"""
        reply = QMessageBox.question(
            self,
            "停止仿真",
            "确定要停止仿真吗？",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.stop_requested.emit()
            self.launch_button.setEnabled(True)
            self.stop_button.setEnabled(False)

    def _on_emergency_clicked(self):
        """急停 - 仅发送制动信号，不停止仿真进程"""
        reply = QMessageBox.warning(
            self,
            "紧急停止",
            "确定要触发紧急停止吗？\n车辆将立即停止运行！",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            # 通过主窗口的 system_subscriber 发送急停信号
            main_window = self._find_main_window()
            if main_window and hasattr(main_window, 'system_subscriber'):
                main_window.system_subscriber.publish_emergency()
            # 不停止仿真进程，仅让车辆制动
            if main_window:
                main_window._set_bottom("🛑 急停已触发，车辆已制动", 'danger')

    def _find_main_window(self):
        """查找主窗口"""
        from wuta_gui.ui.main_window import MainWindow
        parent = self.parent()
        while parent:
            if isinstance(parent, MainWindow):
                return parent
            parent = parent.parent()
        return None

    def on_simulation_stopped(self):
        """仿真停止后的回调"""
        self.launch_button.setEnabled(True)
        self.stop_button.setEnabled(False)
