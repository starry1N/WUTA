"""仿真启动模块 - 复用 start_simulator.sh"""

import os
import signal
import subprocess
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

from PyQt5.QtCore import QObject
from PyQt5.QtCore import pyqtSignal


class Launcher(QObject):
    """
    仿真启动器 - 调用 start_simulator.sh 启动仿真
    
    信号：
        process_started: (PID)
        process_finished: (exit_code)
        log_line: (level, message)
    """
    
    process_started = pyqtSignal(int)
    process_finished = pyqtSignal(int)
    log_line = pyqtSignal(str, str)
    
    STATE_FILE = ".wuta_gui_state.json"
    
    def __init__(self, wuta_root: str, parent=None):
        super().__init__(parent)
        self.wuta_root = Path(wuta_root)
        self.state_file = self.wuta_root / self.STATE_FILE
        self.process: Optional[subprocess.Popen] = None
        self.log_file: Optional[str] = None
    
    def _find_start_script(self) -> Path:
        """查找 start_simulator.sh 脚本"""
        # 首先检查 wuta_root 下是否有
        script = self.wuta_root / "start_simulator.sh"
        if script.exists():
            return script
        
        # 向上查找（最多3层）
        current = self.wuta_root
        for _ in range(3):
            current = current.parent
            script = current / "start_simulator.sh"
            if script.exists():
                return script
        
        # 如果都找不到，返回默认路径
        return self.wuta_root / "start_simulator.sh"
    
    def launch(self, params: Dict[str, Any]) -> bool:
        """
        启动仿真
        
        Args:
            params: 启动参数字典
            
        Returns:
            是否成功启动
        """
        # 构建命令
        cmd = self._build_command(params)
        
        # 创建日志文件
        log_dir = self.wuta_root / "logs"
        log_dir.mkdir(exist_ok=True)
        self.log_file = str(log_dir / f"sim_{datetime.now():%Y%m%d_%H%M%S}.log")
        
        try:
            # 启动进程
            log_handle = open(self.log_file, 'w')
            log_handle.write(f"# Command: {' '.join(cmd)}\n")
            log_handle.write(f"# Started: {datetime.now().isoformat()}\n\n")
            log_handle.flush()
            
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=str(self.wuta_root),
                text=True,
                bufsize=1,
                preexec_fn=os.setsid  # 创建新进程组
            )
            
            # 保存状态
            state = {
                "pid": self.process.pid,
                "cmd": cmd,
                "log_file": self.log_file,
                "started_at": datetime.now().isoformat(),
                "params": params,
                "status": "running"
            }
            self._save_state(state)
            
            # 启动日志读取线程
            import threading
            self.log_thread = threading.Thread(target=self._read_logs, daemon=True)
            self.log_thread.start()
            
            self.process_started.emit(self.process.pid)
            return True
            
        except Exception as e:
            self.log_line.emit("ERROR", f"启动失败: {str(e)}")
            return False
    
    def _build_command(self, params: Dict[str, Any]) -> list:
        """构建启动命令"""
        start_script = self._find_start_script()
        cmd = ["bash", str(start_script)]
        
        # 跳过构建（启动页面已确保构建完成）
        cmd.append("--skip-build")
        
        # 添加 launch 参数
        launch_args = self._params_to_args(params)
        cmd.extend(launch_args)
        
        return cmd
    
    def _params_to_args(self, params: Dict[str, Any]) -> list:
        """将参数字典转换为 launch 参数列表"""
        args = []

        # 任务模式映射（整数 -> 字符串）
        MODE_MAP = {0: "trackdrive", 1: "skidpad", 2: "acceleration"}

        # 基础参数
        if 'mission_mode' in params:
            mode = params['mission_mode']
            mode_name = MODE_MAP.get(mode, "trackdrive") if isinstance(mode, int) else mode
            args.append(f"mission_mode:={mode_name}")
        
        if 'track_file' in params:
            track_val = params['track_file']
            if track_val and track_val != "default":
                # 提取文件名（不含路径和扩展名）
                from pathlib import Path
                track_val = Path(track_val).stem
            args.append(f"track_file:={track_val}")
        
        # 感知模式
        perception = params.get('perception_mode', 'simulated')
        if perception == 'traditional':
            args.append("use_track_truth_map:=false")
            args.append("use_simulated_cone_colors:=false")
        elif perception == 'simulated':
            args.append("use_track_truth_map:=false")
            args.append("use_simulated_cone_colors:=true")
        elif perception == 'truth_map':
            args.append("use_track_truth_map:=true")
            args.append("use_simulated_cone_colors:=false")
        
        # 定位模式
        localization = params.get('localization_mode', 'ekf')
        args.append(f"use_ground_truth_localization:={'true' if localization == 'truth' else 'false'}")
        
        # 布尔选项
        bool_params = {
            'launch_rviz': 'launch_rviz',
            'auto_start': 'auto_start',
            'launch_ins': 'launch_ins',
            'launch_localization': 'launch_localization',
        }
        
        for param_key, launch_key in bool_params.items():
            if param_key in params:
                value = params[param_key]
                args.append(f"{launch_key}:={'true' if value else 'false'}")
        
        # 数值参数
        numeric_params = [
            'lidar_fov_deg', 'lidar_max_range', 'trackdrive_finish_laps',
            'startup_delay', 'wheel_base', 'max_steer_angle', 'vehicle_dt'
        ]
        
        for param in numeric_params:
            if param in params:
                args.append(f"{param}:={params[param]}")
        
        return args
    
    def _read_logs(self):
        """读取日志输出"""
        if not self.process:
            return
        
        log_handle = None
        if self.log_file:
            try:
                log_handle = open(self.log_file, 'a')
            except Exception:
                pass
        
        try:
            for line in iter(self.process.stdout.readline, ''):
                if line:
                    stripped = line.strip()
                    self.log_line.emit("INFO", stripped)
                    if log_handle:
                        log_handle.write(stripped + '\n')
                        log_handle.flush()
        finally:
            if log_handle:
                log_handle.close()
        
        # 进程结束
        self.process.wait()
        self.process_finished.emit(self.process.returncode)
    
    def stop(self):
        """停止仿真"""
        if self.process and self.process.poll() is None:
            try:
                # 发送 SIGTERM 到进程组
                os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
                
                # 等待 2 秒
                import time
                time.sleep(2)
                
                # 如果还在运行，强制终止
                if self.process.poll() is None:
                    os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
                    
            except (ProcessLookupError, OSError):
                pass
        
        # 更新状态
        state = self._load_state()
        if state:
            state["status"] = "stopped"
            self._save_state(state)
    
    def is_running(self) -> bool:
        """检查仿真是否正在运行"""
        return self.process is not None and self.process.poll() is None
    
    def get_log_file(self) -> Optional[str]:
        """获取日志文件路径"""
        return self.log_file
    
    def get_status(self) -> Dict[str, Any]:
        """获取当前状态"""
        state = self._load_state()
        if not state:
            return {"status": "idle"}
        
        pid = state.get("pid")
        if pid and self._is_process_running(pid):
            state["status"] = "running"
        else:
            state["status"] = "stopped"
        
        return state
    
    def _is_process_running(self, pid: int) -> bool:
        """检查进程是否运行"""
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False
    
    def _save_state(self, state: Dict[str, Any]):
        """保存状态到文件"""
        try:
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
        except Exception:
            pass
    
    def _load_state(self) -> Optional[Dict[str, Any]]:
        """加载状态"""
        try:
            if self.state_file.exists():
                with open(self.state_file) as f:
                    return json.load(f)
        except Exception:
            pass
        return None
