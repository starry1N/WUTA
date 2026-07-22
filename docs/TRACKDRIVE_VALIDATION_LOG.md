# Trackdrive 高速循迹验证与调整日志

日期：2026-07-22
环境：Ubuntu 22.04 / ROS 2 Humble / `<repo-root>`
验证模式：`use_ground_truth_localization:=true`，先绕过 INS/KISS-ICP/EKF，只验证感知、建图、规划、控制闭环。赛道 YAML 仅用于 LiDAR 仿真生成锥桶真值和离线误差评估，不作为 Trackdrive 规划输入。

## 验证命令

构建受影响包（示例路径用 `<repo-root>` 表示仓库根目录）：

```bash
cd <repo-root>/WUTA-FSD/ros2_ws
colcon build --base-paths . --symlink-install \
  --packages-select boundary_detector path_generator controller mission_manager

source install/setup.bash
cd <repo-root>/WUTA-SIM
colcon build --base-paths . --symlink-install \
  --packages-select simulator_bringup lidar_sim can_simulator
```

单张地图验证：

```bash
cd <repo-root>
./start_simulator.sh --skip-build \
  track_file:=trackdrive \
  mission_mode:=trackdrive \
  use_ground_truth_localization:=true \
  launch_rviz:=false

./start_simulator.sh --skip-build \
  track_file:=track_autocross_1784542421809 \
  mission_mode:=trackdrive \
  use_ground_truth_localization:=true \
  launch_rviz:=false
```

验证时将每次运行的 ROS 日志保存到运行机临时目录；日志分析使用连续中心线折线段距离，而不是“最近中心采样点距离”，避免锥桶间距导致直道误差虚高。

## 地图验证结果

| 地图 | 赛道规模 | 单圈结果 | 无前向目标 | 中心线拒绝 | Delaunay 兜底 | 横向误差 mean / p95 / max |
| --- | --- | --- | ---: | ---: | ---: | --- |
| `trackdrive.yaml` | 191 对蓝黄锥，约 463.3 m | 完成，66.400 s | 0 | 0 | 59 | 0.050 / 0.220 / 1.025 m |
| `track_autocross_1784542421809.yaml` | 265 对蓝黄锥，约 666.6 m | 完成，首圈 96.080 s，第二圈 96.500 s | 0 | 1 | 129 | 0.167 / 0.809 / 1.714 m |

结论：两张不同高速循迹地图均能完成闭环运行，没有再出现锥桶路径反向导致的掉头、绕圈或 `No forward waypoint target available` 停车。复杂图在急弯/过渡区域仍有一次较大的瞬时偏差，后续可通过曲率限速继续压低 max error。

## 外部赛道压力验证

