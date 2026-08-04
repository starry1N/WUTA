"""顶栏状态组件 - Apple 风格（保证文字完整显示）"""

from PyQt5.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QFrame

from wuta_gui.ui.theme import (
    COLORS, FONT_NORMAL, FONT_SMALL,
    font, mono_font
)


class StatusBar(QWidget):
    """常驻顶栏：显示车辆状态信息

    布局策略：
    - 左侧：模式 + 状态（上下两行，不限制宽度）
    - 右侧：5 个数据项（2x3 网格），每项有足够空间
    - 优先保证文字完整显示，不使用固定宽度限制
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(136)
        self.setStyleSheet(f"background-color: {COLORS['top_bar']};")
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # === 左侧：模式 + 状态 ===
        status_widget = QFrame()
        status_widget.setMinimumWidth(170)
        status_widget.setStyleSheet(f"""
            background-color: {COLORS['bg_secondary']};
            border: 1px solid {COLORS['separator']};
            border-radius: 12px;
        """)
        status_layout = QVBoxLayout(status_widget)
        status_layout.setContentsMargins(14, 10, 14, 10)
        status_layout.setSpacing(8)

        # 任务模式
        mode_box = QVBoxLayout()
        mode_box.setSpacing(2)
        lbl_mode_title = QLabel("任务模式")
        lbl_mode_title.setFont(font(FONT_SMALL))
        lbl_mode_title.setStyleSheet(f"color: {COLORS['text_secondary']};")
        self.lbl_mode = QLabel("—")
        self.lbl_mode.setFont(font(FONT_NORMAL, bold=True))
        self.lbl_mode.setStyleSheet(f"color: {COLORS['accent']};")
        mode_box.addWidget(lbl_mode_title)
        mode_box.addWidget(self.lbl_mode)
        status_layout.addLayout(mode_box)

        # 运行状态
        state_box = QVBoxLayout()
        state_box.setSpacing(2)
        lbl_state_title = QLabel("运行状态")
        lbl_state_title.setFont(font(FONT_SMALL))
        lbl_state_title.setStyleSheet(f"color: {COLORS['text_secondary']};")
        self.lbl_state = QLabel("—")
        self.lbl_state.setFont(font(FONT_NORMAL, bold=True))
        self.lbl_state.setStyleSheet(f"color: {COLORS['text_primary']};")
        state_box.addWidget(lbl_state_title)
        state_box.addWidget(self.lbl_state)
        status_layout.addLayout(state_box)

        status_layout.addStretch()
        layout.addWidget(status_widget)

        # === 右侧：数据项网格（2 行 × 3 列）===
        grid_widget = QWidget()
        grid_layout = QVBoxLayout(grid_widget)
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.setSpacing(6)

        # 第一行：车速 / X / Y
        row1 = QHBoxLayout()
        row1.setSpacing(8)
        self.lbl_speed = self._create_data_item("车速", "—", "m/s")
        self.lbl_x = self._create_data_item("X", "—", "m")
        self.lbl_y = self._create_data_item("Y", "—", "m")
        for w in [self.lbl_speed, self.lbl_x, self.lbl_y]:
            row1.addWidget(w, 1)
        grid_layout.addLayout(row1)

        # 第二行：航向 / 延迟 / (空白)
        row2 = QHBoxLayout()
        row2.setSpacing(8)
        self.lbl_yaw = self._create_data_item("航向", "—", "°")
        self.lbl_latency = self._create_data_item("延迟", "—", "ms")
        row2.addWidget(self.lbl_yaw, 1)
        row2.addWidget(self.lbl_latency, 1)
        placeholder = QWidget()
        row2.addWidget(placeholder, 1)
        grid_layout.addLayout(row2)

        grid_layout.addStretch()
        layout.addWidget(grid_widget, 1)

    def _create_data_item(self, name: str, value: str, unit: str) -> QFrame:
        """创建数据项 - 保证文字完整显示"""
        widget = QFrame()
        widget.setMinimumWidth(95)
        widget.setStyleSheet(f"""
            background-color: {COLORS['bg_secondary']};
            border: 1px solid {COLORS['separator']};
            border-radius: 8px;
        """)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(2)

        # 名称行（名称 + 单位）
        name_row = QHBoxLayout()
        name_row.setSpacing(4)
        lbl_name = QLabel(name)
        lbl_name.setFont(font(FONT_SMALL))
        lbl_name.setStyleSheet(f"color: {COLORS['text_secondary']};")
        lbl_unit = QLabel(unit)
        lbl_unit.setFont(font(FONT_SMALL))
        lbl_unit.setStyleSheet(f"color: {COLORS['text_tertiary']};")
        name_row.addWidget(lbl_name)
        name_row.addWidget(lbl_unit)
        name_row.addStretch()

        # 数值（使用较小字体保证长数值完整显示）
        lbl_value = QLabel(value)
        lbl_value.setFont(mono_font(FONT_SMALL, bold=True))
        lbl_value.setStyleSheet(f"color: {COLORS['text_primary']};")

        layout.addLayout(name_row)
        layout.addWidget(lbl_value)

        widget.value_label = lbl_value
        return widget

    # === 更新接口 ===

    def reset_all(self):
        self.lbl_mode.setText("—")
        self.lbl_state.setText("—")
        self.lbl_speed.value_label.setText("—")
        self.lbl_x.value_label.setText("—")
        self.lbl_y.value_label.setText("—")
        self.lbl_yaw.value_label.setText("—")
        self.lbl_latency.value_label.setText("—")
        # 强制重绘确保 UI 更新
        self.update()

    def set_mode(self, mode: str):
        self.lbl_mode.setText(mode or "—")

    def set_state(self, state: str):
        self.lbl_state.setText(state or "—")

    def set_pose(self, x: float, y: float, yaw: float):
        self.lbl_x.value_label.setText(f"{x:.2f}")
        self.lbl_y.value_label.setText(f"{y:.2f}")
        self.lbl_yaw.value_label.setText(f"{yaw:.1f}")

    def set_velocity(self, speed: float):
        self.lbl_speed.value_label.setText(f"{speed:.1f}")

    def set_latency(self, ms):
        """设置延迟（修复 None 值 bug）"""
        if ms is None:
            self.lbl_latency.value_label.setText("—")
        else:
            self.lbl_latency.value_label.setText(f"{ms:.1f}")
