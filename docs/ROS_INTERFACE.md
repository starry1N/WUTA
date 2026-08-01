# ROS 2 接口规范

> 接口名和类型均来自节点源码。除特别说明外，`create_publisher(..., 10)`/
> `create_subscription(..., 10)` 表示 depth 10、可靠、volatile 的默认 QoS；
> `SensorDataQoS` 表示 best-effort、volatile、keep-last 的传感器 QoS。
>
> **默认定位链：** `ins_simulator`、KISS-ICP、EKF 与 localization_manager 默认启动。
> `/sim/ground_truth` → `/cg410/odometry` 与 `/hesai/pandar` → `/kiss/odometry` 由 EKF
> 融合为 `/odometry/filtered`，再转换为 `/localization/pose`。

## 1. Topic Interface

| Topic | Type | Publisher | Subscriber | 频率 / QoS |
| --- | --- | --- | --- | --- |
| `/sim/ground_truth` | `nav_msgs/msg/Odometry` | `vehicle_model` | lidar/can/bridge | vehicle `dt`，默认 50 Hz；depth 50 |
| `/hesai/pandar` | `sensor_msgs/msg/PointCloud2` | `lidar_simulator` | lidar_detection、NDT、map_saver、KISS-ICP、simulation_bridge | 默认 10 Hz；发布 depth 10；检测/NDT/map_saver 用 SensorDataQoS；其 `header.stamp` 是仿真端到端延迟的起点 |
| `/sim/lidar/visible_cones` | `visualization_msgs/msg/MarkerArray` | `lidar_simulator` | RViz | 随扫描；depth 10；`lidar` frame；marker stamp=0（最新 TF） |
| `/sim/lidar/track_cones` | `visualization_msgs/msg/MarkerArray` | `lidar_simulator` | RViz | 启动时一次；Reliable + Transient Local；`map` frame |
| `/localization/velocity` | `geometry_msgs/msg/TwistStamped` | `can_simulator` | controller | 随 ground truth；depth 50 |
| `/cg410/odometry` | `nav_msgs/msg/Odometry` | `ins_simulator` | `ekf_node` | 默认启动，20 Hz；depth 20；`map` frame |
| `/localization/pose` | `geometry_msgs/msg/PoseStamped` | `localization_manager`（默认）或 simulation_bridge（真值回退） | 建图/规划/控制 | 随 EKF 输出；bridge 仅在 `use_ground_truth_localization=true` 时注册发布器；depth 10 |
| `/perception/lidar/cones_raw` | `wuta_msgs/msg/ConeArray` | lidar_detection（仅模拟颜色模式） | simulated_cone_colorizer | 随点云；保留原检测坐标和采样时间；depth 10 |
| `/perception/lidar/cones` | `wuta_msgs/msg/ConeArray` | 默认 lidar_detection；模拟颜色模式为 simulated_cone_colorizer；未来相机融合待实现 | cone_map_builder | 随点云；模拟颜色模式只改 `color`，两种发布路径互斥；未来相机融合应向既有消息填充稳定蓝/黄 `color`，不新增真值中心线接口；depth 10 |
| `/perception/lidar/cones_viz` | `visualization_msgs/msg/MarkerArray` | lidar_detection | RViz | 有订阅者时；转换到 `map` 后发布；使用采样时间；depth 10 |
| `/mapping/cone_map` | `wuta_msgs/msg/ConeMap` | 默认 `cone_map_builder`；`use_track_truth_map=true` 时 `track_truth_map_publisher` | boundary_detector、mission_manager | 5 Hz；builder 为 Reliable + Volatile、depth 10，真值快捷模式为 Reliable + Transient Local、depth 1；两种模式互斥 |
| `/mapping/cone_map_viz` | `visualization_msgs/msg/MarkerArray` | 默认 cone_map_builder；`use_track_truth_map=true` 时 track_truth_map_publisher | RViz | 5 Hz；builder 为 Reliable + Volatile、depth 10，真值快捷模式为 Reliable + Transient Local、depth 1；按算法输入渲染蓝/黄/橙锥桶 |
| `/planning/centerline` | `autoware_msgs/msg/Lane` | boundary_detector | path_generator | EXPLORE 为局部中心线；闭环验收后为冻结的有序全局中心线；depth 10 |
| `/planning/centerline_viz` | `visualization_msgs/msg/MarkerArray` | boundary_detector | RViz | 有订阅者时；depth 10 |
| `/planning/global_centerline_ready` | `std_msgs/msg/Bool` | boundary_detector | mission_manager、path_generator | 全局中心线验收结果；Reliable + Transient Local |
| `/planning/path_confidence` | `std_msgs/msg/Float32` | boundary_detector | path_generator | 局部/全局路径置信度 `[0,1]`；Reliable + Transient Local |
| `/planning/final_waypoints` | `autoware_msgs/msg/Lane` | path_generator | controller | 中心线或任务状态触发；depth 10 |
| `/planning/final_waypoints_viz` | `visualization_msgs/msg/MarkerArray` | path_generator | RViz | 最终参考路径 `LINE_STRIP`；任务路径发布时；depth 10 |
| `/planning/driven_trajectory_viz` | `visualization_msgs/msg/MarkerArray` | path_generator | RViz | `/localization/pose` 经仅可视化的一阶平滑和空间降采样后累积；每 3 个位置点更新；depth 10 |
| `/control/command` | `autoware_msgs/msg/Command` | controller | vehicle_model、simulation_bridge | 控制定时器，默认 50 Hz；depth 10；`header.stamp` 在控制器发布前写入，是仿真端到端延迟的终点 |
| `/system/mission_complete` | `std_msgs/msg/Bool` | controller | mission_manager | Skidpad 在固定 25 m 出口或 Acceleration 在终点线后 100 m 停止区末端停车后一次发布 `true`；mission_manager 据此进入 FINISH；depth 10 |
| `/control/target_viz` | `visualization_msgs/msg/MarkerArray` | controller | RViz | 有订阅者时；depth 10 |
| `/system/mission_state` | `wuta_msgs/msg/MissionState` | mission_manager | 规划/控制/定位/NDT/map_saver、simulation_bridge | **唯一发布者**；10 Hz；depth 10 |
| `/system/lap_count` | `std_msgs/msg/UInt32` | mission_manager | cone_map_builder、path_generator、track_truth_map_publisher、simulation_bridge | 由定位位姿穿越正式起终线生成；Reliable + Transient Local；builder 在首个正式建图圈后冻结地图，第三圈后 FINISH |
| `/system/start_command` | `std_msgs/msg/Bool` | simulation_bridge（`auto_start=true`）或外部；实车 CAN 接口待实现 | mission_manager | 仿真出发输入；`true` 使 READY 进入 EXPLORE；depth 10 |
| `/clicked_point` | `geometry_msgs/msg/PointStamped` | RViz Publish Point | simulation_bridge | `manual_ready=true` 时，一次点击锁存人工就绪并使 bridge 发布 ready；depth 10 |
| `/system/lap_time` | `std_msgs/msg/Float64` | simulation_bridge | RViz/记录工具 | 仿真真值跨线用时；仅用于成绩和正式圈次对照，不控制 Trackdrive 状态机 |
| `/system/simulator_latency` | `std_msgs/msg/Float64` | simulation_bridge | RViz/记录工具 | 每个控制命令发布；单位 s；`/control/command.header.stamp - 最新 /hesai/pandar.header.stamp` |
| `/system/status_viz` | `visualization_msgs/msg/MarkerArray` | simulation_bridge | RViz | 10 Hz；显示任务模式、状态、真值速度/位置、最近单圈用时与 LiDAR→命令延迟；depth 10 |
| `/system/lidar_ready` | `std_msgs/msg/Bool` | simulation_bridge | mission_manager | 10 Hz；depth 10 |
| `/system/localization_ready` | `std_msgs/msg/Bool` | localization_manager（默认）或 simulation_bridge（真值回退） | mission_manager | 随定位输出；depth 10 |
| `/system/localization_confidence` | `std_msgs/msg/Float32` | localization_manager（默认）或 simulation_bridge（真值回退） | mission_manager、path_generator | 协方差派生或真值调试置信度 `[0,1]`；depth 10 |
| `/odometry/filtered` | `nav_msgs/msg/Odometry` | robot_localization `ekf_node` | localization_manager | 默认融合输出；50 Hz；`odom` frame |
| `/kiss/odometry` | `nav_msgs/msg/Odometry` | `kiss_icp_node` | `kiss_odom_sanitizer_node`（可选）、map_saver | 默认约 10 Hz；`odom` frame；KISS 不发布 TF；默认只作诊断/地图保存，不直接进入 EKF |
| `/kiss/odometry_sanitized` | `nav_msgs/msg/Odometry` | `kiss_odom_sanitizer_node` | `ekf_node` | 仅 `fuse_kiss_odometry=true`；只携带通过检查的车体系 `vx/vy/yaw_rate`，不携带可融合的 KISS pose |
| `/ndt/pose` | `geometry_msgs/msg/PoseStamped` | ndt_localization | localization_manager | NDT 激活时；depth 10 |
| `/ndt/path` | `nav_msgs/msg/Path` | ndt_localization | 工具/RViz | NDT 激活时；depth 10 |
| `/ndt/aligned_cloud` | `sensor_msgs/msg/PointCloud2` | ndt_localization | 工具/RViz | 有订阅者时；depth 10 |
| `/ndt/map_ready` | `std_msgs/msg/Bool` | map_saver | mission_manager、外部编排 | 保存成功时发布 `true`；仅当 `use_ndt_race_localization=true` 时作为 RACE 门槛；depth 10 |
| `/initialpose` | `geometry_msgs/msg/PoseWithCovarianceStamped` | 外部（RViz/定位工具） | ndt_localization | depth 10 |
| `/system/emergency` | `std_msgs/msg/Bool` | simulation_bridge（仿真固定 `false`）或外部；实车 CAN 接口待实现 | mission_manager | depth 10 |
| `/system/mission_mode_cmd` | `std_msgs/msg/String` | simulation_bridge（由 launch 的 `mission_mode` 映射）或外部；实车 CAN 接口待实现 | mission_manager | `trackdrive`/`skidpad`/`acceleration`；depth 10 |
| `/system/inspection_trigger` | `std_msgs/msg/Bool` | simulation_bridge（仿真固定 `false`）或外部；实车 CAN 接口待实现 | mission_manager | depth 10 |
| `/system/inspection_result` | `std_msgs/msg/String` | mission_manager | 外部 | 车检触发后；当前内容为未实现提示 |

