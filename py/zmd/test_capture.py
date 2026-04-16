"""
test.py
测试 ScreenCaptureThread 的使用
"""

import sys
import os
import time
import cv2

# 将项目根目录加入路径，以便能导入 core 模块
# 假设 test.py 在根目录，core 在根目录下的 core 文件夹
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.interceptor.screen_capture import ScreenCaptureThread

def main():
    # 1. 实例化并启动线程
    capturer = ScreenCaptureThread(config_path="config/settings.yaml")
    capturer.start()
    
    print("开始接收画面... 按 'q' 退出。")
    
    last_time = time.time()
    fps = 0
    
    cv2.namedWindow("Capture Test", cv2.WINDOW_NORMAL)

    while True:
        # 2. 从队列获取图像
        frame = capturer.get_frame()
        
        if frame is not None:
            # 计算 FPS
            current_time = time.time()
            if current_time - last_time >= 1.0:
                print(f"接收 FPS: {fps}")
                fps = 0
                last_time = current_time
            fps += 1
            
            # 在画面左上角显示 FPS
            cv2.putText(frame, f"FPS: {fps}", (10, 50), 
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            
            # 3. 显示画面
            cv2.imshow("Capture Test", frame)
        
        # 处理按键退出
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
            
        # 避免死循环占用 CPU，如果取不到图稍微休眠一下
        if frame is None:
            time.sleep(0.001)

    # 4. 清理资源
    capturer.stop()
    cv2.destroyAllWindows()
    print("测试结束。")

if __name__ == "__main__":
    main()