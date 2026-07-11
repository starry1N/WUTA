# ROS 2 接口规范

> 接口名和类型均来自节点源码。除特别说明外，`create_publisher(..., 10)`/
> `create_subscription(..., 10)` 表示 depth 10、可靠、volatile 的默认 QoS；
> `SensorDataQoS` 表示 best-effort、volatile、keep-last 的传感器 QoS。
>
> **状态约束：** INS 模拟器与 KISS-ICP + EKF 系统集成为待实现项。下表中 KISS、
> `/cg410/odometry`、`/odometry/filtered` 和 localization_manager 相关条目是源码/配置
> 已定义的预期接口，不属于当前默认仿真闭环。

## 1. Topic Interface

| Topic | Type | Publisher | Subscriber | 频率 / QoS |
| --- | --- | --- | --- | --- |
| `/sim/ground_truth` | `nav_msgs/msg/Odometry` | `vehicle_model` | lidar/can/bridge | vehicle `dt`，默认 50 Hz；depth 50 |
| `/hesai/pandar` | `sensor_msgs/msg/PointCloud2` | `lidar_simulator` | lidar_detection、NDT、map_saver、KISS-ICP | 默认 10 Hz；发布 depth 10；检测/NDT/map_saver 用 SensorDataQoS |
| `/sim/lidar/visible_cones` | `visualization_msgs/msg/MarkerArray` | `lidar_simulator` | RViz | 随扫描；depth 10；`lidar` frame |
| `/sim/lidar/track_cones` | `visualization_msgs/msg/MarkerArray` | `lidar_simulator` | RViz | 启动时一次；Reliable + Transient Local；`map` frame |
| `/localization/velocity` | `geometry_msgs/msg/TwistStamped` | `can_simulator` | controller | 随 ground truth；depth 50 |
| `/localization/pose` | `geometry_msgs/msg/PoseStamped` | simulation_bridge（默认仿真）或 localization_manager（可选） | 建图/规划/控制 | bridge 随 ground truth；depth 10 |
| `/perception/lidar/cones` | `wuta_msgs/msg/ConeArray` | lidar_detection | cone_map_builder | 随点云；depth 10 |
| `/perception/lidar/cones_viz` | `visualization_msgs/msg/MarkerArray` | lidar_detection | RViz | 有订阅者时；depth 10 |
| `/mapping/cone_map` | `wuta_msgs/msg/ConeMap` | cone_map_builder | boundary_detector、mission_manager | 5 Hz 定时器；depth 10 |
| `/mapping/cone_map_viz` | `visualization_msgs/msg/MarkerArray` | cone_map_builder | RViz | 5 Hz；depth 10 |
| `/planning/centerline` | `autoware_msgs/msg/Lane` | boundary_detector | path_generator | 收到地图时；depth 10 |
| `/planning/centerline_viz` | `visualization_msgs/msg/MarkerArray` | boundary_detector | RViz | 有订阅者时；depth 10 |
| `/planning/final_waypoints` | `autoware_msgs/msg/Lane` | path_generator | controller | 中心线或任务状态触发；depth 10 |
| `/control/command` | `autoware_msgs/msg/Command` | controller | vehicle_model | 控制定时器，默认 50 Hz；depth 10 |
| `/control/target_viz` | `visualization_msgs/msg/MarkerArray` | controller | RViz | 有订阅者时；depth 10 |
| `/system/mission_state` | `wuta_msgs/msg/MissionState` | simulation_bridge（默认）或 mission_manager | 规划/控制/定位/NDT/map_saver | bridge 10 Hz；depth 10 |
| `/system/lidar_ready` | `std_msgs/msg/Bool` | simulation_bridge | mission_manager | 10 Hz；depth 10 |
| `/system/localization_ready` | `std_msgs/msg/Bool` | simulation_bridge 或 localization_manager | mission_manager | 10 Hz（bridge）；depth 10 |
| `/odometry/filtered` | `nav_msgs/msg/Odometry` | robot_localization EKF | localization_manager | 待实现 KISS+EKF 集成；depth 10 |
| `/kiss/odometry` | `nav_msgs/msg/Odometry` | kiss_icp_node | map_saver、EKF 配置 | 待实现 KISS+EKF 集成；KISS QoS 配置 |
| `/ndt/pose` | `geometry_msgs/msg/PoseStamped` | ndt_localization | localization_manager | NDT 激活时；depth 10 |
| `/ndt/path` | `nav_msgs/msg/Path` | ndt_localization | 工具/RViz | NDT 激活时；depth 10 |
| `/ndt/aligned_cloud` | `sensor_msgs/msg/PointCloud2` | ndt_localization | 工具/RViz | 有订阅者时；depth 10 |
| `/ndt/map_ready` | `std_msgs/msg/Bool` | map_saver | 外部编排 | 保存成功时；depth 10 |
| `/initialpose` | `geometry_msgs/msg/PoseWithCovarianceStamped` | 外部（RViz/定位工具） | ndt_localization | depth 10 |
| `/system/emergency` | `std_msgs/msg/Bool` | 外部 | mission_manager | depth 10 |
| `/system/mission_mode_cmd` | `std_msgs/msg/String` | 外部 | mission_manager | depth 10 |
| `/system/inspection_trigger` | `std_msgs/msg/Bool` | 外部 | mission_manager | depth 10 |
| `/system/inspection_result` | `std_msgs/msg/String` | mission_manager | 外部 | 车检触发后；当前内容为未实现提示 |