KISS-ICP 在 `publish_debug_clouds=true` 时还会发布相对名称 `kiss/frame`、
`kiss/keypoints`、`kiss/local_map`（均 `PointCloud2`）；默认配置关闭这些调试点云。

### Message Structure

```text
wuta_msgs/msg/Cone
  geometry_msgs/Point position
  uint8 color  # UNKNOWN=0, BLUE=1, YELLOW=2, ORANGE=3
  float32 confidence

wuta_msgs/msg/ConeArray
  std_msgs/Header header  # sensor 或 map frame
  Cone[] cones

wuta_msgs/msg/ConeMap
  std_msgs/Header header  # map
  Cone[] blue_cones, yellow_cones, orange_cones, unknown_cones
  bool is_closed

wuta_msgs/msg/MissionState
  Header header; uint8 state; uint8 mission_mode; uint8 localization_mode
  string description

autoware_msgs/msg/Lane
  Header header
  Waypoint[] waypoints  # PoseStamped pose + TwistStamped twist

autoware_msgs/msg/Command
  std_msgs/Header header  # controller writes publish timestamp; frame_id=base_link
  float64 speed
  float64 angle
  int32 dv_state
```

## 2. Service and Action Interface

本项目自身节点未定义 `.srv` 或 `.action`。默认 bringup 中的 KISS-ICP 节点创建 reset
service。

