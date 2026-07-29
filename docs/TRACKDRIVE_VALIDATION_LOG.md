# Trackdrive 高速循迹验证与调整日志

日期：2026-07-22
环境：Ubuntu 22.04 / ROS 2 Humble / `<repo-root>`
验证模式：各节分别标注正常定位链或 `use_ground_truth_localization:=true`。赛道 YAML
用于 LiDAR 仿真生成锥桶真值、可选模拟相机颜色和离线误差评估，不作为 Trackdrive
中心线输入。

## 2026-07-29 track2 重复建图与无模拟颜色首圈停车复验

本轮使用默认正常定位链
`INS -> KISS-ICP -> EKF -> localization_manager`，保持
`use_track_truth_map:=false` 和 `use_ground_truth_localization:=false`。针对现场截图分别复现：

- 开启 `use_simulated_cone_colors` 时，闭环前会因定位修正产生并行重复轨迹；基线三次在
  闭环时才集中合并 11、5、3 条，说明截图中的在线堆叠确实存在。
- 关闭 `use_simulated_cone_colors` 时，原先按所有观测多数票分左右侧，两次闭图分别产生
  107、114 个错色锥桶；全局中心线仅覆盖约 10%，因此质量门槛正确拒绝进入 RACE。
- 改为最近观测后，常规运行可得到完整颜色拓扑；压力运行仍出现 16 个侧别错误，彩色配对
  只能形成 226 点、覆盖率 0.883、闭合误差 89.63 m，车辆会停在 `MAPPING_DONE`。

对应调整：

1. 保留 `merge_distance=0.5 m` 作为单帧关联半径，新增
   `consolidation_distance=1.0 m`，每个检测帧后传递式合并已收敛的兼容轨迹；发布阈值提高到
   `min_hit_count=3`。
2. 上游相机/融合颜色始终优先并投票；只有未知色才使用距离车辆最近的一次左右侧观测，避免
   远处相邻赛段的多帧观测主导颜色。
3. `cone_map_builder` 订阅正式 `/system/lap_count`，达到 `mapping_laps=1` 时冻结地图；
   原起点距离、累计里程与航向检测保留为几何兜底。
4. 闭图后的彩色配对若未通过原质量门槛，`boundary_detector` 仅从同一 ConeMap 估计局部
   边界切向，筛选近似垂直于两端切向的横跨赛道锥桶对，再执行相同排序、覆盖率和闭合距离
   验收。该兜底不读取赛道 YAML 或真值中心线。

将上述 16 错色的失败地图原样回放后，几何兜底生成 270 点中心线，覆盖率 1.000、闭合误差
1.21 m、置信度 0.962，并成功冻结。另以隔离 ROS 测试故意禁止几何回环，只发布
`/system/lap_count=1`，builder 日志明确为
`Loop closed! reason=formal lap count`，证明正式圈次闭图路径可独立工作。

最终两组完整三圈：

| 模拟颜色 | EXPLORE | RACE 2/3 | RACE 3/3 | 冻结地图 | 结果 |
| --- | ---: | ---: | ---: | --- | --- |
| `false` | 178.84 s | 76.51 s | 70.93 s | 531；错色 0；重复真值 0；1 m 内重叠 0 | `MAPPING_DONE -> RACE -> FINISH` |
| `true` | 137.78 s | 76.61 s | 71.00 s | 531；错色 0；重复真值 0；1 m 内重叠 0 | `MAPPING_DONE -> RACE -> FINISH` |

关闭/开启模拟颜色时，建图点到最近真值的 mean/p95/max 分别为
0.132/0.424/0.499 m 和 0.103/0.254/0.361 m。两轮分别在线消解 125、79 条重复轨迹，
最终均冻结 266 点常规彩色中心线，第三圈后进入 `FINISH`。赛道 YAML 只在运行结束后用于
离线计数、错色和距离核对；运行中的地图、闭环与中心线均来自在线链路。

2026-07-30 又用最终构建补跑三次独立首圈；两次开启模拟颜色，一次关闭模拟颜色：

