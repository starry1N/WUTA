# WUTA 部署与运行手册

## 1. 部署边界

当前仓库可直接部署的软件仿真闭环。INS 模拟器和 KISS-ICP + EKF 融合定位是待实现项。
真实车辆部署需要额外提供与配置一致的 LiDAR、CG-410/INS、CAN/VCU 驱动；这些驱动不在
当前源码中。不要把 simulator 的 `/sim/ground_truth` 或 `simulation_bridge` 当作实车定位源。

最低运行环境：Ubuntu + ROS 2 Humble、PCL、tf2、RViz2、Python `numpy`/`yaml`，以及
package.xml 声明的依赖。NDT/KISS 路径还需要 PCD 地图、Eigen 与对应定位组件。

## 2. Build

```bash
source /opt/ros/humble/setup.bash
cd /home/starry1n/WUTA
./start_simulator.sh --build-only
```

该脚本先调用 `WUTA-FSD/ros2_ws/build_ws.sh`，再使用
`colcon build --base-paths . --symlink-install --packages-up-to simulator_bringup` 构建
`WUTA-SIM`。手动构建时必须保持相同 source 顺序，详见 `DEVELOPMENT.md`。

## 3. Configuration

| 用途 | 实际文件 |
| --- | --- |
| 仿真 LiDAR | `WUTA-SIM/perception_simulation/config/lidar_simulator.yaml` |
| 赛道 | `WUTA-SIM/perception_simulation/tracks/{trackdrive,skidpad,acceleration}.yaml` |
| 感知/地图/规划/控制 | 各 FSD package 的 `config/*.yaml` |
| KISS-ICP（待实现集成） | `WUTA-FSD/ros2_ws/src/localization/kiss_icp_wrapper/config/kiss_icp_hesai128.yaml` |
| EKF（待实现集成） | `WUTA-FSD/ros2_ws/src/localization/localization_manager/config/ekf.yaml` |
| NDT/保存地图 | `WUTA-FSD/ros2_ws/src/localization/ndt_localization/config/ndt_localization.yaml` |
| RViz | `WUTA-SIM/simulator_bringup/rviz/wuta_simulator.rviz` |

部署前为真实硬件复核 frame、话题名、QoS、LiDAR 外参和 EKF 输入。NDT 默认地图路径为
`/tmp/wuta_lidar_map.pcd`；锥筒地图保存默认 `/tmp/wuta_cone_map.yaml`，应替换为有权限且
可追溯的持久化路径。

## 4. Launch

完整仿真并打开项目 RViz：

```bash
cd /home/starry1n/WUTA
./start_simulator.sh --rviz
```

仅使用已有构建：

```bash
./start_simulator.sh --skip-build --rviz
```

常见 launch 覆盖：

```bash
ros2 launch simulator_bringup simulator.launch.py \
  track_file:=skidpad mission_mode:=skidpad launch_rviz:=true
ros2 launch simulator_bringup simulator.launch.py launch_fsd:=false
```

第二条只启动仿真与 bridge，不启动 FSD 感知-控制链，因此 FSD Pipeline 可视化为空是预期行为。

## 5. Runtime Check

```bash
ros2 node list
ros2 topic list -t
ros2 topic info -v /sim/lidar/track_cones
ros2 topic echo --once /sim/lidar/track_cones
ros2 run tf2_tools view_frames
```

最小闭环应具备 `vehicle_model`、`lidar_simulator`、`can_simulator`、
`simulation_bridge` 与 `map -> base_link -> lidar`。完整默认链再包含
`lidar_detection_node`、`cone_map_builder`、`boundary_detector_node`、
`path_generator_node`、`controller_node`。

RViz Fixed Frame 设为 `map`。若 `Visible Cones` 报 transform 错误，检查
`/sim/ground_truth`、bridge 和 static `base_link -> lidar`；若 MarkerArray topic 显示为
`visualization_marker_array`，重新加载本仓库安装的 RViz 配置。

## 6. 真实硬件接入检查

1. 将 LiDAR 驱动输出与 `/hesai/pandar` 类型/时间戳/frame 对齐，或通过参数重映射；
2. 提供 `base_link -> lidar` 静态外参与完整定位 TF；
3. 提供 `/cg410/odometry` 后才启用当前 EKF 配置；
4. 审核 `map_saver` 的 TODO：其源码暂假定点云已在 map frame，不能未经修复直接用于
   多 frame 实车建图；
5. 验证紧急制动与 VCU/CAN：`mission_manager` 的 CAN 车检发送当前未实现，不能作为安全
   功能部署依据。
