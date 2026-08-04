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
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QFontDatabase


def _ensure_ros_environment(wuta_root: Path) -> None:
    """确保 ROS 环境已正确 source。

    如果 wuta_msgs 无法导入，说明当前进程环境不完整。
    此时自动重新执行自身（先 source 所有 setup 文件），
    确保新进程拥有完整环境。
    """
    # 已 source 过（或首次启动就能导入），直接返回
    try:
        import wuta_msgs  # noqa: F401
        return
    except ImportError:
        pass

    # 需要 source 的 setup 文件
    setup_files = [
        "/opt/ros/humble/setup.bash",
        str(wuta_root / "WUTA-FSD/ros2_ws/install/setup.bash"),
        str(wuta_root / "WUTA-SIM/install/setup.bash"),
    ]
    existing_setup = [f for f in setup_files if os.path.isfile(f)]
    if not existing_setup:
        return  # 没有 setup 文件，无法修复

    # 构造重新执行命令：source 所有 setup 后，用同一个 Python 重新运行
    source_cmds = " && ".join(f'source "{s}"' for s in existing_setup)
    # 使用当前 Python 解释器重新执行，传递原始参数
    gui_args = " ".join(sys.argv[1:])
    rerun_cmd = f'{source_cmds} && exec "{sys.executable}" -m wuta_gui {gui_args}'

    print("[GUI] ROS environment not detected, restarting with proper setup...")
    print(f"[GUI] Running: {rerun_cmd}")

    # 用 exec 替换当前进程（如果 bash 支持的话），否则用 subprocess
    result = subprocess.run(
        ["bash", "-c", rerun_cmd],
        cwd=str(wuta_root),
    )
    # 新进程已启动，退出当前进程
    sys.exit(result.returncode)


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
    # 首先检查当前目录
    current = Path.cwd()
    if (current / "start_simulator.sh").exists():
        return current

    # 向上查找（最多3层）
    for _ in range(3):
        current = current.parent
        if (current / "start_simulator.sh").exists():
            return current

    # 如果找不到，使用默认路径
    return Path.cwd()


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

    # 设置全局样式 - Apple 风格浅色主题
    app.setStyleSheet("""
        QMainWindow {
            background-color: #f5f5f7;
        }
        QGroupBox {
            font-weight: 600;
            font-size: 15px;
            border: 1px solid #d2d2d7;
            border-radius: 10px;
            margin-top: 12px;
            padding-top: 16px;
            background-color: #ffffff;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 16px;
            padding: 0 8px;
            color: #1d1d1f;
        }
        QPushButton {
            background-color: #0071e3;
            color: white;
            border: none;
            border-radius: 8px;
            padding: 8px 20px;
            font-weight: 500;
            font-size: 14px;
        }
        QPushButton:hover {
            background-color: #0077ed;
        }
        QPushButton:pressed {
            background-color: #0068d0;
        }
        QPushButton:disabled {
            background-color: #d2d2d7;
            color: #8e8e93;
        }
        QComboBox {
            border: 1px solid #d2d2d7;
            border-radius: 8px;
            padding: 6px 12px;
            background-color: white;
            min-height: 24px;
        }
        QComboBox:hover {
            border-color: #0071e3;
        }
        QComboBox::drop-down {
            border: none;
            width: 24px;
        }
        QCheckBox {
            font-size: 14px;
            color: #1d1d1f;
            spacing: 8px;
        }
        QCheckBox::indicator {
            width: 18px;
            height: 18px;
        }
        QRadioButton {
            font-size: 14px;
            color: #1d1d1f;
            spacing: 8px;
        }
        QRadioButton::indicator {
            width: 18px;
            height: 18px;
        }
        QLabel {
            color: #1d1d1f;
        }
        QMessageBox {
            background-color: #ffffff;
        }
        QMessageBox QLabel {
            color: #1d1d1f;
            font-size: 13px;
        }
        QMessageBox QPushButton {
            background-color: #ffffff;
            color: #1d1d1f;
            border: 1px solid #d2d2d7;
            border-radius: 8px;
            padding: 8px 20px;
            font-size: 13px;
            font-weight: 500;
            min-width: 70px;
        }
        QMessageBox QPushButton:hover {
            background-color: #f0f0f2;
        }
        QPushButton:pressed {
            background-color: #e8e8ed;
        }
    """)

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
