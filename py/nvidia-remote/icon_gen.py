# create_standard_ico.py
import sys
from PIL import Image
import numpy as np
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPixmap, QPainter, QColor, QPen
from PyQt6.QtCore import Qt, QPoint

def create_standard_ico():
    """创建一个符合 Windows 标准的 ICO 文件"""
    
    # 必须先创建 QApplication 实例
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    # 创建多个尺寸的图标（Windows 图标通常包含多个尺寸）
    sizes = [16, 32, 48, 64, 128, 256]
    images = []
    
    for size in sizes:
        # 创建画布
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 绘制背景
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(50, 50, 50))
        
        # 圆角半径根据尺寸调整
        radius = max(2, size // 6)
        painter.drawRoundedRect(0, 0, size, size, radius, radius)
        
        # 绘制折线（根据尺寸调整线条粗细和位置）
        pen_width = max(1, size // 16)
        pen = QPen(QColor(0, 255, 0), pen_width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        
        # 根据尺寸调整坐标
        points = [
            QPoint(int(size * 0.15), int(size * 0.7)),
            QPoint(int(size * 0.4), int(size * 0.4)),
            QPoint(int(size * 0.6), int(size * 0.6)),
            QPoint(int(size * 0.85), int(size * 0.25))
        ]
        
        for i in range(len(points) - 1):
            painter.drawLine(points[i], points[i+1])
        
        painter.end()
        
        # 转换为 PIL Image
        qimage = pixmap.toImage()
        ptr = qimage.bits()
        ptr.setsize(qimage.sizeInBytes())
        arr = np.array(ptr).reshape((size, size, 4))
        
        # 确保 RGBA 格式正确
        pil_img = Image.fromarray(arr, 'RGBA')
        images.append(pil_img)
    
    # 保存为多尺寸 ICO
    output_path = "app_icon.ico"
    images[0].save(
        output_path, 
        format='ICO', 
        sizes=[(s, s) for s in sizes],
        append_images=images[1:]
    )
    
    print(f"标准 ICO 文件已创建: {output_path}")
    return output_path

if __name__ == "__main__":
    create_standard_ico()
    # 不需要 app.exec()，因为不需要显示窗口
    print("完成！")