作为源码依赖引入的 KISS-ICP ROS 节点创建相对名 `reset` service：

| Service | Type | Request | Response | 作用 |
| --- | --- | --- | --- | --- |
| `/kiss/reset`（kiss_icp_node） | `std_srvs/srv/Empty` | 空 | 空 | 重置 KISS-ICP 状态 |

仓库中的 robot_localization 包定义以下服务类型。它们由该第三方包的过滤/地理坐标节点
按自身配置提供，不由 WUTA 的 `simulator.launch.py` 启动，因此不能视为默认系统服务。

| Type | Request | Response |
| --- | --- | --- |
| `robot_localization/srv/FromLL` | `geographic_msgs/GeoPoint ll_point` | `geometry_msgs/Point map_point` |
| `robot_localization/srv/ToLL` | `geometry_msgs/Point map_point` | `geographic_msgs/GeoPoint ll_point` |
| `robot_localization/srv/SetDatum` | `geographic_msgs/GeoPose geo_pose` | 空 |
| `robot_localization/srv/SetPose` | `geometry_msgs/PoseWithCovarianceStamped pose` | 空 |
| `robot_localization/srv/GetState` | `builtin_interfaces/Time time_stamp`、`string frame_id` | `float64[15] state`、`float64[225] covariance` |
| `robot_localization/srv/ToggleFilterProcessing` | `bool on` | `bool status` |

