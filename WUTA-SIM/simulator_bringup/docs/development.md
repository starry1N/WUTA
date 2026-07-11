# Simulator Bringup 开发记录

## RViz 真值地图配置

默认 RViz 配置为 `rviz/wuta_simulator.rviz`，安装后路径为：

```text
install/simulator_bringup/share/simulator_bringup/rviz/wuta_simulator.rviz
```

`MarkerArray` 显示必须使用 RViz 的 `Topic` 配置字段，并指向真实 ROS 话题。
若该字段缺失或写成无法被当前 RViz 读取的字段，RViz 会保存默认占位话题
`visualization_marker_array`。该话题不是本项目任何节点发布的内容；出现它表示
该显示没有订阅到预期话题。

| RViz 显示名称 | 正确话题 | 发布者 |
| --- | --- | --- |
| `Visible Cones` | `/sim/lidar/visible_cones` | `lidar_simulator` |
| `Loaded Track Cones (YAML Ground Truth)` | `/sim/lidar/track_cones` | `lidar_simulator` |
| `Perception Cones` | `/perception/lidar/cones_viz` | `lidar_detection_node` |
| `Cone Map` | `/mapping/cone_map_viz` | `cone_map_builder` |
| `Centerline` | `/planning/centerline_viz` | `boundary_detector_node` |
| `Control Target` | `/control/target_viz` | `controller_node` |

`Loaded Track Cones (YAML Ground Truth)` 使用 `Reliable + Transient Local`，并显式
启用 `track_cones` 与 `track_cone_info` 命名空间。RViz 的 Fixed Frame 必须为 `map`。

注意：FSD Pipeline 下的四项可视化仅在相应算法节点启动且产生数据后才会显示；
它们为空不代表 simulator 真值地图有问题。

## README 自动启动脚本

仓库根目录的 `start_simulator.sh` 是 README 推荐入口。它按如下顺序处理 overlay：

```text
WUTA-FSD/ros2_ws/install/setup.bash
-> WUTA-SIM/install/setup.bash
-> ros2 launch simulator_bringup simulator.launch.py
```

默认不会启动 RViz。必须传入 `--rviz`，脚本才会追加 `launch_rviz:=true` 并加载上述
默认配置：

```bash
cd /home/starry1n/WUTA
./start_simulator.sh --rviz
```

`--skip-build` 只使用已有 install 空间；修改 Python 节点、launch 或 `.rviz` 后，
若未重新构建，仍会加载旧版安装文件。首次验证修改时使用：

```bash
./start_simulator.sh --clean --rviz
```

之后可使用：

```bash
./start_simulator.sh --skip-build --rviz
```

应先完全关闭旧的 ROS/RViz 进程，再启动新实例，避免手工打开的旧 RViz 配置或不同
ROS 环境导致话题看似缺失。

## 配置检查

构建 `simulator_bringup` 后，可确认安装配置不含 RViz 默认占位话题：

```bash
cd /home/starry1n/WUTA/WUTA-SIM
colcon build --packages-select simulator_bringup --symlink-install
rg 'visualization_marker_array' \
  install/simulator_bringup/share/simulator_bringup/rviz/wuta_simulator.rviz
```

最后一条命令不应有输出。

