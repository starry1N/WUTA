"""WUTA 仿真控制面板 - 入口文件

使用方法:
    python -m wuta_gui
    或
    python -m wuta_gui --wuta-root /path/to/wuta
"""

# 禁止生成 __pycache__，避免修改代码后缓存不生效
import sys
import os
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'

import argparse
import subprocess
from pathlib import Path

from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtGui import QFont, QFontDatabase

from wuta_gui.core import workspace
from wuta_gui.ui import theme


def restart_with_ros_environment(wuta_root: Path, reason: str = "") -> bool:
    """在当前进程中 source 完整 ROS 环境后重新执行 GUI。

    阻塞至新 GUI 进程退出；成功重启后当前进程退出，不会返回。
    仅在 FSD 已构建（install/setup.bash 存在）时执行，
    否则直接返回 False，调用方继续运行。
    """
    # wuta_msgs 来自 FSD 的 install；若 FSD 尚未构建，
    # 任何 setup 文件都无法提供它，重启也无济于事
    fsd_setup = Path(wuta_root) / workspace.FSD_INSTALL_REL
    if not fsd_setup.is_file():
        return False

    # 需要 source 的 setup 文件（仅存在的）
    existing_setup = workspace.setup_files(wuta_root)
    if not existing_setup:
        return False

    # 构造重新执行命令：source 所有 setup 后，用同一个 Python 重新运行
    source_cmds = " && ".join(f'source "{s}"' for s in existing_setup)
    # 使用当前 Python 解释器重新执行，传递原始参数
    gui_args = " ".join(sys.argv[1:])
    # WUTA_GUI_ENV_CHECKED 标记已重启过，防止无限循环
    rerun_cmd = (
        f'export WUTA_GUI_ENV_CHECKED=1 && {source_cmds} '
        f'&& exec "{sys.executable}" -m wuta_gui {gui_args}'
    )

    if reason:
        print(f"[GUI] {reason}")
    print(f"[GUI] Running: {rerun_cmd}")

    # 用 exec 替换当前进程（如果 bash 支持的话），否则用 subprocess
    result = subprocess.run(
        ["bash", "-c", rerun_cmd],
        cwd=str(wuta_root),
    )
    # 新进程已启动，退出当前进程
    sys.exit(result.returncode)
    return True  # 不可达，仅为类型提示


def _ensure_ros_environment(wuta_root: Path) -> None:
    """确保 ROS 环境已正确 source。

    如果 wuta_msgs 无法导入，说明当前进程环境不完整。
    此时自动重新执行自身（先 source 所有 setup 文件），
    确保新进程拥有完整环境。
    若 FSD 尚未构建（如全新 clone）或重启后仍无法导入，
    则直接以无 ROS 模式启动，避免无限重启循环。
    """
    # 已 source 过（或首次启动就能导入），直接返回
    try:
        import wuta_msgs  # noqa: F401
        return
    except ImportError:
        pass

    # 防循环：已经重启过一次仍无法导入，说明环境确实不完整，
    # 继续重启无意义，直接以无 ROS 模式启动
    if os.environ.get("WUTA_GUI_ENV_CHECKED"):
        print("[GUI] Running without ROS topics (workspace not fully built).")
        return

    # wuta_msgs 来自 FSD 的 install；若 FSD 尚未构建，重启也无济于事
    fsd_setup = Path(wuta_root) / workspace.FSD_INSTALL_REL
    if not fsd_setup.is_file():
        print("[GUI] FSD workspace not built yet, running without ROS topics.")
        return

    # source 完整环境后重启自身
    restart_with_ros_environment(wuta_root)


def check_dependencies():
    """检查必要的依赖（仅检查 PyQt5 和 yaml，不检查 ROS）"""
    missing = []

    try:
        import PyQt5
    except ImportError:
        missing.append("PyQt5")

    try:
        import yaml
    except ImportError:
        missing.append("pyyaml")

    return missing


def find_wuta_root() -> Path:
    """自动查找 WUTA 根目录"""
    return workspace.find_wuta_root()


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="WUTA 仿真控制面板")
    parser.add_argument(
        "--wuta-root",
        type=str,
        default=None,
        help="WUTA 项目根目录路径（自动检测）"
    )
    return parser.parse_args()


def _pick_font(size: int = 14) -> QFont:
    """选择可用字体，优先中文字体以避免 Linux 下乱码"""
    preferred = [
        "Noto Sans CJK SC",
        "WenQuanYi Micro Hei",
        "WenQuanYi Zen Hei",
        "Droid Sans Fallback",
        "Source Han Sans SC",
    ]
    db = QFontDatabase()
    available = db.families()
    for name in preferred:
        if name in available:
            return QFont(name, size)
    return QFont("Sans Serif", size)


def main():
    """主函数"""
    # 解析参数
    args = parse_arguments()

    # 确定 WUTA 根目录
    if args.wuta_root:
        wuta_root = Path(args.wuta_root).resolve()
    else:
        wuta_root = find_wuta_root()

    # 检查 WUTA 根目录是否存在
    if not wuta_root.exists():
        print(f"错误: WUTA 根目录不存在: {wuta_root}")
        sys.exit(1)

    # 确保 ROS 环境已 source（必要时重启自身）
    _ensure_ros_environment(wuta_root)

    # 检查必要依赖（仅 PyQt5 和 yaml）
    missing_deps = check_dependencies()
    if missing_deps:
        print("缺少以下依赖:")
        for dep in missing_deps:
            print(f"  - {dep}")
        print("\n请安装缺失的依赖后重试")
        sys.exit(1)

    # 创建应用
    app = QApplication(sys.argv)
    app.setApplicationName("WUTA SIM Panel")
    app.setApplicationVersion("1.0.0")

    # 设置全局字体（Linux 需中文字体支持，避免乱码）
    font = _pick_font(14)
    app.setFont(font)

    # 设置全局样式（Apple 风格浅色主题，统一定义于 theme.py）
    app.setStyleSheet(theme.global_style())

    # 创建主窗口
    from wuta_gui.ui.main_window import MainWindow

    try:
        window = MainWindow(str(wuta_root))
        window.show()
    except Exception as e:
        QMessageBox.critical(None, "启动失败", f"无法启动控制面板:\n{str(e)}")
        sys.exit(1)

    # 运行应用
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
