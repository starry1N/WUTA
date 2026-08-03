"""调参页面 - 批量同步模式，修复参数覆盖bug"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QComboBox, QCheckBox,
    QScrollArea, QFrame, QGroupBox, QDoubleSpinBox,
    QSpinBox, QPushButton, QFileDialog, QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSignal

from wuta_gui.ui.theme import (
    COLORS, FONT_DISPLAY, FONT_NORMAL, FONT_SMALL,
    font, mono_font, groupbox_style, spinbox_style, scroll_style, button_style
)


class ParamsPage(QWidget):
    """参数调整页面 - 批量同步到仿真"""

    # 批量同步信号
    params_sync_requested = pyqtSignal(dict)  # {参数名: 值}
    feedback = pyqtSignal(str, str)  # (level, message)

    # 参数定义
    PARAM_DEFS = {
        'trackdrive_velocity': {'type': 'float', 'default': 7.0, 'range': (1.0, 15.0), 'unit': 'm/s', 'category': '速度', 'desc': '探索圈速度上限'},
        'trackdrive_race_velocity': {'type': 'float', 'default': 10.0, 'range': (1.0, 20.0), 'unit': 'm/s', 'category': '速度', 'desc': '比赛圈速度上限'},
        'trackdrive_lateral_accel_limit': {'type': 'float', 'default': 4.0, 'range': (0.5, 10.0), 'unit': 'm/s²', 'category': '速度', 'desc': '横向加速度限制'},
        'trackdrive_min_velocity': {'type': 'float', 'default': 3.0, 'range': (0.5, 10.0), 'unit': 'm/s', 'category': '速度', 'desc': '最低速度'},
        'merge_distance': {'type': 'float', 'default': 0.5, 'range': (0.1, 2.0), 'unit': 'm', 'category': '建图', 'desc': '同一锥桶合并距离'},
        'min_hit_count': {'type': 'int', 'default': 2, 'range': (1, 10), 'unit': '次', 'category': '建图', 'desc': '发布前最低检测次数'},
        'loop_closure_distance': {'type': 'float', 'default': 3.0, 'range': (1.0, 10.0), 'unit': 'm', 'category': '建图', 'desc': '闭环距离阈值'},
        'min_cones_for_closure': {'type': 'int', 'default': 10, 'range': (5, 50), 'unit': '个', 'category': '建图', 'desc': '闭环最少锥桶数'},
        'lookahead_distance': {'type': 'float', 'default': 15.0, 'range': (5.0, 50.0), 'unit': 'm', 'category': '规划', 'desc': '局部前瞻距离'},
        'trackdrive_global_horizon_distance': {'type': 'float', 'default': 40.0, 'range': (10.0, 100.0), 'unit': 'm', 'category': '规划', 'desc': '全局前瞻距离'},
        'global_min_coverage_ratio': {'type': 'float', 'default': 0.6, 'range': (0.1, 1.0), 'unit': '', 'category': '规划', 'desc': '全局最小覆盖率'},
        'max_detection_range': {'type': 'float', 'default': 20.0, 'range': (5.0, 100.0), 'unit': 'm', 'category': 'LiDAR', 'desc': '最大检测距离'},
        'cluster_tolerance': {'type': 'float', 'default': 0.4, 'range': (0.1, 2.0), 'unit': 'm', 'category': 'LiDAR', 'desc': '聚类间距阈值'},
        'min_cluster_size': {'type': 'int', 'default': 3, 'range': (1, 20), 'unit': '点', 'category': 'LiDAR', 'desc': '聚类最少点数'},
        'max_cluster_size': {'type': 'int', 'default': 200, 'range': (50, 500), 'unit': '点', 'category': 'LiDAR', 'desc': '聚类最多点数'},
        'max_match_distance': {'type': 'float', 'default': 1.0, 'range': (0.1, 5.0), 'unit': 'm', 'category': '模拟相机', 'desc': '颜色匹配距离门限'},
        'max_pose_age_sec': {'type': 'float', 'default': 0.20, 'range': (0.05, 1.0), 'unit': 's', 'category': '模拟相机', 'desc': '位姿最大时差'},
        'assign_colors': {'type': 'bool', 'default': True, 'category': '建图', 'desc': '按 LiDAR 左右分色'},
        'detector_type': {'type': 'enum', 'default': 'traditional', 'options': ['traditional', 'dl'], 'category': 'LiDAR', 'desc': '检测器类型'},
        'use_ransac': {'type': 'bool', 'default': True, 'category': 'LiDAR', 'desc': '使用 RANSAC 去地面'},
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        # 直接保存控件引用：{param_name: widget}
        self._widgets = {}
        self._setup_ui()
        self.feedback.connect(self._show_feedback)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 16, 20, 16)

        # 标题
        title = QLabel("参数调整")
        title.setFont(font(FONT_DISPLAY, bold=True))
        title.setStyleSheet(f"color: {COLORS['text_primary']};")
        layout.addWidget(title)

        # 反馈区域
        fb_row = QHBoxLayout()
        self.fb_label = QLabel("")
        self.fb_label.setFont(mono_font(FONT_SMALL))
        self.fb_label.setWordWrap(True)
        self.fb_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.fb_label.setMinimumHeight(28)
        fb_row.addWidget(self.fb_label, 1)

        fb_close = QPushButton("✕")
        fb_close.setFixedSize(20, 20)
        fb_close.setStyleSheet(f"border:none;background:transparent;color:{COLORS['text_secondary']};")
        fb_close.clicked.connect(lambda: (self.fb_label.hide(), fb_close.hide()))
        self._fb_close = fb_close
        fb_row.addWidget(fb_close)
        layout.addLayout(fb_row)
        self.fb_label.hide()
        fb_close.hide()

        # 滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(scroll_style())

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(8)

        # 按分类组织参数
        categories = {}
        for name, defs in self.PARAM_DEFS.items():
            cat = defs.get('category', '其他')
            categories.setdefault(cat, []).append((name, defs))

        for cat, params in categories.items():
            group = QGroupBox(f"{cat} 参数")
            group.setStyleSheet(groupbox_style())
            group_layout = QVBoxLayout(group)
            group_layout.setSpacing(4)

            for name, defs in params:
                group_layout.addWidget(self._create_row(name, defs))

            content_layout.addWidget(group)

        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)

        # 操作按钮
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        btn_sync = QPushButton("🔄 同步到仿真")
        btn_sync.setFont(font(FONT_NORMAL, bold=True))
        btn_sync.setStyleSheet(button_style('success'))
        btn_sync.clicked.connect(self._sync_params)

        btn_save = QPushButton("保存预设")
        btn_save.setStyleSheet(button_style('primary'))
        btn_save.clicked.connect(self._save_preset)

        btn_load = QPushButton("加载预设")
        btn_load.setStyleSheet(button_style('default'))
        btn_load.clicked.connect(self._load_preset)

        btn_reset = QPushButton("恢复默认")
        btn_reset.setStyleSheet(button_style('default'))
        btn_reset.clicked.connect(self._reset_defaults)

        btn_row.addWidget(btn_sync)
        btn_row.addWidget(btn_save)
        btn_row.addWidget(btn_load)
        btn_row.addWidget(btn_reset)
        btn_row.addStretch()
        layout.addLayout(btn_row)

    def _create_row(self, name: str, defs: dict) -> QWidget:
        """创建单行参数控件"""
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        # 名称和描述
        name_layout = QVBoxLayout()
        name_layout.setSpacing(1)
        lbl_name = QLabel(name)
        lbl_name.setFont(font(FONT_NORMAL, bold=True))
        lbl_name.setStyleSheet(f"color: {COLORS['text_primary']};")
        lbl_desc = QLabel(defs.get('desc', ''))
        lbl_desc.setFont(font(FONT_SMALL))
        lbl_desc.setStyleSheet(f"color: {COLORS['text_secondary']};")
        name_layout.addWidget(lbl_name)
        name_layout.addWidget(lbl_desc)
        layout.addLayout(name_layout, 2)

        # 类型标签
        type_lbl = QLabel(defs['type'])
        type_lbl.setFont(font(FONT_SMALL))
        type_lbl.setStyleSheet(f"color: {COLORS['accent']};")
        type_lbl.setFixedWidth(40)
        layout.addWidget(type_lbl)

        # 输入控件
        ptype = defs['type']
        widget = None

        if ptype == 'float':
            spin = QDoubleSpinBox()
            spin.setRange(*defs['range'])
            spin.setValue(defs['default'])
            spin.setSingleStep(0.1)
            spin.setDecimals(2)
            if 'unit' in defs:
                spin.setSuffix(f" {defs['unit']}")
            spin.setStyleSheet(spinbox_style())
            layout.addWidget(spin, 1)
            widget = spin

        elif ptype == 'int':
            spin = QSpinBox()
            spin.setRange(*defs['range'])
            spin.setValue(defs['default'])
            if 'unit' in defs:
                spin.setSuffix(f" {defs['unit']}")
            spin.setStyleSheet(spinbox_style())
            layout.addWidget(spin, 1)
            widget = spin

        elif ptype == 'bool':
            chk = QCheckBox()
            chk.setChecked(defs['default'])
            layout.addWidget(chk, 1)
            widget = chk

        elif ptype == 'enum':
            combo = QComboBox()
            combo.addItems(defs['options'])
            combo.setCurrentText(defs['default'])
            layout.addWidget(combo, 1)
            widget = combo

        elif ptype == 'string':
            edit = QLineEdit()
            edit.setText(str(defs['default']))
            layout.addWidget(edit, 1)
            widget = edit

        # 直接保存控件引用（关键修复：不再依赖遍历查找）
        if widget is not None:
            self._widgets[name] = widget

        return row

    def _sync_params(self):
        """同步所有参数到仿真"""
        params = self.get_all_params()
        if params:
            self.params_sync_requested.emit(params)
        else:
            self.feedback.emit("error", "没有可同步的参数")

    def _save_preset(self):
        """保存参数预设到 YAML"""
        path, _ = QFileDialog.getSaveFileName(self, "保存预设", "params_preset.yaml", "YAML (*.yaml)")
        if not path:
            return
        import yaml
        try:
            with open(path, 'w') as f:
                yaml.dump(self.get_all_params(), f, allow_unicode=True)
            QMessageBox.information(self, "保存成功", f"预设已保存到:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "保存失败", str(e))

    def _load_preset(self):
        """从 YAML 加载参数预设"""
        path, _ = QFileDialog.getOpenFileName(self, "加载预设", "", "YAML (*.yaml)")
        if not path:
            return
        import yaml
        try:
            with open(path) as f:
                params = yaml.safe_load(f)
            self.apply_params(params)
            QMessageBox.information(self, "加载成功", f"预设已加载:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "加载失败", str(e))

    def _reset_defaults(self):
        """恢复默认值"""
        reply = QMessageBox.question(self, "确认重置", "确定恢复所有参数为默认值？")
        if reply == QMessageBox.Yes:
            defaults = {name: d['default'] for name, d in self.PARAM_DEFS.items()}
            self.apply_params(defaults)
            self.feedback.emit("success", "已恢复默认值")

    def _show_feedback(self, level: str, message: str):
        """显示反馈信息"""
        self.fb_label.show()
        self._fb_close.show()

        colors = {
            'success': (COLORS['success'], '#e8f5e9'),
            'info': (COLORS['accent'], '#e3f2fd'),
            'warning': (COLORS['warning'], '#fff3e0'),
            'error': (COLORS['danger'], '#ffebee'),
        }
        fg, bg = colors.get(level, colors['info'])
        self.fb_label.setStyleSheet(f"""
            QLabel {{
                padding: 6px 10px;
                border-radius: 4px;
                background-color: {bg};
                border: 1px solid {fg};
                color: {fg};
            }}
        """)
        icon = {'success': '✓', 'info': '⟳', 'warning': '⚠', 'error': '✗'}.get(level, '')
        self.fb_label.setText(f"{icon} {message}")

    def apply_params(self, params: dict):
        """应用参数值到界面（外部调用）"""
        for name, value in params.items():
            if name not in self._widgets:
                continue
            w = self._widgets[name]
            defs = self.PARAM_DEFS.get(name, {})
            ptype = defs.get('type', 'string')

            if ptype == 'float' and isinstance(w, QDoubleSpinBox):
                w.setValue(float(value))
            elif ptype == 'int' and isinstance(w, QSpinBox):
                w.setValue(int(value))
            elif ptype == 'bool' and isinstance(w, QCheckBox):
                w.setValue(bool(value))
            elif ptype == 'enum' and isinstance(w, QComboBox):
                w.setCurrentText(str(value))
            elif ptype == 'string' and isinstance(w, QLineEdit):
                w.setText(str(value))

    def get_all_params(self) -> dict:
        """获取所有参数当前值"""
        params = {}
        for name, w in self._widgets.items():
            defs = self.PARAM_DEFS.get(name, {})
            ptype = defs.get('type', 'string')

            if ptype == 'float' and isinstance(w, QDoubleSpinBox):
                params[name] = w.value()
            elif ptype == 'int' and isinstance(w, QSpinBox):
                params[name] = w.value()
            elif ptype == 'bool' and isinstance(w, QCheckBox):
                params[name] = w.isChecked()
            elif ptype == 'enum' and isinstance(w, QComboBox):
                params[name] = w.currentText()
            elif ptype == 'string' and isinstance(w, QLineEdit):
                params[name] = w.text()
        return params
