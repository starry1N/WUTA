# 工控机交接：双目 YOLOv8 / LiDAR 后融合

本文面向在工控机继续开发的 agent，更新于 2026-09-15。最初交接基线为顶层仓库
`4450f66`（`main`）和 FSD 子模块 `b754e5e`（`小登测试`）；今天的实机开发仍存在
未提交本地修改，重新 clone 不会自动获得。接手前检查顶层和子模块 `git status`，
当前完成项与现场数据以 [HARDWARE_FUSION.md](HARDWARE_FUSION.md) 为准。

## 获取与构建

```bash
git clone --recurse-submodules https://github.com/starry1N/WUTA.git
cd WUTA
git submodule sync --recursive
git submodule update --init --recursive

cd WUTA-FSD/ros2_ws
./build_ws.sh --lightweight
source install/setup.bash
cd ../../WUTA-SIM
colcon build --base-paths . --symlink-install --packages-up-to simulator_bringup --parallel-workers 1
```

FSD 使用 `小登测试` 分支；嵌套的 KISS-ICP 和 robot_localization 必须初始化。
融合新增 ROS 接口，因此不能只复制旧的 `install/` 目录或使用旧 build 产物。

## 当前可运行入口

融合仿真入口：

```bash
./start_fusion_simulator.sh --rviz
./start_fusion_simulator.sh --skip-build track_file:=trackdrive mission_mode:=trackdrive
```

它会启动合成 LiDAR、传统 LiDAR 锥筒检测、合成双目检测、后融合、ConeMapBuilder 和原有
规划控制。RViz 配置显示 `/hesai/pandar` 原始点云，以及
`/mapping/cone_map_viz` 的融合建图结果。这里的“相机”是
`simulated_stereo_detections`，它仅用 YAML/真值生成检测级观测，不能代表 YOLO 或双目实机性能。

当前工控机真实 ZED 2i/M1 入口：

```bash
./start_simulator.sh --hardware --skip-build --rviz
# 只查看正在运行的系统，不重启驱动
./start_simulator.sh --hardware --view-only
```

当前默认权重位于 `WUTA-FSD/ros2_ws/src/perception/camera_detection/models/yolov8sp2-int8.engine`，外参位于
`WUTA-FSD/ros2_ws/src/perception/calibration/camera_lidar.yaml`。默认 TensorRT INT8，
red 代表橙色锥桶。真实点云 `/rslidar_points` 与 ZED 注册图像/深度进入融合，ZED pose/TF
支持独立设备建图；RViz 仅显示点云和地图，独立终端显示 YOLO 叠框图像。
三个启动脚本实际启动前会停止旧 WUTA launch 及子进程；仅构建、查看参数和
`--view-only` 不清理。直接 `ros2 launch` 没有这项脚本清理。
现场门限集中在 [perception/config](../WUTA-FSD/ros2_ws/src/perception/config/README.md)；
`--debug-orange --rviz` 仅显示当前橙锥位置，并清除旧标记。

通用外部设备适配入口仍保留：

```bash
ros2 launch detection_fusion fusion_mapping.launch.py
```

该入口不启动真实驱动、YOLO 推理或车辆控制。必须由外部提供：

| 输入 | 类型/要求 |
| --- | --- |
| `/hesai/pandar` | `sensor_msgs/msg/PointCloud2`，LiDAR 驱动输出，时间同步且扫描已去畸变 |
| `/camera/yolo/cones` | `wuta_msgs/msg/CameraConeDetectionArray`，已撤销 letterbox/缩放的左目校正图像框与颜色概率 |
| `/camera/left/depth_registered` | `sensor_msgs/msg/Image`，32FC1 米或 16UC1 毫米，已对齐左目 |
| `/camera/left/camera_info` | `sensor_msgs/msg/CameraInfo`，左目校正 P 矩阵和一致的 frame/resolution |
| TF 与 `/localization/pose` | 覆盖 LiDAR 扫描和相机曝光两个采样时刻；`odom` 必须连续 |

