"""构建管理模块 - 复用 start_simulator.sh"""

import re
import subprocess
import time
from enum import Enum
from pathlib import Path

from PyQt5.QtCore import QThread
from PyQt5.QtCore import pyqtSignal

from wuta_gui.core import workspace


class BuildMode(Enum):
    """构建模式"""
    INCREMENTAL = "incremental"      # 增量构建
    LIGHTWEIGHT = "lightweight"      # 轻量构建（限制并行）
    CLEAN = "clean"                  # 清理重建
    CLEAN_LIGHTWEIGHT = "clean_lightweight"  # 清理重建 + 轻量
    SKIP = "skip"                    # 跳过构建


class Builder(QThread):
    """
    构建线程 - 调用 start_simulator.sh 执行构建
    
    信号：
        progress: (百分比, 消息)
        log_line: (日志行)
        stage_changed: (阶段名称)
        finished: (是否成功, 消息)
    """
    
    progress = pyqtSignal(int, str)
    log_line = pyqtSignal(str)
    stage_changed = pyqtSignal(str)
    finished = pyqtSignal(bool, str)
    
    def __init__(self, wuta_root: str, mode: BuildMode, parent=None):
        super().__init__(parent)
        self.wuta_root = Path(wuta_root)
        self.mode = mode
        self._is_running = True
        self.process = None
    
    def run(self):
        """执行构建"""
        try:
            if self.mode == BuildMode.SKIP:
                self.progress.emit(100, "跳过构建")
                self.finished.emit(True, "已跳过构建")
                return
            
            # 构建命令
            cmd = self._build_command()
            
            self.log_line.emit(f"执行命令: {' '.join(cmd)}")
            
            # 启动进程
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=str(self.wuta_root),
                text=True,
                bufsize=1
            )
            
            # 读取输出
            start_time = time.time()
            
            for line in iter(self.process.stdout.readline, ''):
                if not self._is_running:
                    self.process.terminate()
                    self.process.wait()
                    self.finished.emit(False, "已取消")
                    return
                
                line = line.strip()
                if line:
                    self.log_line.emit(line)
                    self._parse_progress(line)
            
            # 等待完成
            self.process.wait()
            
            if self.process.returncode == 0:
                elapsed = time.time() - start_time
                self.progress.emit(100, "构建完成")
                self.finished.emit(True, f"构建完成，耗时 {int(elapsed)} 秒")
            else:
                self.finished.emit(False, f"构建失败，退出码: {self.process.returncode}")
                
        except Exception as e:
            self.finished.emit(False, f"构建异常: {str(e)}")
    
    def _build_command(self) -> list:
        """构建命令"""
        start_script = workspace.find_start_script(self.wuta_root)
        cmd = ["bash", str(start_script)]
        
        if self.mode == BuildMode.CLEAN:
            cmd.append("--clean")
        elif self.mode == BuildMode.LIGHTWEIGHT:
            cmd.append("--lightweight")
        elif self.mode == BuildMode.CLEAN_LIGHTWEIGHT:
            cmd.append("--clean")
            cmd.append("--lightweight")
        
        # 仅构建，不启动
        cmd.append("--build-only")
        
        return cmd
    
    def _parse_progress(self, line: str):
        """解析构建进度"""
        # FSD 构建阶段
        if "[1/2]" in line:
            self.stage_changed.emit("构建 WUTA-FSD")
        elif "[2/2]" in line:
            self.stage_changed.emit("构建 WUTA-SIM")
        
        # 解析 colcon 进度
        if "Starting" in line and "--->" in line:
            package_name = line.split("--->")[-1].strip()
            self.progress.emit(-1, f"编译 {package_name}")
        
        # 解析完成信息
        if "packages finished" in line:
            match = re.search(r'(\d+) packages finished', line)
            if match:
                count = int(match.group(1))
                self.log_line.emit(f"已完成 {count} 个包")
    
    def stop(self):
        """停止构建"""
        self._is_running = False
        if self.process and self.process.poll() is None:
            self.process.terminate()
