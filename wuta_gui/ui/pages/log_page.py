"""日志页面 - Apple 风格"""

import os
import subprocess
import datetime

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTextEdit, QPushButton, QFileDialog, QFrame
)
from PyQt5.QtGui import QTextCursor

from wuta_gui.ui.theme import (
    COLORS, FONT_DISPLAY, FONT_NORMAL, FONT_SMALL,
    font, mono_font, button_style, textedit_style, toggle_style
)


class LogPage(QWidget):
    """日志页面 - 显示仿真运行日志"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.log_file_path = ""
        self._auto_scroll = True
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 16, 20, 16)

        # 标题
        title = QLabel("运行日志")
        title.setFont(font(FONT_DISPLAY, bold=True))
        title.setStyleSheet(f"color: {COLORS['text_primary']};")
        layout.addWidget(title)

        # 文件路径行
        path_card = QFrame()
        path_card.setStyleSheet(f"""
            background-color: {COLORS['bg_secondary']};
            border: 1px solid {COLORS['separator']};
            border-radius: 10px;
        """)
        path_layout = QHBoxLayout(path_card)
        path_layout.setContentsMargins(14, 10, 14, 10)
        path_layout.setSpacing(10)

        lbl = QLabel("📁  日志文件:")
        lbl.setFont(font(FONT_NORMAL))
        lbl.setStyleSheet(f"color: {COLORS['text_secondary']};")
        path_layout.addWidget(lbl)

        self.path_label = QLabel("无")
        self.path_label.setFont(mono_font(FONT_SMALL))
        self.path_label.setStyleSheet(f"color: {COLORS['accent']};")
        self.path_label.setWordWrap(False)
        path_layout.addWidget(self.path_label, 1)

        self.btn_open_dir = QPushButton("📂 打开目录")
        self.btn_open_dir.setStyleSheet(button_style('default'))
        self.btn_open_dir.clicked.connect(self._open_log_dir)
        path_layout.addWidget(self.btn_open_dir)

        self.btn_export = QPushButton("💾 导出")
        self.btn_export.setStyleSheet(button_style('default'))
        self.btn_export.clicked.connect(self._export_log)
        path_layout.addWidget(self.btn_export)

        layout.addWidget(path_card)

        # 日志文本框
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(mono_font(FONT_SMALL))
        self.log_text.setStyleSheet(textedit_style())
        layout.addWidget(self.log_text)

        # 工具栏
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self.btn_clear = QPushButton("🗑️  清空")
        self.btn_clear.setStyleSheet(button_style('default'))
        self.btn_clear.clicked.connect(self.log_text.clear)
        toolbar.addWidget(self.btn_clear)

        self.btn_scroll = QPushButton("⏩  自动滚动")
        self.btn_scroll.setCheckable(True)
        self.btn_scroll.setChecked(True)
        self.btn_scroll.setStyleSheet(toggle_style())
        self.btn_scroll.clicked.connect(self._toggle_scroll)
        toolbar.addWidget(self.btn_scroll)

        toolbar.addStretch()

        self.lbl_line_count = QLabel("行数: 0")
        self.lbl_line_count.setFont(font(FONT_SMALL))
        self.lbl_line_count.setStyleSheet(f"color: {COLORS['text_secondary']};")
        toolbar.addWidget(self.lbl_line_count)
        layout.addLayout(toolbar)

    def set_log_file(self, file_path: str):
        self.log_file_path = file_path
        self.path_label.setText(file_path)

    def append_log(self, level: str, message: str):
        color_map = {
            "INFO": COLORS['success'],
            "WARN": COLORS['warning'],
            "ERROR": COLORS['danger'],
            "DEBUG": COLORS['text_tertiary'],
        }
        color = color_map.get(level.upper(), COLORS['text_primary'])

        timestamp = datetime.datetime.now().strftime("%H:%M:%S")

        html = f'<span style="color: {COLORS["text_tertiary"]};">[{timestamp}]</span> '
        html += f'<span style="color: {color}; font-weight: 600;">[{level.upper()}]</span> '
        html += f'<span style="color: {COLORS["text_primary"]};">{message}</span>'

        self.log_text.append(html)

        doc = self.log_text.document()
        self.lbl_line_count.setText(f"行数: {doc.lineCount()}")

        if self._auto_scroll:
            cursor = self.log_text.textCursor()
            cursor.movePosition(QTextCursor.End)
            self.log_text.setTextCursor(cursor)

    def _open_log_dir(self):
        log_dir = os.path.dirname(self.log_file_path) if self.log_file_path else "../../logs"
        if os.path.exists(log_dir):
            subprocess.Popen(["xdg-open", log_dir])

    def _export_log(self):
        path, _ = QFileDialog.getSaveFileName(self, "导出日志", "wuta_log.txt", "Text Files (*.txt)")
        if path:
            with open(path, 'w') as f:
                f.write(self.log_text.toPlainText())

    def _toggle_scroll(self, enabled: bool):
        self._auto_scroll = enabled
