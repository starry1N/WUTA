"""任务模式常量 - 集中管理，避免各模块重复定义"""

# 任务模式 ID（与 wuta_msgs/MissionState 保持一致）
MODE_TRACKDRIVE = 0
MODE_SKIDPAD = 1
MODE_ACCELERATION = 2

# 显示名称（启动页面单选按钮）
MODE_NAMES = {
    MODE_TRACKDRIVE: "Trackdrive",
    MODE_SKIDPAD: "Skidpad",
    MODE_ACCELERATION: "Acceleration",
}

# 状态字符串（顶栏/计时面板使用，大写）
MODE_STRINGS = {
    MODE_TRACKDRIVE: "TRACKDRIVE",
    MODE_SKIDPAD: "SKIDPAD",
    MODE_ACCELERATION: "ACCELERATION",
}

# launch 参数值（小写，供 start_simulator.sh）
MODE_LAUNCH = {
    MODE_TRACKDRIVE: "trackdrive",
    MODE_SKIDPAD: "skidpad",
    MODE_ACCELERATION: "acceleration",
}

# 赛道文件前缀
MODE_TRACK_PREFIX = {
    MODE_TRACKDRIVE: "trackdrive",
    MODE_SKIDPAD: "skidpad",
    MODE_ACCELERATION: "acceleration",
}


def mode_string(mission_mode: int) -> str:
    """模式整数 -> 大写状态字符串"""
    return MODE_STRINGS.get(mission_mode, MODE_STRINGS[MODE_TRACKDRIVE])