| 模拟颜色 | 闭图触发 | EXPLORE | 在线消解 | 冻结地图 | 中心线 | 结果 |
| --- | --- | ---: | ---: | --- | --- | --- |
| `true` | 正式圈次 | 196.32 s | 13 | 531；重复真值 0；1 m 内重叠 0 | 266 点；0.922 | 进入 `RACE` |
| `true` | 几何回环 | 194.50 s | 3 | 531；重复真值 0；1 m 内重叠 0 | 266 点；0.923 | 进入 `RACE` |
| `false` | 几何回环 | 202.65 s | 10 | 531；错色 0；重复真值 0；1 m 内重叠 0 | 266 点；0.923 | 进入 `RACE` |

三次建图点到最近真值的 mean/p95/max 分别为
0.034/0.068/0.154 m、0.036/0.080/0.115 m 和 0.028/0.057/0.080 m。
两条闭图触发路径均在最终构建上实际通过；关闭模拟颜色的复跑也没有停在
`MAPPING_DONE`。这三次常规彩色中心线均直接通过质量门槛；几何中心线兜底仍由前述
16 错色失败地图的原样回放覆盖。

本轮按既定范围不处理 track10/11 的紧邻赛段分支选择问题。

## 2026-07-29 track2 默认配置全链路验收

本轮从 GitHub 最新父仓库和 FSD 子模块开始，在虚拟机正式目录使用
`config/simulator_defaults.yaml` 启动。定位保持
`use_ground_truth_localization:=false`，实际运行 INS、KISS-ICP、EKF 和
`localization_manager`；感知与建图保持
`lidar_detection -> simulated_cone_colorizer -> cone_map_builder`，未启用
`use_track_truth_map`。

密集赛道使用 50 m 量程执行逐锥遮挡时，单帧耗时可超过 4 s，后半圈会使点云时间戳
落后并被颜色注入节点拒绝；完全关闭遮挡则会放入过多紧邻赛段锥桶，75 s 内地图膨胀到
630 个并出现 69 组 0.5 m 内近重复。最终默认保留
`lidar_enable_occlusion:=true`，把 `lidar_max_range:=20.0` 与下游检测距离对齐。

首圈闭环后地图为蓝 265、黄 266，共 531 个锥桶，与 track2 真值总数一致；闭环归并后
0.5 m 内近重复为 0。建图点到同色最近真值的 mean/p95/max 为
0.041/0.081/0.123 m，没有误差超过 0.5 m 的锥桶。`boundary_detector` 从闭环 ConeMap
生成并冻结 266 点有序全局中心线，置信度 0.895，随后状态立即从
`EXPLORE -> MAPPING_DONE -> RACE`。

| 正式圈次 | 阶段 | 用时 | 距离 | 结果 |
| ---: | --- | ---: | ---: | --- |
| 1/3 | EXPLORE | 210.40 s | 900.7 m | 在线地图闭环，五项 RACE 门槛通过 |
| 2/3 | RACE | 78.79 s | 722.5 m | 冻结中心线竞速，最高车速达到 10 m/s |
| 3/3 | RACE | 72.21 s | 711.4 m | `lap_count=3`，`RACE -> FINISH` |

停车补测先向车辆模型发送 10 m/s，再发布 `MissionState.FINISH`；控制器最后命令和
`/sim/ground_truth` 线速度均变为 0.000 m/s。由此完整验证了首圈在线建图、闭环切换、
两圈竞速和第三圈后停车。

## 2026-07-28 正常定位全模拟器验收

本轮在独立干净验收副本中使用 `use_ground_truth_localization:=false`，实际启动
`ins_simulator`、KISS-ICP、EKF 和 `localization_manager`。默认配置也改为该模式；
`simulation_bridge` 仅保留真值计时，在关闭真值定位时不创建 `/localization/pose`
发布器或真值 TF broadcaster。运行中 `/localization/pose` 只有
`localization_manager` 一个发布端点。