仓库中未定义 action 文件。

## 3. TF Frame

默认仿真 TF 树：

```text
map
 └─ odom            static: simulator.launch.py，仿真中与 map 同原点
     └─ base_link   dynamic: ekf_node
         └─ lidar   static: simulator.launch.py，平移 (0, 0, 1) m
```

KISS-ICP 的 `lidar_odom_frame=odom`、`base_frame=base_link`，且
`publish_odom_tf=false`，避免与 EKF 竞争 TF。EKF 配置为 `world_frame=odom`，发布唯一的
动态 `odom -> base_link`。`use_ground_truth_localization:=true` 时，simulation_bridge
才会额外发布真值 `map -> base_link`，因此不能和默认 EKF TF 同时用于 FSD。

`/hesai/pandar` 与 `/perception/lidar/cones` 保留 ground-truth 采样时间，供感知和建图
使用。`/perception/lidar/cones_viz` 在采样时刻精确转换到 `map` 后发布，因此 RViz 不再
需要查询历史 `map -> lidar` TF。仅用于 RViz 的
`/sim/lidar/visible_cones` 使用零时间戳请求最新 `map -> odom -> base_link -> lidar` TF。
`/sim/lidar/track_cones` 与 `/mapping/cone_map_viz` 直接在 `map`。

## 4. Parameters

