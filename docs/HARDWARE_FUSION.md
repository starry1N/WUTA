# 工控机实机感知与可视化

从仓库根目录启动：

```bash
# 查看已经运行的实机链路，同时新开终端显示 YOLO 图像，不再启动设备
./start_simulator.sh --hardware --view-only

# 停止旧链路后，使用新配置启动真实设备 + YOLO + 后融合 + 建图 + RViz
./start_simulator.sh --hardware --skip-build --rviz

# 等价的独立实机入口
./start_hardware_fusion.sh --skip-build --rviz
./start_fusion_simulator.sh --hardware --skip-build --rviz

# 首次部署构建，不启动设备
./start_hardware_fusion.sh --build-only --lightweight

# 列出全部 launch 参数，不启动设备
./start_simulator.sh --hardware --show-args
```

普通 `start_simulator.sh` / `start_fusion_simulator.sh` 仍启动合成传感器；
`--hardware` 在读取仿真默认配置之前转到独立实机入口，不继承赛道、真值地图和车辆控制。
三个启动入口在实际启动前都会先停止上一套 WUTA launch 及其子进程。实机入口随后检查
M1 UDP 6699/7788 端口；若端口仍由 WUTA launch 之外的进程占用，则拒绝重复启动。
`--no-drivers` 仅适用于外部已经提供单一、正确时基的驱动对，仍会启动感知与建图节点；
若整条链路已在运行，应使用 `--view-only`。

实机参数示例：

```bash
./start_hardware_fusion.sh --skip-build --rviz \
  --model WUTA-FSD/ros2_ws/src/perception/camera_detection/models/best.pt \
  --calibration WUTA-FSD/ros2_ws/src/perception/calibration/camera_lidar.yaml \
  confidence_threshold:=0.25 inference_threads:=4 fusion_wait_sec:=1.2 \
  publish_annotated_image:=true publish_unmatched_lidar:=false red_color:=3
```

`--no-rviz` 禁用窗口；`--rviz-config PATH` 选择其他 RViz 配置。
脚本在打开 RViz 时默认通过 gnome-terminal 新开图像终端，显示
`/camera/yolo/image_annotated`。`--no-image-view` 禁用独立图像窗口，
`--image-view` 可在不启动 RViz 时启用，`--image-view-topic /topic` 改为其他图像话题。
也可手动在新终端运行 `bash view_yolo_image.sh`，或传入
`/zed/zed_node/rgb/image_rect_color` 查看原图。
路径参数相对于调用时的当前目录解析，默认模型/外参/显示配置相对于仓库根目录。
还可覆盖 `image_topic`、`lidar_topic`、`depth_topic`、`info_topic`、
`localization_pose_topic`。改变驱动输入话题后，需同步调整 RViz 配置中的话题。
普通融合仿真也支持 `rviz_config:=/absolute/path/to/file.rviz` 与 `--no-rviz`。

## 实机 RViz 显示

配置位于 FSD 的 `detection_fusion/config/hardware.rviz`，默认固定帧为 `map`：

| 显示 | 话题 | 默认状态 |
| --- | --- | --- |
| M1 Live PointCloud | `/rslidar_points` | 开启 |
| Fused Cone Map | `/mapping/cone_map_viz` | 开启；须先有有效位姿和建图数据 |

RViz 仅保留上述点云与锥桶地图两项；YOLO 图像通过独立 rqt_image_view 窗口显示。
实机和融合仿真配置均采用 Orbit 三维视角，默认工具为 MoveCamera：
鼠标左键拖动旋转，中键拖动平移，滚轮缩放；Shift + 左键可平移。
若当前启用了其他交互工具，按 M 或点击工具栏 Move Camera 后拖动。

图像和点云均用 Best Effort/Volatile；绘框图像保留曝光时间和原图分辨率，
刷新频率由 GPU 推理速度决定。没有检测时仍显示无框画面。
点云通过实时 `map <- rslidar` TF 显示；若点云提示变换错误，应检查 ZED 定位 TF 的时间覆盖范围。

## 今日开发记录与验收边界（2026-09-15）

### 已完成

- 实机入口已接通 ZED 2i、RoboSense M1、相机检测、雷达检测、后融合、
  cone_map_builder 和 RViz。当前运行图中 M1 点云只有一个发布者，算法输入为
  `/rslidar_points` 的真实点云，不再使用仿真点云。
- 默认权重切换为 `camera_detection/models/best.pt`。YOLO 使用原生 PyTorch CUDA，
  运行状态为 `pytorch` / `PyTorch:cuda:0`；仍可显式传入 ONNX 权重。模型类别
  `red/yellow/blue` 映射为橙/黄/蓝，其中 `red` 按项目数据语义映射为橙色锥桶。