标准 `trackdrive.yaml` 使用真值 ConeMap 快捷输入完成三圈，圈时为
79.85 / 52.25 / 47.15 s，状态完整经过
`EXPLORE → MAPPING_DONE → RACE → FINISH`，第三圈后控制指令为零。连续 8 s
定位抽样中，INS 平面误差 mean/p95/max 为 0.063/0.128/0.166 m，EKF 为
0.189/1.084/1.580 m；EKF 偶有 update-rate warning，但没有阻断状态机。

Track2 使用在线链路
`lidar_detection → simulated_cone_colorizer → cone_map_builder`。闭环前内部地图一度
存在 10 条已收敛到 `merge_distance=0.5 m` 内的重复轨迹；闭环最终合并后内部地图
为 531 个锥桶，与真值总数一致。发布/保存的确认地图为蓝 265、黄 264，0.5 m 内重复
对为 0，颜色错误为 0；建图点到同色最近真值的 mean/p95/max 为
0.049/0.121/0.183 m。两个真值点因命中次数不足未进入确认地图。

| 正式圈次 | 阶段 | 用时 | 结果 |
| ---: | --- | ---: | --- |
| 1/3 | EXPLORE | 216.66 s | 在线建图闭合，合并 10 条重复轨迹，五项 RACE 门槛通过 |
| 2/3 | RACE | 77.30 s | 使用冻结全局中心线完成 |
| 3/3 | RACE | 71.64 s | `lap_count=3`，进入 `FINISH` 并停车 |

其它赛事模式同样使用正常定位链回归：

- Acceleration：0–75 m 为 5.116 s，在停止区末端进入 `FINISH`；最终真值
  `x=175.804 m`、速度 0，控制指令为零。
- Skidpad：入口计时 5.242 s，四圈分别为
  11.536 / 11.641 / 11.583 / 11.579 s；车辆进入 25 m 出口终点容差后发布
  `/system/mission_complete`，最终状态和控制指令均为停车。
- `WUTA-SIM` 全包测试汇总为 10 tests、0 failures、0 errors、2 skipped。

剩余风险：完整 FSD 测试中 vendored `robot_localization` 的 EKF/UKF interface launch
tests 失败；EKF 在独立 ROS domain 重跑后 10 项通过 7 项，失败项为
`PoseBasicIO`、`TwistBasicIO` 和 `ImuDifferentialIO`。实际赛事链路全部完成，但该第三方
测试失败仍需后续单独处理。Track2 第一圈局部中心线较短时会多次降到 3 m/s，并出现短暂停车
后自恢复；mission_manager 直接积分高频融合位姿也会高估圈距，因此当前圈距只作诊断，
正式完成条件以有限起终线穿越和圈次为准。

## 2026-07-28 track2 在线建图与模拟颜色验收

用户实际 `track2.yaml` 为 265 个蓝锥、266 个黄锥、约 667 m 的 autocross 赛道。先以
`use_track_truth_map:=true` 回归现有快捷模式，三圈均完成，证明当前版本不会在首圈结束后
停在 `MAPPING_DONE`。随后使用以下参数验收新模拟颜色链路：

```bash
./start_simulator.sh --skip-build \
  track_file:=/path/to/track2.yaml \
  mission_mode:=trackdrive \
  use_track_truth_map:=false \
  use_simulated_cone_colors:=true \
  use_ground_truth_localization:=true \
  launch_rviz:=false
```

该运行保留 `lidar_detection` 与 `cone_map_builder`，YAML 只用于给当前检测补颜色。颜色匹配
日志持续为 100%；builder 首圈闭合时内部地图为 531 个锥桶，发布的确认地图为蓝 265、
黄 265、未知 0，通过地图质量门槛；`boundary_detector` 从该闭环地图冻结 266 点全局
中心线，置信度 0.904。与 531 个 YAML 真值锥桶逐点核对后，确认地图漏检 1 个、重复匹配
0 个；建图点到最近真值的平均/最大距离为 0.009/0.032 m，任意两建图点最小间距
1.506 m，`0.5 m` 内重叠对为 0。因此未出现单锥重复堆叠或地图数量膨胀。

