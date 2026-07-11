# WUTA ROS 2 内部设计

## 1. 模块设计与代码位置

| 模块 | 核心类 / 位置 | 初始化与运行 |
| --- | --- | --- |
| 车辆仿真 | `VehicleModel`；`WUTA-SIM/vehicle_model/src/vehicle_model/vehicle_model/vehicle_model.py` | 订阅命令；按 `dt` 积分自行车模型并发布 Odometry |
| LiDAR 仿真 | `LidarSimulatorNode`、`LidarSimulator`；`WUTA-SIM/perception_simulation/lidar_sim/` | 加载 YAML；启动时发布静态地图；定时生成 scan |
| 仿真桥接 | `SimulationBridge`；`WUTA-SIM/simulator_bringup/simulator_bringup/simulation_bridge.py` | 转发真值 pose、TF 与就绪/任务状态 |
| 感知 | `LidarDetectionNode` 与 `TraditionalDetector`；`WUTA-FSD/.../perception/lidar_detection/` | PointCloud2 转 PCL，检测后发布 ConeArray |
| 锥筒地图 | `ConeMapBuilder`；`WUTA-FSD/.../mapping/cone_map_builder/` | 用 TF 变换检测，去重、颜色分配、闭环和定时发布 |
| 边界/中心线 | `BoundaryDetectorNode` 与 `PathSearch`；`WUTA-FSD/.../planning/boundary_detector/` | 对局部锥筒执行 Delaunay/中点搜索 |
| 路径 | `PathGeneratorNode`；`WUTA-FSD/.../planning/path_generator/` | Trackdrive 转发中心线；另两赛项解析生成路径 |
| 控制 | `ControllerNode`、`PurePursuit`、`TwistFilter`；`WUTA-FSD/.../control/controller/` | 定时计算目标点、转向与速度限幅 |
| 定位 | `LocalizationManager`、`NdtLocalization`、KISS-ICP | KISS-ICP + EKF/INS 系统集成为待实现；NDT 仅在 NDT 模式运行 |

所有自定义 C++ 节点以 `rclcpp::spin(std::make_shared<...>())` 运行；Python 节点以
单节点 `rclpy.spin(node)` 运行。它们没有 ROS lifecycle 状态机，启动、运行和
shutdown 分别对应构造函数、回调/定时器和 `destroy_node()`/`rclcpp::shutdown()`。

## 2. Algorithm Design

### 2.1 LiDAR 与真值地图

```text
track YAML + vehicle pose
  -> 视场/距离/前向筛选
  -> 可选锥筒遮挡判断与检测概率
  -> 锥筒表面点 + 高斯噪声 + 地面点
  -> PointCloud2（lidar frame）
```

YAML 中的全部锥筒另作为静态 `map` marker 发布。marker 的圆柱高度按 YAML 底面位置
居中，颜色/尺寸来自锥筒规格，文本 marker 给出编号、类型和尺寸。此真值话题不进入
FSD 建图链路。

### 2.2 传统锥筒检测与地图

检测器以高度阈值或 RANSAC 去地面、体素下采样、欧氏聚类，再以宽度/高度/距离筛选。
`ConeMapBuilder` 以消息时间戳查询 `map <- sensor_frame`，在 `merge_distance` 内对坐标
做命中次数加权平均；未确认锥筒在发布前由 `min_hit_count` 过滤。颜色可按车辆航向的
左右叉积分配。达到最少确认数量且车辆离开又回到起点阈值内时，地图闭环并保存 YAML。

### 2.3 规划与控制

Trackdrive：`BoundaryDetectorNode` 提取 lookahead 范围内的蓝/黄/未知锥筒，构建 Delaunay
图并搜索中点序列，输出 `Lane`。Skidpad 按当前位姿/航向生成两个圆各两圈；Acceleration
按航向每米生成一个点并在最后 10 m 降速。控制器只在 `EXPLORE` 或 `RACE` 启用：以速度
比例的 lookahead 选择目标点，Pure Pursuit 计算命令，`TwistFilter` 再执行车辆约束/安全
过滤。

### 2.4 定位模式

KISS-ICP + EKF/INS 是待实现的系统集成：KISS-ICP 源码可将点云注册为里程计，EKF 配置
预期融合 `/kiss/odometry` 与 `/cg410/odometry`，但当前没有 INS 模拟器，且默认 bringup
不启动/连接这条链。`LocalizationManager` 已预留在 `LOC_KISS_ICP` 时接受
`/odometry/filtered`，在 `LOC_NDT` 时接受 `/ndt/pose`。NDT 读取 PCD 地图、等待初始位姿，
在 NDT 模式对降采样 scan 匹配并维护最多 500 个 pose 的路径。`map_saver` 的传感器到 map
变换在源码中仍标为 TODO，使用它保存地图前必须验证 TF 假设。

## 3. Communication and Concurrency Design

Topic 被用于连续流（点云、位姿、路径、命令和状态）；当前项目没有自定义 action。KISS
的 `reset` 使用 service，因为它是一次性状态改变。

`ConeMapBuilder` 明确创建两个 `MutuallyExclusive` callback group：50 Hz pose 回调和较慢的
锥筒整合回调互不占用同一个组；要获得并发执行效果，部署者还需配合 MultiThreadedExecutor，
而其 `main` 当前使用普通 `rclcpp::spin`。其他项目节点未创建 callback group，按单执行器
回调模型运行。

时间设计：桥接节点用 ground-truth 的 header stamp 同时发布 `map -> base_link`；LiDAR 节点
缓存这个 stamp 发布 lidar-frame 点云和可见 marker，避免 TF future extrapolation。

## 4. Design Decisions

| 问题 | 选择 | 原因与替代方案 |
| --- | --- | --- |
| 真值赛道如何调试 | `/sim/lidar/track_cones` 静态、Transient Local marker | 与 `/mapping/cone_map_viz` 的估计地图隔离；替代方案是直接发布 ConeMap，但会把仿真真值伪装成 FSD 输出 |
| 坐标变换 | ConeMapBuilder 在检测消息时间戳查询 TF | 保证地图与传感器观测时间一致；错误使用 `now()` 会造成时序偏差 |
| Trackdrive 路径 | Delaunay 中点路径 | 可由局部锥筒地图恢复赛道中心；Skidpad/Acceleration 用已知几何以避免不必要的锥筒依赖 |
| 定位模式切换 | MissionState 的 `localization_mode` | 将探索与比赛位姿源显式分开；当前 simulator 默认使用真值 bridge，不能等同于真实定位验证 |
| RViz marker 话题 | `.rviz` 使用 `Topic` 字段 | 无效字段会被 RViz 回退为 `visualization_marker_array`，该默认名不是系统接口 |
