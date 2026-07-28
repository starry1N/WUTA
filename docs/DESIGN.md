# WUTA ROS 2 内部设计

## 1. 模块设计与代码位置

| 模块 | 核心类 / 位置 | 初始化与运行 |
| --- | --- | --- |
| 车辆仿真 | `VehicleModel`；`WUTA-SIM/vehicle_model/src/vehicle_model/vehicle_model/vehicle_model.py` | 订阅命令；按 `dt` 积分自行车模型并发布 Odometry |
| LiDAR 仿真 | `LidarSimulatorNode`、`LidarSimulator`；`WUTA-SIM/perception_simulation/lidar_sim/` | 加载 YAML；启动时发布静态地图；定时生成 scan |
| 仿真桥接 | `SimulationBridge`；`WUTA-SIM/simulator_bringup/simulator_bringup/simulation_bridge.py` | 发布就绪和仿真开始输入；以真值跨线计单圈、以 LiDAR/命令头时间戳计延迟；订阅 MissionState 做状态可视化；真值 pose/TF 仅作显式回退 |
| 任务状态机 | `MissionManager`；`WUTA-FSD/ros2_ws/src/system/mission_manager/` | 唯一发布 MissionState；验证地图/定位/中心线门槛，按定位过线统计 Trackdrive 三圈 |
| 感知 | `LidarDetectionNode` 与 `TraditionalDetector`；`WUTA-FSD/.../perception/lidar_detection/` | PointCloud2 转 PCL，检测后发布 ConeArray |
| 锥筒地图 | `ConeMapBuilder`；`WUTA-FSD/.../mapping/cone_map_builder/` | 用 TF 变换检测，去重、颜色分配、闭环和定时发布 |
| 边界/中心线 | `BoundaryDetectorNode` 与 `PathSearch`；`WUTA-FSD/.../planning/boundary_detector/` | EXPLORE 局部搜索；闭环后从蓝黄锥地图生成、验收并冻结有序全局中心线 |
| 路径 | `PathGeneratorNode`；`WUTA-FSD/.../planning/path_generator/` | Trackdrive 环线切片和分圈速度剖面；Skidpad 固定四圈、退出和停车路径；Acceleration 解析直线路径 |
| 控制 | `ControllerNode`、`PurePursuit`、`TwistFilter`；`WUTA-FSD/.../control/controller/` | 定时计算目标点、转向与速度限幅 |
| 定位 | `INSSimulator`、`kiss_icp_node`、`ekf_node`、`LocalizationManager`、`NdtLocalization` | 默认融合 INS 与 KISS-ICP；NDT 仅在 NDT 模式运行 |

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
左右叉积分配。达到最少确认数量、累计行驶阈值、起点距离和起点朝向条件后，地图闭环并
保存 YAML。
闭环冻结前会按同一 `merge_distance` 对同色或未知色兼容轨迹做传递式最终合并，处理
独立轨迹均值在一圈内逐渐收敛后形成的重复堆叠；在线半径不扩大，避免误合并真实相邻锥桶。

无相机仿真可启用 `use_simulated_cone_colors`。检测器先将无颜色 ConeArray 发布到
`/perception/lidar/cones_raw`，`simulated_cone_colorizer` 使用同一采样时刻的真值位姿
将检测中心变换到 `map`，与 YAML 锥桶做距离门控匹配后仅复制颜色，再交给
`ConeMapBuilder`。builder 在该模式下关闭左右位置颜色启发式，但仍独立负责坐标估计、
命中融合、去重和闭环；因此该模式可评价建图几何，不等同于 `use_track_truth_map` 的
完整 ConeMap 快捷输入。真实系统仍应由相机检测与融合节点提供颜色。

### 2.3 规划与控制