| Node | 参数（类型） | 来源 / 说明 |
| --- | --- | --- |
| vehicle_model | `wheel_base`、`max_steer_angle`、`dt`、`start_x/y/yaw`（double） | `vehicle_model.py` / launch |
| lidar_simulator | topic/frame 名（string）、`publish_rate_hz`/FOV/范围/噪声（double）、点数（int）、开关（bool） | `config/lidar_simulator.yaml` |
| simulation_bridge | `ground_truth_topic`、`map_frame`、`base_frame`、`mission_mode_cmd`（string）；`publish_start_command`、`publish_truth_localization`、`manual_ready`（bool）；`timing_min_lap_duration`（double）、`trackdrive_finish_laps`（int） | 提供仿真就绪/GO/急停/车检输入、真值计时、延迟、真值定位调试和状态显示；订阅正式圈次用于对照，Trackdrive 完成权属于 mission_manager |
| track_truth_map_publisher | `track_file`、`map_topic`、`visualization_topic`、`map_frame`（string）；`mapping_laps`（int）、`publish_rate_hz`（double） | 将 YAML 锥桶坐标/颜色转换为 ConeMap，模拟相机提供正确颜色；达到正式建图圈数后闭环，不发布 YAML 中心线 |
| simulated_cone_colorizer | `track_file`、`input_topic`、`output_topic`、`ground_truth_topic`（string）；`max_match_distance`、`max_pose_age_sec`、`lidar_offset_x/y`（double）；`pose_history_size`（int） | 仅模拟颜色模式启动；按时间戳真值位姿匹配 YAML 锥桶并只复制颜色，不生成地图或中心线。实车对应能力为**待实现**的相机锥桶检测/融合：应复用既有 `ConeArray` 颜色字段，避免紧凑赛道中无颜色 Delaunay 的跨段歧义 |
| lidar_detection_node | `detector_type`、topic 名、地面/体素/聚类/几何阈值、`model_path` | `config/lidar_detection.yaml` |
| cone_map_builder | `merge_distance`、`consolidation_distance`、`min_hit_count`、`mapping_laps`、几何闭环阈值、`assign_colors`、`map_save_path`、`tf_lookup_timeout_sec`、`pending_detection_timeout_sec`、`max_pending_detections`、`localization_jump_threshold`、`localization_jump_cooldown_sec`、`use_latest_tf_fallback` | `config/cone_map_builder.yaml`；每帧以最近兼容轨迹关联，并记录同帧共视的真实近邻；定位跳变时清空待处理检测并暂停融合；在线去重只合并从未共视的轨迹，正式圈次闭图且保留几何兜底；默认只使用检测采样时刻 TF，缺失时排队重试 |
| boundary_detector_node | 局部 lookahead/配对/Delaunay 参数；全局宽度、去重、几何邻域/切向一致性、最大段长/闭合距离、最小点数/覆盖率 | 只根据 ConeMap 与定位生成中心线；闭环后优先按颜色配对，失败时使用局部切向筛选横跨赛道锥桶对，再以同一质量门槛验收并冻结；不读取 YAML 中心线 |
| path_generator_node | Trackdrive 第一圈/第二圈/第三圈速度、曲率、全局前视段、短路径、可见距离、置信度与定位超时参数；其他赛项参数 | 第一圈 7 m/s 上限，RACE 两圈 9/10 m/s；冻结环线切片后取曲率、可见距离、路径/定位置信度的最低速度上限 |
| controller_node | 车辆几何、Pure Pursuit lookahead/连续进度窗口、`skidpad_lookahead=3.0 m`、`trackdrive_dynamic_lookahead`、Trackdrive 3–5 m 曲率前视、目标丢失保持参数、起步稳定参数 `trackdrive_start_speed=3.0 m/s` / `trackdrive_start_speed_duration=4.0 s`、`control_rate_hz`、`max_steering_rate_deg_s`、Skidpad 完成位置/速度阈值 | `config/controller.yaml`；Skidpad 固定前视；Trackdrive 从前方 12 m 中心线估计曲率，在 3–5 m 间按变化率限制调整前视，且不随规划速度变化。首个有效前向目标出现后，Trackdrive 在配置时长内将速度目标固定为 3 m/s，以等待初始在线地图/中心线稳定；设时长为 0 可关闭。其后 Trackdrive 从前视点读取曲率速度，Skidpad/Acceleration 从单调路径进度读取速度；转向输出按速率限制抑制定位噪声引起的抖动 |
| mission_manager | 地图质量、定位质量/超时、正式圈数、起终线距离/用时/宽度/航向、`use_ndt_race_localization` | 唯一发布 MissionState 和正式圈次；五项门槛通过后 RACE，第三圈后 FINISH |
| ekf_node | `odom0/odom1` 配置、INS pose 门限、过程噪声 | `localization_manager/config/ekf.yaml`；INS 提供绝对 pose、纵向速度和 yaw rate；可选 KISS sanitizer 只提供速度约束，KISS pose 永不融合 |
| kiss_odom_sanitizer_node | 输入/输出/INS topic、INS 超时、硬速度/yaw rate 上限、INS 速度/yaw rate 差值门限 | 仅 `fuse_kiss_odometry=true`；从 KISS 增量推导 twist，拒绝非有限、异常时间间隔、过大增量及与 INS 不一致的样本 |
| localization_manager | 无显式声明参数 | 默认定位集成；通过固定话题与 MissionState 选源；拒绝非有限输出，并在 FINISH/EMERGENCY 停止转发 |
| ndt_localization / map_saver | 地图路径、NDT/体素参数、累积距离 | `config/ndt_localization.yaml` |
| kiss_icp_node | frame/TF、协方差、范围、体素、阈值、迭代参数 | `kiss_icp_wrapper/config/kiss_icp_hesai128.yaml` |

完整参数名、默认值与类型以对应 YAML 和节点 `declare_parameter` 为准。