外部地图来源：[iv461/fsd_racetrack_dataset](https://github.com/iv461/fsd_racetrack_dataset)。原始 `dataset/cone_map_*.yaml` 与 `dataset/boundaries_*.yaml` 转换为 WUTA 赛道 YAML 后保存到 `<repo-root>/external_validation_tracks/`。转换脚本只做坐标平移、起点对齐和蓝/黄边界方向统一；规划节点仍只消费在线 `/mapping/cone_map` 和 `/localization/pose`。

本轮补充下载并转换了 6-9 号赛道：

| 地图 | 赛道规模 | 结果 | 无前向目标 | 中心线拒绝 | Delaunay 兜底 | 横向误差 mean / p95 / max |
| --- | --- | --- | ---: | ---: | ---: | --- |
| `external_fsd_dataset_track_6.yaml` | 蓝 75、黄 74，约 237.9 m | 完成 | 0 | 0 | 21 | 0.981 / 3.155 / 4.719 m |
| `external_fsd_dataset_track_7.yaml` | 蓝 80、黄 79，约 224.7 m | 完成 | 0 | 1 | 18 | 0.263 / 0.834 / 1.869 m |
| `external_fsd_dataset_track_8.yaml` | 蓝 94、黄 93，约 231.0 m | 完成 | 0 | 2 | 8 | 2.036 / 6.758 / 7.469 m |
| `external_fsd_dataset_track_9.yaml` | 蓝 99、黄 97，约 309.4 m | 未完成；默认保守策略下进入局部循环 | 107 | 2 | 160 | 1.121 / 4.499 / 10.361 m |

补充观察：

- `track_7` 可视为通过效果较好的外部回归图。
- `track_6` 与 `track_8` 能闭环，但局部急弯或相邻赛段较近时仍会出现 3 m 以上瞬时偏差，需要继续优化中心线连续性和平滑。
- `track_9` 暴露出局部路径选择边界：把 `local_pairing_min_streak` 强行设为 `0` 可以跑完该图，但会导致 `track_6` 失败。因此默认保留为 `10`，避免局部几何兜底过早抢占原本可用的 Delaunay 路径。
- 当前结论不是“所有外部压力图全绿”，而是确认标准图和多张外部图能闭环，同时定位到剩余主要风险：紧凑/相邻赛段上的局部中心线分支选择。

## 已做调整与作用

| 模块 | 调整 | 作用 |
| --- | --- | --- |
| `boundary_detector` | 移除使用完整赛道 YAML/reference centerline 的方案 | 避免 Trackdrive “拿答案跑”；规划只消费 `/mapping/cone_map` 和 `/localization/pose` |
| `boundary_detector` | 蓝/黄锥在线配对作为主路径来源，Delaunay 作为兜底 | 充分利用当前建图颜色信息；颜色不足时仍可继续给控制器提供局部中心线 |
| `boundary_detector` | 按车辆航向过滤车后中心点，并修正局部路径反向 | 避免 Pure Pursuit 追向车后点，降低掉头概率 |
| `boundary_detector` | 新增基于车辆航向、候选点距离和蓝黄锥局部切向的连续性排序 | 避免相邻赛段很近时，中心线从当前赛段跳到错误分支 |
| `boundary_detector` | 新增局部车辆坐标系左右锥几何配对兜底，并由 `local_pairing_min_streak` 控制启用时机 | 在颜色配对长期不足时提供备用中心线；默认保守启用，避免误配抢走 Delaunay |
| `boundary_detector.yaml` | `lookahead_distance` 提高到 30 m | 高速 7 m/s 下让局部地图覆盖控制器前视距离，避免每帧只剩很少路径点 |
| `path_generator` | Trackdrive 中心线按 `trackdrive_resample_spacing=1.0 m` 重采样 | 稀疏中心线变成连续目标点，Pure Pursuit 不再只追末端点 |
| `path_generator` | Trackdrive 按局部路径曲率限制 waypoint 速度，参数为 `trackdrive_min_velocity` 与 `trackdrive_lateral_accel_limit` | 弯道目标速度可低于直道目标速度，降低紧弯高速过冲风险；不使用赛道 YAML 真值 |
| `controller` | Trackdrive 通用前视调为 `ld_ratio=1.2`、`max_lookahead=10.0 m` | 7 m/s 下前视约 8.4 m，减少局部路径过短时的切弯/跳点 |
| `controller` | 只选择车体前方目标；无前方目标时停车 | 防止瞬时反向路径引导车辆掉头绕圈 |
| `lidar_sim` | LiDAR FOV 调整为 360 deg | 更符合 Hesai 128 旋转激光雷达；侧后方锥桶可进入建图 |
| `lidar_sim` | 关闭简化遮挡模型 `enable_occlusion=false` | 原遮挡模型会把同侧远处锥桶成片挡掉，导致直道前方地图不足；关闭后感知地图更稳定 |
| `can_simulator` | logger 改为 f-string | 修复 Python logger 参数格式问题，减少运行期噪声 |
| 文档 | 更新 planning/controller/ROS interface 说明 | 对齐当前实现，明确 Trackdrive 不读取 YAML 中心线 |

## 当前边界

- 本日志验证的是真值定位调试模式，不代表 INS/KISS-ICP/EKF 全定位链已经通过。
- `Delaunay fallback` 次数仍较多，说明在线蓝黄锥配对在急弯和局部可见锥不足时还会依赖兜底。
- 复杂图 max error 仍超过 1 m，主要出现在急弯/过渡段；若要满足更严格评估，需要继续做更稳定的中心线分支选择、路径平滑和速度剖面联调。