Trackdrive：EXPLORE 时，`BoundaryDetectorNode` 提取 lookahead 范围内的蓝/黄/未知锥筒，
构建 Delaunay 图并搜索局部中点序列。`ConeMap.is_closed=true` 后，它仅从闭环锥桶地图配对
蓝黄边界、按车辆初始航向排序并验收覆盖率/闭合距离/段长，成功后冻结有方向的全局中心线；
不读取赛道 YAML 的 reference centerline。`PathGeneratorNode` 从冻结环线按连续进度切取 40 m
前向路径，按三点曲率计算 `v=sqrt(lateral_accel_limit / |curvature|)`。第一、二、三圈默认
速度上限依次为 7、9、10 m/s，且取前向可见距离、路径置信度和定位置信度形成的更低安全上限。
Skidpad 按 `skidpad_start_*` 固定 map 参考生成：右环顺时针
两圈、左环逆时针两圈，再沿进入方向退出 25 m 并制动；不以实时定位位姿重建。Acceleration
按赛道 map 参考穿过 75 m 终点线后在 100 m 停止区恒减速度制动。控制器在 `EXPLORE`、
`MAPPING_DONE` 或 `RACE` 启用，避免门槛验收期间停车：通常以速度
比例的 lookahead 选择目标点，Pure Pursuit 计算命令，`TwistFilter` 再执行车辆约束/安全
过滤。Trackdrive 使用固定 `trackdrive_lookahead=5.0 m`，并在短暂失去前向目标时以低速保留上一有效命令，
超时后停车；Acceleration 保持动态前视。Skidpad 专用 `skidpad_lookahead=3.0 m` 覆盖通用动态前视（5 m/s 下原本为 10 m）：
圆的半径仅 9.125 m，10 m 前视会跨越交叉点的曲率切换，从而在第一/三圈切入内侧、或在第四圈
出口过早卸载转向。自交叉 Skidpad 路径通过单调前向进度索引保持圈序；零速终点只有在车辆
进入完成位置容差后才能成为进度点，避免定位噪声导致出口或停止区提前停车；停车后控制器通知
`mission_manager` 发布 `FINISH`。

### 2.4 定位模式

`ins_simulator` 默认以 20 Hz 缓存 `/sim/ground_truth`，向位置、yaw、速度和角速度注入
可配置高斯噪声及协方差，再发布 `/cg410/odometry`。KISS-ICP 将 `/hesai/pandar` 注册为
`/kiss/odometry`；其 `lidar_odom_frame=odom` 且不发布 TF。EKF 融合这两路 Odometry，发布
`/odometry/filtered` 和唯一的动态 `odom -> base_link`。bringup 另发布静态同原点
`map -> odom` 与 `base_link -> lidar`，避免 TF 发布者冲突。`LocalizationManager` 在
`LOC_KISS_ICP` 时将 `/odometry/filtered` 转为 `/localization/pose`，在 `LOC_NDT` 时接受
`/ndt/pose`。`use_ground_truth_localization:=true` 是调试回退，不应与默认 EKF TF 并用。
该参数为 `false` 时，`simulation_bridge` 不创建真值 pose publisher 或 TF broadcaster。
NDT 读取 PCD 地图、等待初始位姿，在 NDT 模式对降采样 scan 匹配并维护最多 500 个 pose
的路径。`map_saver` 的传感器到 map 变换在源码中仍标为 TODO，使用它保存地图前必须验证
TF 假设。

### 2.5 调试可视化与状态机

`path_generator` 发布 `/planning/final_waypoints_viz`（规划参考路径）和
`/planning/driven_trajectory_viz`（定位估计的实际行驶轨迹）。后者只在可视化层对
`/localization/pose` 做一阶平滑与最小空间间隔采样；它不回写 EKF、不改变建图，也不改变控制输入。
因此 Ground Truth 用于判断仿真车辆真实运动，Driven Trajectory 用于观察实车可获得的定位轨迹。

`simulation_bridge` 不拥有任务状态：它发布就绪、可选真值定位，并在仿真中作为临时 VCU 输入源
周期发布 `/system/mission_mode_cmd`、`/system/start_command`、`/system/emergency=false` 与
`/system/inspection_trigger=false`；它订阅唯一的 `/system/mission_state` 生成
`/system/status_viz` 文字 marker。`mission_manager` 在两项 ready 后进入 READY，收到
`/system/start_command` 后进入 EXPLORE。Trackdrive 在地图闭合、地图质量、定位质量、冻结
全局中心线及第一圈均通过后进入 RACE；它用 `/localization/pose` 建立有限起终线并发布
`/system/lap_count`，第三圈后进入 FINISH。Skidpad/Acceleration 仍接收控制器的
`/system/mission_complete`。`manual_ready:=true` 时，bridge 以 RViz
`/clicked_point` 锁存人工 ready，供调试状态机。

FSD 的 `ros2_ws/src/system/can_interface/` 是实车 CAN/VCU 适配预留源码：其接口约定为 CAN
输入发布任务控制与车速、订阅任务状态/车检结果回传 CAN。该目录当前缺少 ROS package 构建文件，
默认 bringup 不编译、不启动；文档中的实车 CAN 输入均为待实现，不可当作已有硬件能力。

### 2.6 仿真赛项指标

`SimulationBridge` 以 `/sim/ground_truth` 的 `Odometry.header.stamp` 和位置计算成绩，因此
不受 INS/KISS-ICP/EKF 估计误差影响。Acceleration 从 `x=0` 起点线到 `x=75` 终点线；
Skidpad 在 `x=0` 的同一条线完成每个圆；Trackdrive 的正式圈次不使用仿真真值线，而由
`mission_manager` 以首次有效定位位姿及航向建立有限起终线，检查离线距离、累计距离、用时、
横向范围、穿越方向和航向。`SimulationBridge` 的真值过线只发布 `/system/lap_time` 并对照
正式 `/system/lap_count`，不触发 Trackdrive 完成。