物理外参 `base_link -> camera_left_optical_frame`、相机内参、时间偏移、YOLOv8 权重和类别映射
由硬件侧提供。类别须映射至 UNKNOWN/BLUE/YELLOW/ORANGE 概率；高/低黄锥当前均为 YELLOW。

## 已实现与未完成内容

已实现：双目深度适配、LiDAR 时间触发、基于 TF 的 LiDAR 扫描时刻到相机曝光时刻补偿、
投影/空间门控、歧义拒绝、Hungarian 一对一关联、颜色传递、保守 XY 位置融合，以及输入现有
ConeMapBuilder 的接线。建图在融合模式禁用车辆左右侧猜色，并要求三次颜色支持。

今天另已完成外部 ZED/M1 驱动接线、GPU PT YOLO、已有外参静态 TF、叠框图像、
RANSAC 地面法向约束和框引导真实点云裁剪/深度分层聚类。默认仅发布相机匹配目标。
未完成：运动时硬件同步/扫描去畸变、外参精度验收、锥筒统一参考点标定、协方差地图
滤波、全类别多锥场景与故障注入验收。原始左右图匹配由 ZED SDK 提供。
硬件入口默认 `fuse_positions=false`；完成共同位置参考和误差模型验证前，不要开启它。

相关感知/建图包已构建并完成实机 ROS 联调。最新 20 秒采样有 16 个匹配与框引导目标、
15 个着色目标，但 128 帧融合周期中 111 帧 camera_timeout，地图仍有 2 个 UNKNOWN。
已观察到单帧 BLUE，累计地图颜色确认尚未闭环；优先检查有效检测吞吐、时间关联和
同一轨迹颜色票数，不应把单帧蓝框视为完整地图验收。

## 首次验证顺序

1. 按上述顺序完成两层构建，运行 `./start_fusion_simulator.sh --rviz`。
2. 确认 `/perception/fused/cones` 的 header stamp/frame 等于对应 LiDAR 检测，而非推理完成时间。
3. 确认 `/mapping/cone_map` 只有 cone_map_builder 发布，且 builder 订阅 fused/cones。
4. 检查 `/perception/fusion/status`：可见锥筒时 `matches` 和 `colored` 应出现非零；持续
   `transform_unavailable` 表明 TF/采样时间未满足契约。
5. 以 `simulate_camera:=false` 复测相机掉线退化：应发布 LiDAR-only UNKNOWN 观测，
   不得用左右侧启发式给地图染色。
6. 实机先保持 `fuse_positions=false`，记录 rosbag 后计算颜色错配、漏检、重复地标和时序误差，
   再决定是否调门限或开启位置融合。

建议记录：仿真 `/hesai/pandar` 或实机 `/rslidar_points`、`/perception/lidar/cones_raw`、
`/perception/camera/cones`、`/perception/camera/camera_info`、
`/perception/fused/cones`、`/perception/fusion/status`、`/mapping/cone_map`、
`/tf`、`/tf_static`、`/localization/pose`。完整参数、消息字段、关联公式和退化规则见
[LATE_FUSION.md](LATE_FUSION.md)。
实机另记录 `/camera/yolo/cones`、`/perception/camera/yolo/status`、ZED 图像/深度/
CameraInfo 和 `/zed/zed_node/pose`；用于诊断原始曝光、推理时延和建图位姿。

## 本地未上传内容

当前开发机存在未提交的 `config/simulator_defaults.yaml`、规则草稿和 perception_simulation
赛道草稿（包括 track4/track5/track6）。它们不属于 GitHub 交接基线，工控机 clone 后不会获得。
应先使用已提交的 `trackdrive.yaml`、`skidpad.yaml`、`acceleration.yaml`；若确实需要测试赛道，
请将其作为独立、可审查的赛道提交后再使用。
