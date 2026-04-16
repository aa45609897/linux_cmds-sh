"""
core/interceptor/screen_capture.py
支持指定进程识别、自动获取窗口位置、帧率限制、自动缩放的多线程截图模块
"""

import mss
import numpy as np
import time
import threading
import queue
import yaml
import win32gui
import win32process
import psutil
import os
import cv2  # 引入 OpenCV 用于 Resize
from pathlib import Path

class ScreenCaptureThread(threading.Thread):
    def __init__(self, config_path="config/settings.yaml"):
        """
        初始化截图线程
        """
        super().__init__()
        self._stop_event = threading.Event()
        self.config = self._load_config(config_path)
        self.frame_queue = queue.Queue(maxsize=2) # 队列容量为2，只保留最新帧
        
        self.sct = None 
        self.hwnd = None
        self.monitor = None
        
        # --- 新增：读取目标分辨率 ---
        disp_cfg = self.config['display']
        self.target_width = disp_cfg['width']
        self.target_height = disp_cfg['height']
        
        # 帧率控制参数
        self.target_fps = self.config['capture'].get('target_fps', 60)
        self.frame_duration = 1.0 / self.target_fps if self.target_fps > 0 else 0
        
        print(f"[ScreenCapture] 初始化完成. 目标进程: {self.config['capture']['target_process_name']}, 目标帧率: {self.target_fps}")
        print(f"[ScreenCapture] 目标输出分辨率: {self.target_width}x{self.target_height}")

    def _load_config(self, config_path):
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"配置文件未找到: {config_path}")
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def _find_target_window(self):
        """通过进程名查找窗口句柄并计算截图区域"""
        process_name = self.config['capture']['target_process_name']
        
        def callback(hwnd, windows):
            if win32gui.IsWindowVisible(hwnd):
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                try:
                    process = psutil.Process(pid)
                    if process.name() == process_name:
                        windows.append(hwnd)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

        windows = []
        win32gui.EnumWindows(callback, windows)
        
        if not windows:
            print(f"[Warning] 未找到进程 '{process_name}' 的窗口，回退到配置文件中的手动 ROI 设置。")
            roi = self.config['capture']['game_roi']
            self.monitor = {
                "top": roi['top'],
                "left": roi['left'],
                "width": roi['width'],
                "height": roi['height']
            }
        else:
            self.hwnd = windows[0]
            rect = win32gui.GetWindowRect(self.hwnd)
            self.monitor = {
                "top": rect[1],
                "left": rect[0],
                "width": rect[2] - rect[0],
                "height": rect[3] - rect[1]
            }
            print(f"[ScreenCapture] 已锁定窗口句柄: {self.hwnd}, 源区域: {self.monitor}")

    def get_frame(self):
        """获取最新一帧，非阻塞"""
        try:
            return self.frame_queue.get_nowait()
        except queue.Empty:
            return None

    def run(self):
        """线程主循环"""
        # 1. 初始化窗口位置
        self._find_target_window()
        
        # 2. 在子线程内部初始化 mss
        self.sct = mss.mss()
        print("[ScreenCapture] MSS 实例已在线程内创建")

        while not self._stop_event.is_set():
            start_time = time.time()
            
            try:
                # 3. 执行截图
                screenshot = np.array(self.sct.grab(self.monitor))
                
                # 4. 处理图像：去 Alpha + 拷贝内存 (解决 OpenCV 兼容性)
                frame = screenshot[:, :, :3].copy()
                
                # --- 新增：自动 Resize ---
                # 检查当前帧尺寸是否与目标一致，不一致则缩放
                h, w = frame.shape[:2]
                if w != self.target_width or h != self.target_height:
                    # 使用 INTER_LINEAR 进行缩放，速度和质量平衡
                    frame = cv2.resize(frame, (self.target_width, self.target_height), interpolation=cv2.INTER_LINEAR)
                
                # 5. 放入队列
                if self.frame_queue.full():
                    try:
                        self.frame_queue.get_nowait()
                    except queue.Empty:
                        pass
                self.frame_queue.put(frame)
                
            except Exception as e:
                print(f"[Error] 截图异常: {e}")
                if self.hwnd and not win32gui.IsWindow(self.hwnd):
                    print("[ScreenCapture] 窗口已关闭，尝试重新查找...")
                    self._find_target_window()
                time.sleep(0.5)

            # 6. 帧率控制
            elapsed = time.time() - start_time
            sleep_time = self.frame_duration - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    def stop(self):
        """停止线程"""
        self._stop_event.set()
        self.join()