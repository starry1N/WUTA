# Repository Guidelines

## Project Structure & Module Organization

WUTA is a ROS 2 Humble workspace composed from Git submodules. `WUTA-FSD/ros2_ws/` contains the C++ FSD stack (16 packages): `common/` (`wuta_msgs`, `autoware_msgs`, `wuta_tools`), `control/` (`controller`), `localization/` (`localization_manager`, `ndt_localization`, `kiss_icp_wrapper`, `robot_localization`、递归子模块 `kiss-icp`), `mapping/` (`cone_map_builder`), `perception/` (`lidar_detection`, `camera_detection`, `detection_fusion`), `planning/` (`path_generator`, `boundary_detector`), `system/` (`mission_manager`, `can_interface` — 实车 CAN 预留目录，无 package.xml，当前不参与构建). `WUTA-SIM/` contains Python simulators: `perception_simulation`, `vehicle_model`, `can_simulator`, `wuta-ins-simulator` (submodules) and `simulator_bringup` (main-repo directory). Track definitions live in `WUTA-SIM/perception_simulation/tracks/`. `wuta_gui/` is a PyQt5 control panel (main-repo directory) for build/params/launch/status/timing. Shared technical documentation is under `docs/` (`ROS_INTERFACE.md`, `ARCHITECTURE.md`, `DEVELOPMENT.md`, `DEPLOYMENT.md`); `start_simulator.sh` reads its build/launch defaults from `config/simulator_defaults.yaml`. Initialize all dependencies before building:

```bash
git submodule update --init --recursive
```

Submodule branches: `WUTA-FSD` on `小登测试`, the four WUTA-SIM simulators on `main`. Make changes inside the owning submodule; the top-level repository records submodule commit pointers. Main-repo directories (`simulator_bringup`, `wuta_gui`, `docs/`, `config/`) commit directly to the top-level repository.

## Build, Test, and Development Commands

Build FSD first, then the simulator overlay:

```bash
cd WUTA-FSD/ros2_ws && ./build_ws.sh          # 校验并构建全部 16 个包
source install/setup.bash
cd ../../WUTA-SIM
colcon build --base-paths . --symlink-install --packages-up-to simulator_bringup
```

From the repository root, `./start_simulator.sh` builds and starts the default system. Useful options: `--rviz` (open RViz2), `--skip-build` (use existing install spaces), `--clean` (clean rebuild), `--build-only` (build without launching), `--lightweight` (single-thread build for ≤8GB RAM), `--config PATH` (load build/launch defaults from YAML), `--params-file PATH` (inject node parameters at launch). Launch the PyQt5 control panel with `python3 -m wuta_gui` from the repo root. For focused LiDAR tests, run `python3 -m pytest tests/test_lidar_core.py -q` from `WUTA-SIM/perception_simulation`; `WUTA-SIM/simulator_bringup/test` also has pytest suites. Inspect runtime wiring with `ros2 node list`, `ros2 topic list -t`, and `ros2 run tf2_tools view_frames`.

## Coding Style & Naming Conventions

Use existing ROS 2 conventions: C++17 with `rclcpp`, four-space Python indentation with `rclpy`, and package-local launch/config files. Use `snake_case` for Python files, ROS parameters, topics, and frame names; use `PascalCase` for C++ classes. Keep global topics absolute (for example, `/localization/pose`) and document every new topic, service, action, or frame in `docs/ROS_INTERFACE.md`. The `wuta_gui` panel follows the same conventions (PyQt5, snake_case files, all colors/fonts centralized in `ui/theme.py`).

## Testing Guidelines

Build the smallest affected package set before broad builds. Test new behavior through its actual ROS interface, including message type, frame, timestamp, and QoS where relevant. Do not commit generated `build/`, `install/`, `log/`, `__pycache__/`, root `logs/`, temporary maps, RViz user state, or GUI state (`.wuta_gui_state.json`).

## Commit & Pull Request Guidelines

History contains mixed messages; use clear imperative Conventional Commit-style subjects for new work, such as `fix(localization): publish a single EKF TF`. Commit submodule changes inside their own repository first, then commit the updated top-level pointer. PRs should state scope, test commands/results, configuration changes, and include RViz screenshots when visual output changes. Link related issues and call out interface or TF changes explicitly.
