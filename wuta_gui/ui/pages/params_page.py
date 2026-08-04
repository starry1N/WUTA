"""参数调节页面 - 分类展示所有可调参数，保存后启动时生效"""

from pathlib import Path
from typing import Dict, Any, Optional

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QComboBox, QCheckBox,
    QScrollArea, QFrame, QGroupBox, QDoubleSpinBox,
    QSpinBox, QPushButton, QFileDialog, QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSignal

from wuta_gui.ui.theme import (
    COLORS, FONT_DISPLAY, FONT_SMALL, FONT_NORMAL, FONT_CAPTION,
    font, mono_font, groupbox_style, radio_check_style, spinbox_style,
    scroll_style, button_style, lineedit_style, combo_style
)


class ParamsPage(QWidget):
    """参数调节页面 - 分类展示，保存后启动时生效

    参数定义格式:
        key: {
            'type': 'float'|'int'|'bool'|'enum'|'string',
            'default': 默认值,
            'range': (min, max),  # for float/int
            'options': [...],     # for enum
            'unit': 'm/s',        # 可选单位
            'category': '分类',
            'desc': '用途说明',
            'node': 'node_name',  # 目标节点
        }
    """

    # 参数定义 (排除启动页面已有的参数)
    PARAM_DEFS: Dict[str, Dict[str, Any]] = {
        # === 速度控制 ===
        'trackdrive_velocity': {
            'type': 'float', 'default': 7.0, 'range': (1.0, 20.0),
            'unit': 'm/s', 'category': '速度控制',
            'desc': '第1圈（建图圈）速度上限',
            'node': 'path_generator_node'
        },
        'trackdrive_min_velocity': {
            'type': 'float', 'default': 3.0, 'range': (0.5, 10.0),
            'unit': 'm/s', 'category': '速度控制',
            'desc': '第1圈最低速度（速度过渡下限）',
            'node': 'path_generator_node'
        },
        'trackdrive_lateral_accel_limit': {
            'type': 'float', 'default': 4.0, 'range': (0.5, 15.0),
            'unit': 'm/s²', 'category': '速度控制',
            'desc': '第1圈横向加速度限制（曲率限速）',
            'node': 'path_generator_node'
        },
        'trackdrive_race_lap2_velocity': {
            'type': 'float', 'default': 9.0, 'range': (1.0, 25.0),
            'unit': 'm/s', 'category': '速度控制',
            'desc': '比赛圈速度上限（第2圈，lap_count≤1）',
            'node': 'path_generator_node'
        },
        'trackdrive_race_velocity': {
            'type': 'float', 'default': 10.0, 'range': (1.0, 25.0),
            'unit': 'm/s', 'category': '速度控制',
            'desc': '比赛圈速度上限（第3圈，lap_count>1）',
            'node': 'path_generator_node'
        },
        'trackdrive_race_min_velocity': {
            'type': 'float', 'default': 4.0, 'range': (0.5, 10.0),
            'unit': 'm/s', 'category': '速度控制',
            'desc': '比赛圈最低速度（速度过渡下限）',
            'node': 'path_generator_node'
        },
        'trackdrive_race_lateral_accel_limit': {
            'type': 'float', 'default': 6.0, 'range': (0.5, 15.0),
            'unit': 'm/s²', 'category': '速度控制',
            'desc': '比赛圈横向加速度限制（曲率限速）',
            'node': 'path_generator_node'
        },
        'trackdrive_short_centerline_velocity': {
            'type': 'float', 'default': 3.0, 'range': (0.5, 10.0),
            'unit': 'm/s', 'category': '速度控制',
            'desc': '短中心线限速（点数过少时触发）',
            'node': 'path_generator_node'
        },
        'trackdrive_low_confidence_velocity': {
            'type': 'float', 'default': 3.0, 'range': (0.5, 10.0),
            'unit': 'm/s', 'category': '速度控制',
            'desc': '置信度为0时的速度下限',
            'node': 'path_generator_node'
        },

        # === 路径规划 ===
        'lookahead_distance': {
            'type': 'float', 'default': 15.0, 'range': (5.0, 50.0),
            'unit': 'm', 'category': '路径规划',
            'desc': '边界检测局部前瞻距离（局部路径提取）',
            'node': 'boundary_detector_node'
        },
        'trackdrive_global_horizon_distance': {
            'type': 'float', 'default': 40.0, 'range': (10.0, 100.0),
            'unit': 'm', 'category': '路径规划',
            'desc': '全局路径发布的前视距离',
            'node': 'path_generator_node'
        },
        'trackdrive_global_search_points': {
            'type': 'int', 'default': 24, 'range': (3, 100),
            'unit': '', 'category': '路径规划',
            'desc': '全局路径搜索点数（从近到远搜索）',
            'node': 'path_generator_node'
        },
        'trackdrive_global_min_points': {
            'type': 'int', 'default': 20, 'range': (5, 100),
            'unit': '', 'category': '路径规划',
            'desc': '识别为全局环线的最小点数阈值',
            'node': 'path_generator_node'
        },
        'trackdrive_min_forward_target': {
            'type': 'float', 'default': 0.5, 'range': (0.1, 5.0),
            'unit': 'm', 'category': '路径规划',
            'desc': '最小前向目标距离（过滤反向路径）',
            'node': 'path_generator_node'
        },
        'trackdrive_resample_spacing': {
            'type': 'float', 'default': 1.0, 'range': (0.2, 5.0),
            'unit': 'm', 'category': '路径规划',
            'desc': '路径重采样间距（均匀化路径点）',
            'node': 'path_generator_node'
        },
        'trackdrive_full_speed_forward_distance': {
            'type': 'float', 'default': 15.0, 'range': (5.0, 50.0),
            'unit': 'm', 'category': '路径规划',
            'desc': '速度过渡距离（min→max速度线性过渡）',
            'node': 'path_generator_node'
        },
        'trackdrive_global_publish_period_sec': {
            'type': 'float', 'default': 0.10, 'range': (0.01, 1.0),
            'unit': 's', 'category': '路径规划',
            'desc': '全局路径发布周期（10Hz）',
            'node': 'path_generator_node'
        },

        # === 置信度阈值 ===
        'trackdrive_confidence_slow_threshold': {
            'type': 'float', 'default': 0.45, 'range': (0.0, 1.0),
            'unit': '', 'category': '置信度阈值',
            'desc': '置信度下限（低于此值速度=low_confidence_velocity）',
            'node': 'path_generator_node'
        },
        'trackdrive_confidence_full_threshold': {
            'type': 'float', 'default': 0.75, 'range': (0.0, 1.0),
            'unit': '', 'category': '置信度阈值',
            'desc': '置信度上限（高于此值速度=max_velocity）',
            'node': 'path_generator_node'
        },
        'global_min_coverage_ratio': {
            'type': 'float', 'default': 0.6, 'range': (0.1, 1.0),
            'unit': '', 'category': '置信度阈值',
            'desc': '全局路径最小覆盖率（低于此值不使用全局路径）',
            'node': 'boundary_detector_node'
        },

        # === 建图参数 ===
        'merge_distance': {
            'type': 'float', 'default': 0.5, 'range': (0.1, 2.0),
            'unit': 'm', 'category': '建图参数',
            'desc': '同一锥桶合并距离',
            'node': 'cone_map_builder'
        },
        'min_hit_count': {
            'type': 'int', 'default': 2, 'range': (1, 10),
            'unit': '次', 'category': '建图参数',
            'desc': '锥桶发布前最低检测次数',
            'node': 'cone_map_builder'
        },
        'loop_closure_distance': {
            'type': 'float', 'default': 3.0, 'range': (1.0, 10.0),
            'unit': 'm', 'category': '建图参数',
            'desc': '闭环检测距离阈值',
            'node': 'cone_map_builder'
        },
        'min_cones_for_closure': {
            'type': 'int', 'default': 10, 'range': (5, 50),
            'unit': '个', 'category': '建图参数',
            'desc': '闭环检测最少锥桶数',
            'node': 'cone_map_builder'
        },
        'start_skip_distance': {
            'type': 'float', 'default': 30.0, 'range': (5.0, 100.0),
            'unit': 'm', 'category': '建图参数',
            'desc': '起始跳过距离（防止起点误触发闭环）',
            'node': 'cone_map_builder'
        },
        'loop_closure_heading_tolerance_deg': {
            'type': 'float', 'default': 60.0, 'range': (5.0, 180.0),
            'unit': '°', 'category': '建图参数',
            'desc': '闭环检测航向容差',
            'node': 'cone_map_builder'
        },
        'assign_colors': {
            'type': 'bool', 'default': True,
            'category': '建图参数',
            'desc': '按 LiDAR 左右分色（UNKNOWN 锥桶）',
            'node': 'cone_map_builder'
        },

        # === LiDAR 检测 ===
        'max_detection_range': {
            'type': 'float', 'default': 20.0, 'range': (5.0, 100.0),
            'unit': 'm', 'category': 'LiDAR 检测',
            'desc': '最大检测距离',
            'node': 'lidar_detection_node'
        },
        'cluster_tolerance': {
            'type': 'float', 'default': 0.4, 'range': (0.1, 2.0),
            'unit': 'm', 'category': 'LiDAR 检测',
            'desc': '欧聚类间距阈值',
            'node': 'lidar_detection_node'
        },
        'min_cluster_size': {
            'type': 'int', 'default': 3, 'range': (1, 20),
            'unit': '点', 'category': 'LiDAR 检测',
            'desc': '聚类最少点数',
            'node': 'lidar_detection_node'
        },
        'max_cluster_size': {
            'type': 'int', 'default': 200, 'range': (50, 500),
            'unit': '点', 'category': 'LiDAR 检测',
            'desc': '聚类最多点数',
            'node': 'lidar_detection_node'
        },
        'use_ransac': {
            'type': 'bool', 'default': True,
            'category': 'LiDAR 检测',
            'desc': '使用 RANSAC 去地面',
            'node': 'lidar_detection_node'
        },
        'ground_z_threshold': {
            'type': 'float', 'default': 0.1, 'range': (0.01, 0.5),
            'unit': 'm', 'category': 'LiDAR 检测',
            'desc': '地面高度阈值',
            'node': 'lidar_detection_node'
        },
        'ransac_distance_threshold': {
            'type': 'float', 'default': 0.05, 'range': (0.01, 0.3),
            'unit': 'm', 'category': 'LiDAR 检测',
            'desc': 'RANSAC 距离阈值',
            'node': 'lidar_detection_node'
        },
        'voxel_leaf_size': {
            'type': 'float', 'default': 0.05, 'range': (0.01, 0.5),
            'unit': 'm', 'category': 'LiDAR 检测',
            'desc': '体素滤波叶大小',
            'node': 'lidar_detection_node'
        },
        'detector_type': {
            'type': 'enum', 'default': 'traditional',
            'options': ['traditional', 'dl'],
            'category': 'LiDAR 检测',
            'desc': '检测器类型',
            'node': 'lidar_detection_node'
        },

        # === 模拟相机 ===
        'max_match_distance': {
            'type': 'float', 'default': 1.0, 'range': (0.1, 5.0),
            'unit': 'm', 'category': '模拟相机',
            'desc': '颜色匹配距离门限',
            'node': 'simulated_cone_colorizer'
        },
        'max_pose_age_sec': {
            'type': 'float', 'default': 0.20, 'range': (0.05, 1.0),
            'unit': 's', 'category': '模拟相机',
            'desc': '位姿最大时差',
            'node': 'simulated_cone_colorizer'
        },

        # === 车辆参数 ===
        'lf': {
            'type': 'float', 'default': 0.8, 'range': (0.1, 2.0),
            'unit': 'm', 'category': '车辆参数',
            'desc': '质心到前轴距离',
            'node': 'controller_node'
        },
        'max_steering_rate_deg_s': {
            'type': 'float', 'default': 180.0, 'range': (30.0, 360.0),
            'unit': '°/s', 'category': '车辆参数',
            'desc': '最大转向角速率',
            'node': 'controller_node'
        },
        'finish_position_tolerance': {
            'type': 'float', 'default': 0.75, 'range': (0.1, 3.0),
            'unit': 'm', 'category': '车辆参数',
            'desc': '终点位置容差',
            'node': 'controller_node'
        },
        'finish_speed_threshold': {
            'type': 'float', 'default': 0.2, 'range': (0.05, 1.0),
            'unit': 'm/s', 'category': '车辆参数',
            'desc': '终点速度阈值',
            'node': 'controller_node'
        },

        # === 纯追踪控制 ===
        'ld_ratio': {
            'type': 'float', 'default': 2.0, 'range': (0.5, 5.0),
            'unit': '', 'category': '纯追踪控制',
            'desc': '前瞻距离比率 (lookahead = velocity × ratio)',
            'node': 'controller_node'
        },
        'min_lookahead': {
            'type': 'float', 'default': 2.0, 'range': (0.5, 10.0),
            'unit': 'm', 'category': '纯追踪控制',
            'desc': '最小前瞻距离',
            'node': 'controller_node'
        },
        'max_lookahead': {
            'type': 'float', 'default': 20.0, 'range': (5.0, 50.0),
            'unit': 'm', 'category': '纯追踪控制',
            'desc': '最大前瞻距离',
            'node': 'controller_node'
        },
        'max_progress_advance': {
            'type': 'int', 'default': 4, 'range': (1, 20),
            'unit': '', 'category': '纯追踪控制',
            'desc': '每次控制更新最大前进路点数',
            'node': 'controller_node'
        },
        'skidpad_lookahead': {
            'type': 'float', 'default': 3.0, 'range': (1.0, 10.0),
            'unit': 'm', 'category': '纯追踪控制',
            'desc': '绕桩固定前瞻距离',
            'node': 'controller_node'
        },
        'trackdrive_lookahead': {
            'type': 'float', 'default': 5.0, 'range': (1.0, 20.0),
            'unit': 'm', 'category': '纯追踪控制',
            'desc': '赛道固定前瞻距离',
            'node': 'controller_node'
        },
        'trackdrive_target_loss_hold_time': {
            'type': 'float', 'default': 0.5, 'range': (0.1, 2.0),
            'unit': 's', 'category': '纯追踪控制',
            'desc': '目标丢失保持时间',
            'node': 'controller_node'
        },
        'trackdrive_target_loss_hold_speed': {
            'type': 'float', 'default': 2.0, 'range': (0.5, 5.0),
            'unit': 'm/s', 'category': '纯追踪控制',
            'desc': '目标丢失保持速度',
            'node': 'controller_node'
        },

        # === 全局配对 ===
        'global_pairing_min_width': {
            'type': 'float', 'default': 1.5, 'range': (0.5, 5.0),
            'unit': 'm', 'category': '全局配对',
            'desc': '全局配对最小宽度',
            'node': 'boundary_detector_node'
        },
        'global_pairing_max_width': {
            'type': 'float', 'default': 7.5, 'range': (2.0, 15.0),
            'unit': 'm', 'category': '全局配对',
            'desc': '全局配对最大宽度',
            'node': 'boundary_detector_node'
        },
        'global_pairing_dedup_distance': {
            'type': 'float', 'default': 0.75, 'range': (0.1, 3.0),
            'unit': 'm', 'category': '全局配对',
            'desc': '全局配对去重距离',
            'node': 'boundary_detector_node'
        },
        'global_max_segment_length': {
            'type': 'float', 'default': 10.0, 'range': (2.0, 30.0),
            'unit': 'm', 'category': '全局配对',
            'desc': '全局最大段长度',
            'node': 'boundary_detector_node'
        },
        'global_max_closure_distance': {
            'type': 'float', 'default': 8.0, 'range': (1.0, 20.0),
            'unit': 'm', 'category': '全局配对',
            'desc': '全局最大闭环距离',
            'node': 'boundary_detector_node'
        },
        'global_min_waypoints': {
            'type': 'int', 'default': 20, 'range': (5, 100),
            'unit': '', 'category': '全局配对',
            'desc': '全局最小路点数',
            'node': 'boundary_detector_node'
        },

        # === 局部配对 ===
        'local_pairing_min_streak': {
            'type': 'int', 'default': 3, 'range': (1, 20),
            'unit': '次', 'category': '局部配对',
            'desc': '几何配对回退前最小连续失败次数',
            'node': 'boundary_detector_node'
        },
        'local_pairing_color_imbalance_ratio': {
            'type': 'float', 'default': 0.20, 'range': (0.0, 1.0),
            'unit': '', 'category': '局部配对',
            'desc': '颜色不平衡比率（低于此值触发局部配对）',
            'node': 'boundary_detector_node'
        },
        'delaunay_min_waypoints': {
            'type': 'int', 'default': 3, 'range': (3, 20),
            'unit': '', 'category': '局部配对',
            'desc': 'Delaunay 最小路点数',
            'node': 'boundary_detector_node'
        },

        # === 任务管理 ===
        'min_blue_cones': {
            'type': 'int', 'default': 12, 'range': (1, 50),
            'unit': '个', 'category': '任务管理',
            'desc': '最小蓝色锥桶数（比赛准入）',
            'node': 'mission_manager_node'
        },
        'min_yellow_cones': {
            'type': 'int', 'default': 12, 'range': (1, 50),
            'unit': '个', 'category': '任务管理',
            'desc': '最小黄色锥桶数（比赛准入）',
            'node': 'mission_manager_node'
        },
        'min_map_average_confidence': {
            'type': 'float', 'default': 0.40, 'range': (0.0, 1.0),
            'unit': '', 'category': '任务管理',
            'desc': '最小地图平均置信度',
            'node': 'mission_manager_node'
        },
        'min_map_color_balance': {
            'type': 'float', 'default': 0.35, 'range': (0.0, 1.0),
            'unit': '', 'category': '任务管理',
            'desc': '最小地图颜色平衡度',
            'node': 'mission_manager_node'
        },
        'min_localization_confidence': {
            'type': 'float', 'default': 0.45, 'range': (0.0, 1.0),
            'unit': '', 'category': '任务管理',
            'desc': '最小定位置信度（比赛准入）',
            'node': 'mission_manager_node'
        },
        'localization_timeout_sec': {
            'type': 'float', 'default': 0.50, 'range': (0.05, 2.0),
            'unit': 's', 'category': '任务管理',
            'desc': '定位超时时间',
            'node': 'mission_manager_node'
        },
        'lap_min_duration_sec': {
            'type': 'float', 'default': 10.0, 'range': (1.0, 60.0),
            'unit': 's', 'category': '任务管理',
            'desc': '单圈最小时间',
            'node': 'mission_manager_node'
        },
        'lap_min_distance': {
            'type': 'float', 'default': 30.0, 'range': (5.0, 200.0),
            'unit': 'm', 'category': '任务管理',
            'desc': '单圈最小距离',
            'node': 'mission_manager_node'
        },
        'lap_arm_distance': {
            'type': 'float', 'default': 10.0, 'range': (1.0, 50.0),
            'unit': 'm', 'category': '任务管理',
            'desc': '圈数检测武装距离',
            'node': 'mission_manager_node'
        },
        'lap_line_half_width': {
            'type': 'float', 'default': 4.0, 'range': (0.5, 10.0),
            'unit': 'm', 'category': '任务管理',
            'desc': '圈数检测线半宽',
            'node': 'mission_manager_node'
        },
        'lap_heading_tolerance_deg': {
            'type': 'float', 'default': 75.0, 'range': (5.0, 180.0),
            'unit': '°', 'category': '任务管理',
            'desc': '圈数检测航向容差',
            'node': 'mission_manager_node'
        },
        'use_ndt_race_localization': {
            'type': 'bool', 'default': False,
            'category': '任务管理',
            'desc': '比赛时使用 NDT 定位',
            'node': 'mission_manager_node'
        },

        # === Skidpad ===
        'skidpad_velocity': {
            'type': 'float', 'default': 5.0, 'range': (1.0, 15.0),
            'unit': 'm/s', 'category': 'Skidpad',
            'desc': '绕桩速度',
            'node': 'path_generator_node'
        },
        'skidpad_points': {
            'type': 'int', 'default': 72, 'range': (16, 144),
            'unit': '', 'category': 'Skidpad',
            'desc': '绕桩每圈点数',
            'node': 'path_generator_node'
        },
        'skidpad_exit_length': {
            'type': 'float', 'default': 25.0, 'range': (10.0, 50.0),
            'unit': 'm', 'category': 'Skidpad',
            'desc': '绕桩出口长度',
            'node': 'path_generator_node'
        },
        'skidpad_braking_distance': {
            'type': 'float', 'default': 10.0, 'range': (2.0, 30.0),
            'unit': 'm', 'category': 'Skidpad',
            'desc': '绕桩制动距离',
            'node': 'path_generator_node'
        },

        # === 直线加速 ===
        'acceleration_velocity': {
            'type': 'float', 'default': 15.0, 'range': (5.0, 30.0),
            'unit': 'm/s', 'category': '直线加速',
            'desc': '直线加速速度',
            'node': 'path_generator_node'
        },
        'acceleration_length': {
            'type': 'float', 'default': 75.0, 'range': (20.0, 200.0),
            'unit': 'm', 'category': '直线加速',
            'desc': '计时距离',
            'node': 'path_generator_node'
        },
        'acceleration_stopping_distance': {
            'type': 'float', 'default': 100.0, 'range': (20.0, 300.0),
            'unit': 'm', 'category': '直线加速',
            'desc': '计时后停车距离',
            'node': 'path_generator_node'
        },
    }

    # 信号
    params_saved = pyqtSignal(str)  # 保存成功信号，传递文件路径
    feedback = pyqtSignal(str, str)  # (level, message)

    def __init__(self, wuta_root: str = None, parent=None):
        super().__init__(parent)
        self.wuta_root = Path(wuta_root) if wuta_root else None
        self._widgets: Dict[str, QWidget] = {}
        self._setup_ui()
        self.feedback.connect(self._show_feedback)
        self._load_defaults()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 16, 20, 16)

        # 标题
        title_row = QHBoxLayout()
        title = QLabel("参数调节")
        title.setFont(font(FONT_DISPLAY, bold=True))
        title.setStyleSheet(f"color: {COLORS['text_primary']};")
        title_row.addWidget(title)
        title_row.addStretch()

        # 数据类型说明
        type_hint = QLabel("💡 所有参数保存后将在启动仿真时生效")
        type_hint.setFont(font(FONT_SMALL))
        type_hint.setStyleSheet(f"color: {COLORS['text_secondary']};")
        title_row.addWidget(type_hint)
        layout.addLayout(title_row)

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
            group = QGroupBox(f"{cat}")
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

        btn_save = QPushButton("💾 保存参数")
        btn_save.setFont(font(FONT_NORMAL, bold=True))
        btn_save.setStyleSheet(button_style('primary'))
        btn_save.clicked.connect(self._save_params)

        btn_load = QPushButton("📂 加载预设")
        btn_load.setStyleSheet(button_style('default'))
        btn_load.clicked.connect(self._load_preset)

        btn_reset = QPushButton("🔄 恢复默认")
        btn_reset.setStyleSheet(button_style('default'))
        btn_reset.clicked.connect(self._reset_defaults)

        btn_row.addWidget(btn_save)
        btn_row.addWidget(btn_load)
        btn_row.addWidget(btn_reset)
        btn_row.addStretch()
        layout.addLayout(btn_row)

    def _create_row(self, name: str, defs: dict) -> QWidget:
        """创建单行参数控件"""
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(4, 6, 4, 6)
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
        layout.addLayout(name_layout, 3)

        # 数据类型和范围标签
        type_lbl = self._create_type_label(defs)
        layout.addWidget(type_lbl, 1)

        # 输入控件
        ptype = defs['type']
        widget = None

        if ptype == 'float':
            spin = QDoubleSpinBox()
            spin.setRange(*defs['range'])
            spin.setValue(defs['default'])
            spin.setSingleStep((defs['range'][1] - defs['range'][0]) / 100)
            spin.setDecimals(3)
            if 'unit' in defs:
                spin.setSuffix(f" {defs['unit']}")
            spin.setStyleSheet(spinbox_style())
            spin.setMinimumWidth(120)
            layout.addWidget(spin, 1)
            widget = spin

        elif ptype == 'int':
            spin = QSpinBox()
            spin.setRange(*defs['range'])
            spin.setValue(defs['default'])
            if 'unit' in defs:
                spin.setSuffix(f" {defs['unit']}")
            spin.setStyleSheet(spinbox_style())
            spin.setMinimumWidth(120)
            layout.addWidget(spin, 1)
            widget = spin

        elif ptype == 'bool':
            chk = QCheckBox()
            chk.setChecked(defs['default'])
            chk.setStyleSheet(radio_check_style())
            layout.addWidget(chk, 1)
            widget = chk

        elif ptype == 'enum':
            combo = QComboBox()
            combo.addItems(defs['options'])
            combo.setCurrentText(defs['default'])
            combo.setStyleSheet(combo_style())
            combo.setMinimumWidth(120)
            layout.addWidget(combo, 1)
            widget = combo

        elif ptype == 'string':
            edit = QLineEdit()
            edit.setText(str(defs['default']))
            edit.setStyleSheet(lineedit_style())
            edit.setMinimumWidth(120)
            layout.addWidget(edit, 1)
            widget = edit

        if widget is not None:
            self._widgets[name] = widget

        return row

    def _create_type_label(self, defs: dict) -> QLabel:
        """创建数据类型和范围标签"""
        ptype = defs['type']
        if ptype in ('float', 'int'):
            range_str = f"[{defs['range'][0]}, {defs['range'][1]}]"
            text = f"{ptype}\n{range_str}"
        elif ptype == 'enum':
            opts = '/'.join(defs.get('options', []))
            text = f"enum\n{opts}"
        elif ptype == 'bool':
            text = "bool\ntrue/false"
        else:
            text = "string"

        lbl = QLabel(text)
        lbl.setFont(font(FONT_CAPTION))
        lbl.setStyleSheet(f"color: {COLORS['text_tertiary']};")
        lbl.setAlignment(Qt.AlignCenter)
        return lbl

    def _load_defaults(self):
        """加载默认值"""
        for name, defs in self.PARAM_DEFS.items():
            if name not in self._widgets:
                continue
            w = self._widgets[name]
            ptype = defs['type']
            default = defs['default']

            if ptype == 'float' and isinstance(w, QDoubleSpinBox):
                w.setValue(float(default))
            elif ptype == 'int' and isinstance(w, QSpinBox):
                w.setValue(int(default))
            elif ptype == 'bool' and isinstance(w, QCheckBox):
                w.setChecked(bool(default))
            elif ptype == 'enum' and isinstance(w, QComboBox):
                w.setCurrentText(str(default))
            elif ptype == 'string' and isinstance(w, QLineEdit):
                w.setText(str(default))

    def get_all_params(self) -> Dict[str, Any]:
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

    def apply_params(self, params: Dict[str, Any]):
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
                w.setChecked(bool(value))
            elif ptype == 'enum' and isinstance(w, QComboBox):
                w.setCurrentText(str(value))
            elif ptype == 'string' and isinstance(w, QLineEdit):
                w.setText(str(value))

    def _save_params(self):
        """保存参数到 YAML 文件（弹出文件名输入框）"""
        from PyQt5.QtWidgets import QInputDialog

        # 获取保存文件名
        name, ok = QInputDialog.getText(
            self,
            "保存参数配置",
            "请输入配置名称:",
            text="my_config"
        )
        if not ok or not name.strip():
            return

        # 清理文件名
        name = name.strip()
        # 移除不合法的文件名字符
        import re
        name = re.sub(r'[^\w\-]', '_', name)

        if not name:
            self.feedback.emit("error", "配置名称无效")
            return

        import yaml

        params = self.get_all_params()
        if not params:
            self.feedback.emit("error", "没有可保存的参数")
            return

        # 按节点分组
        node_params: Dict[str, Dict[str, Any]] = {}
        for name_key, value in params.items():
            node = self.PARAM_DEFS[name_key].get('node', 'unknown')
            node_params.setdefault(node, {})[name_key] = value

        # 保存到 YAML
        save_data = {
            'metadata': {
                'description': f'WUTA 参数配置文件 - {name}',
                'format': '按节点分组，启动时通过 ros2 param load 应用到对应节点',
            },
            'parameters': node_params,
        }

        # 确保目录存在
        params_dir = self._get_params_dir()
        params_dir.mkdir(parents=True, exist_ok=True)
        save_path = params_dir / f'{name}.yaml'

        # 检查文件是否已存在
        if save_path.exists():
            reply = QMessageBox.question(
                self,
                "文件已存在",
                f"配置文件 '{name}.yaml' 已存在，是否覆盖？",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                return

        try:
            with open(save_path, 'w', encoding='utf-8') as f:
                yaml.dump(save_data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
            self.feedback.emit("success", f"参数已保存到: {save_path}")
            self.params_saved.emit(str(save_path))
        except Exception as e:
            self.feedback.emit("error", f"保存失败: {str(e)}")

    def _load_preset(self):
        """从 YAML 加载参数预设"""
        import yaml

        path, _ = QFileDialog.getOpenFileName(
            self, "加载预设", str(self._get_params_dir()), "YAML (*.yaml *.yml)"
        )
        if not path:
            return

        try:
            with open(path, encoding='utf-8') as f:
                data = yaml.safe_load(f)

            # 支持两种格式：
            # 1. 扁平格式 {param_name: value, ...}
            # 2. 节点分组格式 {parameters: {node: {param_name: value}}}
            if 'parameters' in data and isinstance(data['parameters'], dict):
                # 节点分组格式，展平
                flat_params = {}
                for node_params in data['parameters'].values():
                    if isinstance(node_params, dict):
                        flat_params.update(node_params)
                self.apply_params(flat_params)
            else:
                # 扁平格式
                self.apply_params(data)

            self.feedback.emit("success", f"预设已加载: {Path(path).name}")
        except Exception as e:
            self.feedback.emit("error", f"加载失败: {str(e)}")

    def _reset_defaults(self):
        """恢复默认值"""
        reply = QMessageBox.question(
            self, "确认重置", "确定恢复所有参数为默认值？",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self._load_defaults()
            self.feedback.emit("success", "已恢复默认值")

    def _get_params_dir(self) -> Path:
        """获取参数文件保存目录"""
        if self.wuta_root:
            return self.wuta_root / "wuta_gui" / "params"
        return Path.home() / ".wuta" / "params"

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

    def get_params_file_path(self) -> Optional[Path]:
        """获取默认参数文件路径"""
        params_file = self._get_params_dir() / 'default_params.yaml'
        if params_file.exists():
            return params_file
        # 如果没有默认文件，返回第一个找到的 yaml 文件
        params_dir = self._get_params_dir()
        if params_dir.exists():
            yaml_files = list(params_dir.glob("*.yaml"))
            if yaml_files:
                return yaml_files[0]
        return None

    def get_all_params_files(self) -> list:
        """获取所有可用的参数配置文件"""
        params_dir = self._get_params_dir()
        if not params_dir.exists():
            return []
        return sorted(params_dir.glob("*.yaml"))
