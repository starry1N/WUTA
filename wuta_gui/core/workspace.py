"""工作空间路径助手 - 统一管理 GUI 对外部（FSD/SIM）的路径依赖

解耦原则：
- 唯一硬接口是 start_simulator.sh（构建/启动）
- 只读访问 SIM 赛道文件（供选择）
- 只读检查 FSD/SIM 构建产物（供构建状态提示）
- 运行时数据通过 ROS 话题（/system/*、/sim/*）通信
所有跨仓库路径集中在此文件，后续调整只需修改一处。
"""

from pathlib import Path

# FSD / SIM 构建产物（相对 wuta_root）
FSD_INSTALL_REL = "WUTA-FSD/ros2_ws/install/setup.bash"
SIM_INSTALL_REL = "WUTA-SIM/install/setup.bash"

# SIM 赛道目录（相对 wuta_root）
TRACKS_REL_DIR = "WUTA-SIM/perception_simulation/tracks"


def find_wuta_root() -> Path:
    """自动查找 WUTA 根目录（含 start_simulator.sh 的目录）"""
    current = Path.cwd()
    for _ in range(4):
        if (current / "start_simulator.sh").exists():
            return current
        current = current.parent
    return Path.cwd()


def find_start_script(wuta_root) -> Path:
    """查找 start_simulator.sh（wuta_root 下或其上层目录）"""
    script = Path(wuta_root) / "start_simulator.sh"
    if script.exists():
        return script
    current = Path(wuta_root)
    for _ in range(3):
        current = current.parent
        script = current / "start_simulator.sh"
        if script.exists():
            return script
    return Path(wuta_root) / "start_simulator.sh"


def tracks_dir(wuta_root) -> Path:
    """SIM 赛道文件目录"""
    return Path(wuta_root) / TRACKS_REL_DIR


def is_built(wuta_root) -> bool:
    """检查 FSD 与 SIM 是否已构建"""
    return (Path(wuta_root) / FSD_INSTALL_REL).exists() and (
        Path(wuta_root) / SIM_INSTALL_REL
    ).exists()


def setup_files(wuta_root) -> list:
    """ROS 环境 setup 文件（仅返回存在的）"""
    candidates = [
        "/opt/ros/humble/setup.bash",
        str(Path(wuta_root) / FSD_INSTALL_REL),
        str(Path(wuta_root) / SIM_INSTALL_REL),
    ]
    return [f for f in candidates if Path(f).is_file()]
