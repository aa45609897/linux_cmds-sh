"""
core/vision/detector.py
基于 Ultralytics YOLO 的视觉检测模块
"""

import yaml
import torch
from ultralytics import YOLO
import cv2
import os

class YOLODetector:
    def __init__(self, config_path="config/model_config.yaml"):
        # 1. 加载配置
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
            
        model_path = self.config['model']['path']
        device = self.config['model']['device']
        
        # 2. 加载模型
        if not os.path.exists(model_path):
            print(f"[Warning] 模型文件不存在: {model_path}，尝试下载默认模型...")
            # 如果没找到，ultralytics 会自动下载 yolo8n.pt，但这需要网络
        
        print(f"[Detector] 正在加载模型 {model_path} 到设备 {device}...")
        self.model = YOLO(model_path)
        
        # 预热：运行一次空推理，避免第一次识别卡顿
        # self.model.predict(source=torch.zeros((1, 3, 640, 640)), device=device, verbose=False)
        
        self.conf = self.config['inference']['conf']
        self.iou = self.config['inference']['iou']
        
        # 获取类别名称映射
        self.names = self.model.names
        
        print(f"[Detector] 模型加载完成。类别: {self.names}")

    def predict(self, frame):
        """
        对单帧图像进行预测
        :param frame: BGR 图像
        :return: 检测结果列表 [dict, dict, ...]
                 dict 结构: {
                    'label': str,
                    'conf': float,
                    'box': [x1, y1, x2, y2],
                    'center': (cx, cy),
                    'area': int
                 }
        """
        if frame is None:
            return []

        # 使用 YOLO 进行推理
        # verbose=False 关闭控制台输出，提升速度
        results = self.model.predict(
            source=frame, 
            conf=self.conf, 
            iou=self.iou, 
            verbose=False,
            device=self.config['model']['device']
        )
        
        parsed_results = []
        
        # 解析结果
        for result in results:
            boxes = result.boxes
            for box in boxes:
                # 获取坐标 (xyxy)
                xyxy = box.xyxy[0].cpu().numpy()
                x1, y1, x2, y2 = map(int, xyxy)
                
                # 计算中心点
                cx = int((x1 + x2) / 2)
                cy = int((y1 + y2) / 2)
                
                # 获取置信度
                conf = float(box.conf[0].cpu().numpy())
                
                # 获取类别 ID 和 名称
                cls_id = int(box.cls[0].cpu().numpy())
                label_name = self.names[cls_id]
                
                parsed_results.append({
                    'label': label_name,
                    'conf': conf,
                    'box': [x1, y1, x2, y2],
                    'center': (cx, cy),
                    'area': (x2 - x1) * (y2 - y1)
                })
                
        return parsed_results

    def draw_results(self, frame, results):
        """
        将检测结果画在图上（用于调试）
        :param frame: 原图
        :param results: predict 返回的结果列表
        :return: 绘制后的图像
        """
        for res in results:
            x1, y1, x2, y2 = res['box']
            cx, cy = res['center']
            label = f"{res['label']} {res['conf']:.2f}"
            
            # 画框
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            # 画中心点
            cv2.circle(frame, (cx, cy), 3, (0, 0, 255), -1)
            # 写字
            cv2.putText(frame, label, (x1, y1 - 10), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        return frame