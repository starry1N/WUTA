"""比赛计时面板 - Apple 风格（保证文字完整显示）"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QProgressBar
)
from PyQt5.QtCore import Qt, QTimer

from wuta_gui.ui.theme import (
    COLORS, FONT_TITLE, FONT_LARGE, FONT_NORMAL, FONT_SMALL,
    font, mono_font
)


class TimingPanel(QWidget):
    """比赛计时面板 - 三种赛项独立布局

    设计原则：
    - 计时基于仿真事件（穿过终点线）
    - 保证所有文字完整显示，不使用固定宽度限制
    - 重要数据用大字醒目显示
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_mode = None
        self._is_running = False

        # 高速循迹数据
        self._lap_times = []
        self._current_lap = 0
        self._total_laps = 3

        # 八字环绕数据
        self._segment_times = []
        self._skidpad_current = 0

        # 直线加速数据
        self._accel_distance = 0.0
        self._accel_speed = 0.0
        self._accel_elapsed = 0.0
        self._accel_finished = False

        # 显示刷新计时器
        self._display_timer = QTimer(self)
        self._display_timer.setInterval(100)
        self._display_timer.timeout.connect(self._refresh_display)

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.content_frame = QFrame()
        self.content_layout = QVBoxLayout(self.content_frame)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(6)
        layout.addWidget(self.content_frame, 1)

        self._show_waiting()

    def _clear_content(self):
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    def _show_waiting(self):
        label = QLabel("等待发车...")
        label.setFont(font(FONT_NORMAL))
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet(f"""
            color: {COLORS['text_secondary']};
            background-color: {COLORS['bg_secondary']};
            border: 1px solid {COLORS['separator']};
            border-radius: 12px;
            padding: 20px;
        """)
        self.content_layout.addWidget(label)

    # === 控制接口 ===

    def start_race(self):
        self._is_running = True
        self._display_timer.start()

    def stop_race(self):
        self._is_running = False
        self._display_timer.stop()

    def reset_race(self, show_waiting: bool = False):
        self._is_running = False
        self._display_timer.stop()
        self._lap_times.clear()
        self._current_lap = 0
        self._total_laps = 3
        self._segment_times.clear()
        self._skidpad_current = 0
        self._accel_distance = 0.0
        self._accel_speed = 0.0
        self._accel_elapsed = 0.0
        self._accel_finished = False
        # 仅在仿真结束时重置为默认状态（等待发车）
        if show_waiting:
            self.current_mode = None
            self._clear_content()
            self._show_waiting()

    def set_mode(self, mode: str):
        if self.current_mode == mode:
            return
        self.current_mode = mode
        self.reset_race()
        self._clear_content()

        if mode == "TRACKDRIVE":
            self._setup_trackdrive_ui()
        elif mode == "SKIDPAD":
            self._setup_skidpad_ui()
        elif mode == "ACCELERATION":
            self._setup_acceleration_ui()

    def _create_info_card(self, title: str, value: str = "—", value_color: str = None,
                          mono: bool = True, title_size: int = FONT_SMALL,
                          value_size: int = FONT_LARGE) -> QFrame:
        """创建信息卡片 - 不限制宽度，保证文字完整"""
        card = QFrame()
        card.setStyleSheet(f"""
            background-color: {COLORS['bg_secondary']};
            border: 1px solid {COLORS['separator']};
            border-radius: 10px;
        """)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(2)

        lbl_title = QLabel(title)
        lbl_title.setFont(font(title_size))
        lbl_title.setStyleSheet(f"color: {COLORS['text_secondary']};")

        lbl_value = QLabel(value)
        if mono:
            lbl_value.setFont(mono_font(value_size, bold=True))
        else:
            lbl_value.setFont(font(value_size, bold=True))
        color = value_color or COLORS['text_primary']
        lbl_value.setStyleSheet(f"color: {color};")

        layout.addWidget(lbl_title)
        layout.addWidget(lbl_value)

        card.value_label = lbl_value
        return card

    # === 高速循迹模式 ===

    def _setup_trackdrive_ui(self):
        """高速循迹 UI - 横向卡片布局"""
        # 主行：圈次 + 累计 + 上一圈时间
        main_row = QHBoxLayout()
        main_row.setSpacing(8)

        # 圈次卡片
        self.td_lap_card = self._create_info_card(
            "圈次", "0 / 3", mono=False, value_size=FONT_LARGE
        )
        main_row.addWidget(self.td_lap_card, 1)

        # 累计卡片
        self.td_accum_card = self._create_info_card(
            "累计", "00:00.000", value_size=FONT_NORMAL
        )
        main_row.addWidget(self.td_accum_card, 1)

        # 上一圈时间卡片（突出显示）
        self.td_last_card = self._create_info_card(
            "上一圈用时", "--",
            value_color=COLORS['accent'], value_size=FONT_TITLE
        )
        main_row.addWidget(self.td_last_card, 1)

        self.content_layout.addLayout(main_row)

        # 底部：各圈时间
        laps_row = QHBoxLayout()
        laps_row.setSpacing(8)
        self.td_lap_labels = []
        for i in range(3):
            lap_card = self._create_info_card(
                f"第{i+1}圈", "--",
                value_color=COLORS['text_tertiary'], value_size=FONT_NORMAL
            )
            laps_row.addWidget(lap_card, 1)
            self.td_lap_labels.append(lap_card.value_label)

        self.content_layout.addLayout(laps_row)

    def _refresh_display(self):
        if not self.current_mode:
            return
        if self.current_mode == "TRACKDRIVE":
            self._refresh_trackdrive()
        elif self.current_mode == "SKIDPAD":
            self._refresh_skidpad()
        elif self.current_mode == "ACCELERATION":
            self._refresh_acceleration()

    def _refresh_trackdrive(self):
        total = sum(self._lap_times)
        self.td_accum_card.value_label.setText(self._format_time(int(total * 1000)))

    def update_trackdrive_lap(self, current_lap: int, total_laps: int,
                               last_lap_time: float = None, all_times: list = None):
        """更新圈时数据"""
        # 如果 UI 尚未初始化（消息在 set_mode 之前到达），自动初始化
        if not hasattr(self, 'td_lap_card'):
            self._setup_trackdrive_ui()

        if all_times is not None:
            self._lap_times = [t for t in all_times if t is not None]
        self._current_lap = current_lap
        self._total_laps = total_laps

        self.td_lap_card.value_label.setText(f"{current_lap} / {total_laps}")

        # 更新各圈时间
        for i in range(3):
            if i < len(self._lap_times):
                self.td_lap_labels[i].setText(self._fmt_short(self._lap_times[i]))
                self.td_lap_labels[i].setStyleSheet(f"color: {COLORS['success']};")
            elif i == current_lap - 1 and current_lap <= 3:
                self.td_lap_labels[i].setText("进行中")
                self.td_lap_labels[i].setStyleSheet(f"color: {COLORS['warning']};")
            else:
                self.td_lap_labels[i].setText("--")
                self.td_lap_labels[i].setStyleSheet(f"color: {COLORS['text_tertiary']};")

        # 更新上一圈时间
        if last_lap_time is not None:
            self.td_last_card.value_label.setText(self._fmt_short(last_lap_time))

        if current_lap > total_laps:
            self.td_last_card.value_label.setText("完成")
            self.td_last_card.value_label.setStyleSheet(f"color: {COLORS['success']};")

    # === 八字环绕模式 ===

    def _setup_skidpad_ui(self):
        """八字环绕 UI - 横向卡片布局"""
        main_row = QHBoxLayout()
        main_row.setSpacing(8)

        # 进度卡片
        self.sp_round_card = self._create_info_card(
            "进度", "0 / 4", mono=False, value_size=FONT_LARGE
        )
        main_row.addWidget(self.sp_round_card, 1)

        # 平均用时卡片
        self.sp_average_card = self._create_info_card(
            "平均用时", "--", value_size=FONT_NORMAL
        )
        main_row.addWidget(self.sp_average_card, 1)

        # 右圈卡片
        self.sp_right_card = self._create_info_card(
            "右圈", "--", value_size=FONT_NORMAL
        )
        main_row.addWidget(self.sp_right_card, 1)

        self.content_layout.addLayout(main_row)

        # 底部：左圈时间
        laps_row = QHBoxLayout()
        laps_row.setSpacing(8)

        self.sp_left_card = self._create_info_card(
            "左圈", "--", value_size=FONT_NORMAL
        )
        laps_row.addWidget(self.sp_left_card, 1)

        # 空白卡片保持对齐
        empty = QFrame()
        empty.setStyleSheet(f"""
            background-color: {COLORS['bg_secondary']};
            border: 1px solid {COLORS['separator']};
            border-radius: 10px;
        """)
        laps_row.addWidget(empty, 1)

        # 另一个空白卡片保持对齐
        empty2 = QFrame()
        empty2.setStyleSheet(f"""
            background-color: {COLORS['bg_secondary']};
            border: 1px solid {COLORS['separator']};
            border-radius: 10px;
        """)
        laps_row.addWidget(empty2, 1)

        self.content_layout.addLayout(laps_row)

    def _refresh_skidpad(self):
        pass

    def update_skidpad(self, segment: int, total_segments: int = 4,
                       segment_time: float = None, all_segments: list = None):
        """更新 skidpad 数据

        赛段顺序（八字环绕）: 右圈1(idx0), 右圈2(idx1), 左圈1(idx2), 左圈2(idx3)
        右圈用时 = 平均(idx0, idx1)
        左圈用时 = 平均(idx2, idx3)
        总平均 = 平均(右圈, 左圈)
        注意：仅在完成全部4段后才计算平均值，避免中途误导性数据
        """
        # 如果 UI 尚未初始化（消息在 set_mode 之前到达），自动初始化
        if not hasattr(self, 'sp_round_card'):
            self._setup_skidpad_ui()

        self._skidpad_current = segment
        self.sp_round_card.value_label.setText(f"{segment} / {total_segments}")

        # 更新各段时间
        if all_segments:
            self._segment_times = all_segments

        # 仅在完成全部4段后才计算并显示平均值
        if len(self._segment_times) >= 4:
            # 右圈：平均 idx0, idx1
            right_times = [self._segment_times[i] for i in [0, 1] if self._segment_times[i] is not None]
            if right_times:
                right_avg = sum(right_times) / len(right_times)
                self.sp_right_card.value_label.setText(self._fmt_short(right_avg))
                self.sp_right_card.value_label.setStyleSheet(f"color: {COLORS['success']};")

            # 左圈：平均 idx2, idx3
            left_times = [self._segment_times[i] for i in [2, 3] if i < len(self._segment_times) and self._segment_times[i] is not None]
            if left_times:
                left_avg = sum(left_times) / len(left_times)
                self.sp_left_card.value_label.setText(self._fmt_short(left_avg))
                self.sp_left_card.value_label.setStyleSheet(f"color: {COLORS['success']};")

            # 总平均
            if right_times and left_times:
                avg = (sum(right_times) / len(right_times) + sum(left_times) / len(left_times)) / 2
                self.sp_average_card.value_label.setText(self._fmt_short(avg))
                self.sp_average_card.value_label.setStyleSheet(f"color: {COLORS['success']};")
        else:
            # 未完成4段时显示进行中状态
            self.sp_right_card.value_label.setText("进行中")
            self.sp_right_card.value_label.setStyleSheet(f"color: {COLORS['warning']};")
            self.sp_left_card.value_label.setText("进行中")
            self.sp_left_card.value_label.setStyleSheet(f"color: {COLORS['warning']};")
            self.sp_average_card.value_label.setText("--")
            self.sp_average_card.value_label.setStyleSheet(f"color: {COLORS['text_tertiary']};")

    # === 直线加速模式 ===

    def _setup_acceleration_ui(self, track_length: float = 75.0):
        """直线加速 UI - 横向卡片布局（距离 + 用时）

        Args:
            track_length: 赛道长度（米），默认 75m
        """
        self._accel_track_length = track_length
        main_row = QHBoxLayout()
        main_row.setSpacing(8)

        # 距离卡片
        self.accel_dist_card = self._create_info_card(
            "距离", "0.0 m", mono=False, value_size=FONT_LARGE
        )
        main_row.addWidget(self.accel_dist_card, 1)

        # 用时卡片（突出显示）
        self.accel_time_card = self._create_info_card(
            "用时", "--",
            value_color=COLORS['accent'], value_size=FONT_TITLE
        )
        main_row.addWidget(self.accel_time_card, 1)

        self.content_layout.addLayout(main_row)

        # 底部：进度条
        self.accel_bar = QProgressBar()
        self.accel_bar.setMaximum(int(track_length))
        self.accel_bar.setFormat(f"%v / {int(track_length)} m")
        self.accel_bar.setFixedHeight(14)
        self.accel_bar.setStyleSheet(f"""
            QProgressBar {{
                border: none; border-radius: 7px; text-align: center;
                font-size: {FONT_SMALL}px;
                background-color: {COLORS['separator']};
                color: {COLORS['text_primary']};
            }}
            QProgressBar::chunk {{
                background-color: {COLORS['accent']};
                border-radius: 7px;
            }}
        """)
        self.content_layout.addWidget(self.accel_bar)

    def _refresh_acceleration(self):
        pass

    def update_acceleration(self, distance: float = 0, speed: float = 0,
                            elapsed: float = 0, finished: bool = False,
                            track_length: float = 75.0):
        """更新直线加速数据

        Args:
            distance: 当前距离（米）
            speed: 当前速度（m/s）
            elapsed: 已用时间（秒）
            finished: 是否完成
            track_length: 赛道长度（米），默认 75m
        """
        # 如果 UI 尚未初始化（消息在 set_mode 之前到达），自动初始化
        if not hasattr(self, 'accel_bar'):
            self._setup_acceleration_ui(track_length)

        # 如果赛道长度变化，更新进度条最大值
        if hasattr(self, '_accel_track_length') and self._accel_track_length != track_length:
            self._accel_track_length = track_length
            self.accel_bar.setMaximum(int(track_length))
            self.accel_bar.setFormat(f"%v / {int(track_length)} m")

        self._accel_distance = distance
        self._accel_speed = speed
        self._accel_elapsed = elapsed
        self._accel_finished = finished

        self.accel_bar.setValue(int(min(distance, track_length)))
        self.accel_dist_card.value_label.setText(f"{distance:.1f} m")

        if finished:
            self.accel_time_card.value_label.setText(f"{elapsed:.3f}s")
            self.accel_time_card.value_label.setStyleSheet(f"color: {COLORS['success']};")
        else:
            self.accel_time_card.value_label.setText(f"{elapsed:.3f}s")

    # === 工具函数 ===

    @staticmethod
    def _format_time(ms: int) -> str:
        """格式化时间: MM:SS.mmm"""
        total_seconds = ms / 1000.0
        minutes = int(total_seconds // 60)
        seconds = total_seconds % 60
        return f"{minutes:02d}:{seconds:06.3f}"

    @staticmethod
    def _fmt_short(seconds: float) -> str:
        """格式化短时间: X.XXXs"""
        return f"{seconds:.3f}s"
