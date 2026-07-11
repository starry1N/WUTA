# WUTA 开发指南

## 1. 环境与工作区

当前环境和脚本面向 Ubuntu 上的 ROS 2 Humble；Python 节点运行于 Python 3，C++ 节点由
ament/CMake 编译。仓库有两个 overlay：

```text
WUTA/
├── WUTA-FSD/ros2_ws/       # C++ FSD、消息包、待集成的 KISS-ICP/robot_localization 源码
├── WUTA-SIM/               # Python 仿真包、bringup、赛道、RViz
├── start_simulator.sh      # 推荐入口
└── docs/
```

每个 colcon 工作区的标准目录为 `src/`、`build/`、`install/`、`log/`；本仓库的
`WUTA-SIM` 使用 `--base-paths .`，所以 Python 包目录直接在该工作区中。

主要依赖由 package.xml 指定：ROS 消息包、PCL/PCL conversions、Eigen、yaml-cpp、tf2、
`numpy`、`PyYAML`。安装前先在目标系统执行 rosdep（如团队环境允许）：

```bash
source /opt/ros/humble/setup.bash
cd /home/starry1n/WUTA
rosdep install --from-paths WUTA-FSD/ros2_ws/src WUTA-SIM --ignore-src -r -y
```

## 2. 构建与启动

必须先构建并 source FSD overlay，后构建 simulator overlay：

```bash
source /opt/ros/humble/setup.bash
cd /home/starry1n/WUTA/WUTA-FSD/ros2_ws
./build_ws.sh
source install/setup.bash

cd ../../WUTA-SIM
colcon build --base-paths . --symlink-install --packages-up-to simulator_bringup
source install/setup.bash
```

根目录脚本封装了此顺序：

```bash
cd /home/starry1n/WUTA
./start_simulator.sh --rviz
```

`--skip-build` 只读取既有 install；修改 Python、launch、YAML 或 RViz 文件后先重建，
再使用 `--skip-build --rviz`。首次排障可使用 `--clean --rviz`。RViz 仅在传入 `--rviz`
时启动。

## 3. 开发工作流

1. 在所属 package 修改源码、launch 或 config；接口变更同时修改 `msg` 定义、调用方和
   `docs/ROS_INTERFACE.md`。
2. 按最小范围构建，例如：

   ```bash
   cd WUTA-SIM
   colcon build --packages-select lidar_sim simulator_bringup --symlink-install
   ```

3. source 两层 install 后运行对应 launch；不要让旧 ROS/RViz 进程混入测试。
4. 检查接口：`ros2 node list`、`ros2 topic list -t`、
   `ros2 topic info -v /sim/lidar/track_cones`。
5. 检查 TF：`ros2 run tf2_tools view_frames`，默认仿真必须有
   `map -> base_link -> lidar`。
6. 运行已有 LiDAR 核心测试：

   ```bash
   cd WUTA-SIM/perception_simulation
   python3 -m pytest tests/test_lidar_core.py -q
   ```

## 4. 配置与调试规则

- 配置文件位于各包 `config/`；赛道 YAML 位于
  `WUTA-SIM/perception_simulation/tracks/`；不要把生成的 `/tmp/wuta_*.yaml`/PCD 当作源码。
- `/sim/lidar/track_cones` 是 YAML 真值，`/mapping/cone_map_viz` 是 FSD 估计地图。调试时
  必须标明二者，不能替换接线。
- 不要把 KISS-ICP 源码或 EKF YAML 视为已接通的定位功能：INS 模拟器与 KISS-ICP + EKF
  集成均待实现；当前仿真定位源是 `simulation_bridge`。
- RViz 的 `MarkerArray` 使用真实 `Topic` 字段；看到
  `visualization_marker_array` 表示 RViz 回退到默认占位而非系统发布者。
- lidar-frame 数据必须与 TF 时间戳匹配；不要用无关的 wall-clock 时间覆盖传感器 stamp。

## 5. 代码与 Git 规范

- C++：遵循现有 rclcpp 风格，类放 `include/<package>/`，实现放 `src/`；使用
  `ament_target_dependencies` 声明依赖；提交前执行 `colcon build`。
- Python：4 空格、类型标注与现有 `rclpy` 生命周期结构；通过 `setup.py` 的
  `console_scripts` 暴露节点。
- ROS 命名：全局接口使用当前绝对名约定（如 `/planning/...`）；frame 名使用
  `map`、`base_link`、`lidar`，新增 frame 必须同时记录发布者。
- Git：一个提交只处理一个可审查目的；提交信息使用动词开头，例如
  `fix(rviz): restore marker topics`。不提交 `build/`、`install/`、`log/` 或临时地图。

## 6. 新 package 清单

新增 ROS package 前，至少提供 `package.xml`、CMakeLists/setup.py、可执行入口、launch 或
明确运行说明、config（若有参数）、测试和文档。若新增 topic/service/action，必须在合并前
更新架构图、接口表及部署检查命令。