控制器每次发布 `autoware_msgs/Command` 前填充 `header.stamp`。bridge 保存最新
`/hesai/pandar.header.stamp`，在收到命令时发布两者之差到 `/system/simulator_latency`；这表示
从最近一帧 LiDAR 采样发布到控制命令发布的端到端时延，不包含 DDS 到 bridge 的观测延迟。

## 3. Communication and Concurrency Design

Topic 被用于连续流（点云、位姿、路径、命令和状态）；当前项目没有自定义 action。KISS
的 `reset` 使用 service，因为它是一次性状态改变。

`ConeMapBuilder` 明确创建两个 `MutuallyExclusive` callback group：50 Hz pose 回调和较慢的
锥筒整合回调互不占用同一个组；要获得并发执行效果，部署者还需配合 MultiThreadedExecutor，
而其 `main` 当前使用普通 `rclcpp::spin`。其他项目节点未创建 callback group，按单执行器
回调模型运行。

时间设计：INS 使用 ground-truth header stamp；KISS 使用点云 stamp；EKF 用融合输出时间戳
发布 `odom -> base_link`。LiDAR 点云和 ConeArray 保留采样时间；`cones_viz` 在采样时刻
精确转换到 `map` 后发布。ConeMapBuilder 先按检测采样时间等待 TF，暂时不可用时排队重试，默认不使用 latest TF，
避免因为车辆运动把历史检测转换到错误位置。

## 4. Design Decisions

| 问题 | 选择 | 原因与替代方案 |
| --- | --- | --- |
| 真值赛道如何调试 | 默认 `/sim/lidar/track_cones` 只作静态 marker；`use_track_truth_map` 提供完整 ConeMap 快捷输入；`use_simulated_cone_colors` 只给在线 LiDAR 检测补颜色 | 快捷地图用于隔离规划/控制；颜色注入保留在线坐标、去重和闭环建图。两种模式均不向规划提供 YAML 中心线，也不替代正式相机融合 |
| 坐标变换 | ConeMapBuilder 只按检测时间查询 TF，短暂缺失时排队重试 | 保持传感器时序，避免用车辆当前位姿转换历史点云造成系统性偏移 |
| Trackdrive 路径 | EXPLORE 局部路径 + 闭环地图冻结全局中心线 | 第一圈在线建图，后两圈沿已验收的有序环线竞速；中心线始终由 ConeMap 推导 |
| Skidpad 交叉点跟踪 | Pure Pursuit 单调局部进度窗口 | 四圈与出口存在几何接近/重合点，按全部未来点搜索会直接跳至出口；每次只在有限连续窗口内推进可保证圈序 |
| Skidpad 横向前视 | 固定 `skidpad_lookahead=3.0 m` | 通用 `v×2.0` 在 5 m/s 时为 10 m，接近圆半径并跨越交叉点的曲率突变；短前视保留当前圆的转向至实际切换点 |
| Trackdrive 横向前视 | 固定 `trackdrive_lookahead=5.0 m`，短暂目标丢失低速保持 | 前视距离不再随 path_generator 的目标速度变化；局部中心线短暂反向/缺失时最多保持 0.5 s、2 m/s，超时停车，避免掉头或指令突变 |
| Trackdrive 纵向速度 | 第一圈 7、第二圈 9、第三圈 10 m/s 上限，叠加曲率/可见距离/路径与定位置信度限速 | 第一圈保持已有速度；只有门槛通过才逐圈提速，质量下降时自动回到保守速度 |
| 转向抖动抑制 | 连续 Pure Pursuit 曲率 + `max_steering_rate_deg_s` | 移除小横向误差的非连续放大；输出再按控制频率限转向速率，避免定位噪声直接成为执行器突变 |
| Acceleration 停车 | 固定 map 路径 + 终点线后恒减速度 | 计时 75 m 内保持速度；停止区使用 `v²=2aΔx`，避免线性速度-距离剖面造成停止点前无限逼近 |
| 仿真状态所有权 | mission_manager 唯一发布 MissionState | bridge 与状态机同时发布会产生竞争；bridge 只提供仿真 ready/start 输入与状态显示 |
| 定位 TF 所有权 | EKF 是默认唯一动态 TF 发布者 | 防止 KISS、真值 bridge 与 EKF 同时发布 `base_link`；真值 bridge 仅以显式参数回退 |
| RViz marker 话题 | `.rviz` 使用 `Topic` 字段 | 无效字段会被 RViz 回退为 `visualization_marker_array`，该默认名不是系统接口 |
