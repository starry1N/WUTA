"""构建页面 - Apple 风格"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QGroupBox,
    QRadioButton, QButtonGroup, QMessageBox, QCheckBox,
    QScrollArea, QFrame
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QTextCursor

from wuta_gui.core.builder import Builder, BuildMode
from wuta_gui.ui.theme import (
    COLORS, FONT_DISPLAY, FONT_LARGE, FONT_SMALL,
    font, mono_font, groupbox_style, radio_check_style, button_style,
    scroll_style, textedit_style
)


class BuildPage(QWidget):
    """构建页面"""

    build_finished = pyqtSignal(bool, str)
    request_switch_to_launch = pyqtSignal()

    def __init__(self, wuta_root: str, parent=None):
        super().__init__(parent)
        self.wuta_root = wuta_root
        self.builder: Builder = None
        self._setup_ui()

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
        title = QLabel("项目构建")
        title.setFont(font(FONT_DISPLAY, bold=True))
        title.setStyleSheet(f"color: {COLORS['text_primary']};")
        layout.addWidget(title)

        # 构建模式
        config_group = QGroupBox("构建模式")
        config_group.setStyleSheet(groupbox_style())
        config_layout = QVBoxLayout(config_group)
        config_layout.setSpacing(10)

        mode_layout = QHBoxLayout()
        mode_layout.setSpacing(16)

        self.mode_group = QButtonGroup()
        self.mode_incremental = QRadioButton("增量构建")
        self.mode_clean = QRadioButton("清理重建")
        self.mode_skip = QRadioButton("跳过构建")

        for btn in [self.mode_incremental, self.mode_clean, self.mode_skip]:
            btn.setStyleSheet(radio_check_style())

        self.mode_group.addButton(self.mode_incremental, 0)
        self.mode_group.addButton(self.mode_clean, 1)
        self.mode_group.addButton(self.mode_skip, 2)
        self.mode_incremental.setChecked(True)

        mode_layout.addWidget(self.mode_incremental)
        mode_layout.addWidget(self.mode_clean)
        mode_layout.addWidget(self.mode_skip)
        mode_layout.addStretch()
        config_layout.addLayout(mode_layout)

        self.lightweight_check = QCheckBox("轻量构建（限制并行编译数，适合内存 ≤8GB）")
        self.lightweight_check.setStyleSheet(radio_check_style())
        config_layout.addWidget(self.lightweight_check)

        self.mode_skip.toggled.connect(lambda c: self.lightweight_check.setDisabled(c))

        layout.addWidget(config_group)

        # 构建日志
        log_group = QGroupBox("构建日志")
        log_group.setStyleSheet(groupbox_style())
        log_layout = QVBoxLayout(log_group)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(mono_font(FONT_SMALL))
        self.log_text.setMinimumHeight(200)
        self.log_text.setStyleSheet(textedit_style())
        log_layout.addWidget(self.log_text)
        layout.addWidget(log_group)

        # 按钮区域
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.btn_start = QPushButton("🔨  开始构建")
        self.btn_start.setMinimumHeight(44)
        self.btn_start.setFont(font(FONT_LARGE, bold=True))
        self.btn_start.setStyleSheet(button_style('primary'))
        self.btn_start.clicked.connect(self._on_start_build)

        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.setMinimumHeight(44)
        self.btn_cancel.setFont(font(FONT_LARGE))
        self.btn_cancel.setStyleSheet(button_style('default'))
        self.btn_cancel.clicked.connect(self._on_cancel_build)

        btn_layout.addWidget(self.btn_start)
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        scroll.setWidget(content)
        main_layout.addWidget(scroll)

    def _get_mode(self) -> BuildMode:
        modes = {0: BuildMode.INCREMENTAL, 1: BuildMode.CLEAN, 2: BuildMode.SKIP}
        return modes.get(self.mode_group.checkedId(), BuildMode.INCREMENTAL)

    def _is_lightweight(self) -> bool:
        return self.lightweight_check.isChecked() and not self.mode_skip.isChecked()

    def _on_start_build(self):
        mode = self._get_mode()
        if mode == BuildMode.CLEAN:
            reply = QMessageBox.warning(
                self, "确认清理", "清理构建将删除所有构建产物。\n确定继续吗？",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                return

        self.btn_start.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.log_text.clear()

        if self._is_lightweight():
            actual = BuildMode.CLEAN_LIGHTWEIGHT if mode == BuildMode.CLEAN else BuildMode.LIGHTWEIGHT
        else:
            actual = mode

        self.builder = Builder(self.wuta_root, actual)
        self.builder.log_line.connect(self._on_log_line)
        self.builder.finished.connect(self._on_build_finished)
        self.builder.start()

    def _on_cancel_build(self):
        if self.builder and self.builder.isRunning():
            self.builder.stop()
            self.builder.wait()
            self.btn_start.setEnabled(True)
            self.btn_cancel.setEnabled(False)

    def _on_log_line(self, line: str):
        self.log_text.append(line)
        cursor = self.log_text.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.log_text.setTextCursor(cursor)

    def _on_build_finished(self, success: bool, message: str):
        self.btn_start.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        if success:
            self.request_switch_to_launch.emit()
        self.build_finished.emit(success, message)
