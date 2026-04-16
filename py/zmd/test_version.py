"""
test_vision.py
测试 截图 + 视觉识别 的完整流程
"""

import sys
import os
import time
import cv2
import numpy as np

# 确保路径正确
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.interceptor.screen_capture import ScreenCaptureThread
from core.vision.detector import YOLODetector

def main():
    # 1. 启动截图线程
    capturer = ScreenCaptureThread(config_path="config/settings.yaml")
    capturer.start()
    time.sleep(1) # 稍作等待，确保 MSS 初始化完成

    # 2. 初始化检测器
    detector = YOLODetector(config_path="config/model_config.yaml")

    print("开始视觉识别测试... 按 'q' 退出。")
    print("提示：目前使用的是通用模型 (yolov8n)，请确保屏幕上有 'person', 'cell phone' 等通用物体，或者加载你自己的模型。")

    last_time = time.time()
    fps = 0
    frame_count = 0
    
    cv2.namedWindow("Vision Test", cv2.WINDOW_NORMAL)

    while True:
        # 3. 获取图像
        frame = capturer.get_frame()
        
        if frame is not None:
            # 4. 进行推理
            start_infer = time.time()
            results = detector.predict(frame)
            infer_time = time.time() - start_infer
            
            # 5. 可视化结果 (绘制框)
            frame_drawn = detector.draw_results(frame, results)
            
            # 6. 计算和显示 FPS
            current_time = time.time()
            frame_count += 1
            if current_time - last_time >= 1.0:
                fps = frame_count
                frame_count = 0
                last_time = current_time
            
            # 显示状态信息
            info_text = f"FPS: {fps} | Infer: {infer_time*1000:.1f}ms | Objects: {len(results)}"
            cv2.putText(frame_drawn, info_text, (10, 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
            
            # 显示画面
            cv2.imshow("Vision Test", frame_drawn)
        
        # 按 q 退出
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    capturer.stop()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()