- YOLO 输出保留 ZED 曝光 header 和 1280x720 原图坐标，叠框图像发布到
  `/camera/yolo/image_annotated`。启动 RViz 时默认另开 rqt_image_view 窗口显示图像。
- M1 地面 RANSAC 增加地面法向约束，法向与雷达 Z 轴夹角最多 5°，避免室内墙面
  被当作地面；迭代上限提高到 500。
- 实机融合默认 `publish_unmatched_lidar=false`，只有与相机框关联成功的雷达目标
  才进入融合输出和地图。相机框未命中传统雷达聚类时，新增框引导原始点云路径：
  从同一帧 `/rslidar_points` 投影裁剪框内点，按 ZED 深度前后 0.4 m 分层，再进行
  0.05 m 体素化、0.15 m 三维连通聚类和锥桶尺寸检查。该路径仍要求存在真实点簇。
- RViz 实机配置只显示 M1 原始点云和 `/mapping/cone_map_viz` 锥桶地图，使用 Orbit
  三维视角；YOLO 图像不占用 RViz 面板。
- 普通仿真、后融合仿真和实机融合三个入口已共用启动前清理：先向旧 WUTA launch
  发送 SIGINT，超时后使用 SIGTERM/SIGKILL，并等待旧包装脚本完全退出。
  `--build-only`、`--show-args`、`--view-only` 不触发清理。
- 已构建 `wuta_msgs`、`camera_detection`、`lidar_detection`、`detection_fusion`、
  `cone_map_builder`。相机模型、标定、关联和框引导聚类的现有自动测试均已通过。

### 现场复测

固定锥桶场景连续观察 20 秒得到：

| 项目 | 结果 |
| --- | ---: |
| ZED 原图 / 深度 | 251 / 247 帧 |
| M1 原始点云 / 雷达聚类 | 193 / 129 帧 |
| YOLO 框 / 双目适配输出 | 32 / 32 帧 |
| 融合状态 | 128 帧 |
| `fused` / `camera_timeout` | 17 / 111 帧 |
| 匹配 / 框引导聚类 / 发布目标 | 16 / 16 / 16 个 |
| 已赋语义颜色 | 15 个 |
| 被过滤的未匹配雷达聚类 | 633 个 |

抽样 YOLO 蓝色检测的蓝色概率为 `0.60698`，双目位置有效；融合输出实际观察到
`color: 1`（BLUE）、置信度 `0.62062` 的锥桶。因此相机类别映射和单帧融合着色已经
生效。该次采样末尾地图仍有 2 个 `unknown_cones`，尚无 `blue_cones`。

图像蓝框、单帧蓝色融合目标和地图蓝色属于三层不同判定：

1. 叠框图像用最大类别分数选择边框颜色，只表达该次 YOLO 分类结果。
2. 融合节点只有在雷达目标与相机框关联成功，且归一化颜色概率不低于 `0.6` 时，
   才把该帧锥桶设为 BLUE；否则保持 UNKNOWN。
3. 地图对同一空间轨迹至少需要 3 次语义颜色支持，且领先颜色占有效颜色票数至少
   70%，才从白色 UNKNOWN 改为蓝色。未达到确认次数、观测关联到不同轨迹，或大量
   雷达帧发生 `camera_timeout` 时，地图会继续显示白色。

当前白色标记位于建图确认层。20 秒内 111/128 个雷达融合周期没有取得 60 ms 内的
相机检测，语义观测较稀疏；同时需要继续检查框引导聚类位置抖动是否超过 builder 的
0.5 m 合并距离。不能仅凭图像出现蓝框判断地图已经取得三次同轨迹蓝色票。

### 剩余工作

- 提高相机检测有效吞吐并优化雷达/相机时间关联，降低 `camera_timeout` 占比；评估
  60 ms 同步窗口和“每个相机帧最多使用一次”的策略是否适合当前 M1/ZED 频率。
- 为 cone_map_builder 增加每条轨迹的颜色票数与关联距离诊断，确认蓝色观测是否
  稳定落入同一 0.5 m 轨迹，并完成 UNKNOWN 到 BLUE 的现场闭环验收。
- 分别用蓝、黄、橙实物锥桶检查检测框、有效深度、投影对齐、matches/colored、
  框引导聚类和最终地图颜色，多锥遮挡场景需单独测试。
- 完成运动状态下硬件统一时基、M1 扫描去畸变和外参重投影精度验收；测试相机掉线、
  深度失效和 TF 中断。
- 车辆部署还需要车辆 `base_link` 外参、INS/EKF 单一 TF 发布源和车辆控制验收。
  共同位置参考点和误差模型通过验收前，实机位置融合保持关闭。

原始标定填在 `perception/calibration/camera_lidar.example.yaml`，运行配置
`camera_lidar.yaml` 使用相同矩阵。权重、运行外参、build/install/log、
独立 Python 依赖均不提交；代码尚未提交或推送。