KISS-ICP 源码还会在 `publish_debug_clouds=true` 时发布相对名称 `kiss/frame`、
`kiss/keypoints`、`kiss/local_map`（均 `PointCloud2`）。这些是待实现 KISS+EKF 集成可用的
接口，不属于 simulator 默认 bringup。

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
  float64 speed
  float64 angle
  int32 dv_state
```

## 2. Service and Action Interface

本项目自身节点未定义 `.srv` 或 `.action`，也没有在默认 bringup 中创建 service/action。

作为源码依赖引入的 KISS-ICP ROS 节点创建相对名 `reset` service：

| Service | Type | Request | Response | 作用 |
| --- | --- | --- | --- | --- |
| `reset`（kiss_icp_node） | `std_srvs/srv/Empty` | 空 | 空 | 重置 KISS-ICP 状态 |

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
 └─ base_link       dynamic: simulation_bridge，时间来自 /sim/ground_truth
     └─ lidar       static: simulator.launch.py，平移 (0, 0, 1) m
```

待实现 KISS-ICP 集成的 frame 名由参数 `lidar_odom_frame`（wrapper 默认 `odom`）和
`base_frame`（默认 `base_link`）决定，并可按 `publish_odom_tf` 发布 TF。EKF 配置中
`world_frame=odom`，并将 `map_frame=map`、`odom_frame=odom`、`base_link_frame=base_link`。

`/sim/lidar/visible_cones` 与 `/hesai/pandar` 在 `lidar`；其时间戳与 ground truth
对齐，避免 RViz 请求未来的 `map -> base_link`。`/sim/lidar/track_cones` 直接在 `map`。

## 4. Parameters

| Node | 参数（类型） | 来源 / 说明 |
| --- | --- | --- |
| vehicle_model | `wheel_base`、`max_steer_angle`、`dt`、`start_x/y/yaw`（double） | `vehicle_model.py` / launch |
| lidar_simulator | topic/frame 名（string）、`publish_rate_hz`/FOV/范围/噪声（double）、点数（int）、开关（bool） | `config/lidar_simulator.yaml` |
| simulation_bridge | `ground_truth_topic`、`mission_mode`、`map_frame`、`base_frame`（string）；`publish_mission_state`（bool） | `simulation_bridge.py` |
| lidar_detection_node | `detector_type`、topic 名、地面/体素/聚类/几何阈值、`model_path` | `config/lidar_detection.yaml` |
| cone_map_builder | `merge_distance`、`min_hit_count`、闭环阈值、`assign_colors`、`map_save_path` | `config/cone_map_builder.yaml` |
| boundary_detector_node | `lookahead_distance`、`desired_velocity` | `config/boundary_detector.yaml` |
| path_generator_node | Trackdrive/Skidpad/Acceleration 速度、半径、点数、长度 | `config/path_generator.yaml` |
| controller_node | 车辆几何、Pure Pursuit lookahead、`control_rate_hz` | `config/controller.yaml` |
| mission_manager | `mission_mode`（string） | `mission_manager.cpp` |
| localization_manager | 无显式声明参数 | 待实现定位集成；通过固定话题与 MissionState 选源 |
| ndt_localization / map_saver | 地图路径、NDT/体素参数、累积距离 | `config/ndt_localization.yaml` |
| kiss_icp_node | 待实现集成：frame/TF、协方差、范围、体素、阈值、迭代参数 | `kiss_icp_wrapper/config/kiss_icp_hesai128.yaml` |

完整参数名、默认值与类型以对应 YAML 和节点 `declare_parameter` 为准。