| 正式圈次 | 阶段 | 用时 | 距离 | 结果 |
| ---: | --- | ---: | ---: | --- |
| 1/3 | EXPLORE | 181.39 s | 668.5 m | 在线地图闭合，五项 RACE 门槛通过 |
| 2/3 | RACE | 76.47 s | 667.1 m | 使用冻结全局中心线完成 |
| 3/3 | RACE | 71.85 s | 667.2 m | 完成后 `RACE → FINISH` |

首圈后没有状态机停车；最终 `/control/command` 为 `speed=0.0`、`angle=0.0`、
`dv_state=4`。但首圈约 110 秒处局部中心线曾短暂断供，控制器先以 2 m/s 保持再停车，
之后重新获得目标并自行恢复。该现象未阻止闭环，仍应作为在线局部规划的剩余风险保留，
不能把本轮结论表述为“首圈全程无停车”。

## 2026-07-27 三圈竞速状态机验收

本轮使用 `use_track_truth_map:=true` 模拟相机向 ConeMap 提供正确锥桶颜色；YAML 未向规划提供
中心线。第一圈结束后 ConeMap 闭环，`boundary_detector` 从 191 对蓝黄锥生成并冻结 191 点
全局中心线，置信度 0.973。地图闭合、地图质量、定位、全局中心线和首圈五项门槛全部通过后，
状态按 `IDLE → READY → EXPLORE → MAPPING_DONE → RACE → FINISH` 运行。

| 正式圈次 | 阶段 | 用时 | 距离 | 速度策略 |
| ---: | --- | ---: | ---: | --- |
| 1/3 | EXPLORE | 78.16 s | 464.4 m | 7 m/s 上限，曲率限速；实际大部分约 6 m/s |
| 2/3 | RACE | 52.39 s | 464.4 m | 9 m/s 上限，曲率/置信度/前视距离联合限速 |
| 3/3 | RACE | 46.99 s | 464.4 m | 10 m/s 上限，曲率/置信度/前视距离联合限速 |

补充降级验收中，以 100 Hz 注入 `localization_confidence=0.0` 后，控制器目标和实际命令均从
约 6.4 m/s 平滑降至 3.0 m/s；停止注入后恢复正常曲率速度，证明定位质量下降不会继续无条件高速。

仿真真值计时连续报告 1/3、2/3、3/3，与正式定位圈次一致；`MAPPING_DONE` 未造成计时归零。
冻结后的首个控制帧只接收 36 个局部前视点，没有将整圈 191 点直接送入控制器。第三圈后
`MissionState.state=6`、`description=lap=3`，车辆真值线速度和角速度均为 0。完整日志保存为
`run2-final.log`（验收机外部工件，不入库）。

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
| `controller` | Trackdrive 固定 `trackdrive_lookahead=5.0 m`，并使用前视目标点的速度 | 局部中心线每次刷新都会从车辆起点重新计数；读取前视点速度可将曲率限速带入弯道，避免起点速度恒为 7 m/s |
| `controller` | 只选择车体前方目标；无前方目标时停车 | 防止瞬时反向路径引导车辆掉头绕圈 |
| `simulator_bringup` | Trackdrive LiDAR 请求 `fov_deg=360` | 扩大默认前向可见窗口，避免 120 deg 配置在急弯只剩单侧边界 |
| `simulator_bringup` | 保留遮挡并将 `max_range` 限为 20 m | 与检测器有效量程一致，避免 50 m 全图遮挡计算拖旧时间戳，同时过滤紧邻赛段的被遮挡锥桶 |
| `can_simulator` | logger 改为 f-string | 修复 Python logger 参数格式问题，减少运行期噪声 |
| 文档 | 更新 planning/controller/ROS interface 说明 | 对齐当前实现，明确 Trackdrive 不读取 YAML 中心线 |

## 当前边界

- 本日志验证的是真值定位调试模式，不代表 INS/KISS-ICP/EKF 全定位链已经通过。
- `Delaunay fallback` 次数仍较多，说明在线蓝黄锥配对在急弯和局部可见锥不足时还会依赖兜底。
- 复杂图 max error 仍超过 1 m，主要出现在急弯/过渡段；若要满足更严格评估，需要继续做更稳定的中心线分支选择、路径平滑和速度剖面联调。
