# test_icon.py
from PIL import Image
import os

# 检查文件是否存在
icon_path = "icon.ico"  # 改成你的文件名
print(f"文件存在: {os.path.exists(icon_path)}")
print(f"文件大小: {os.path.getsize(icon_path)} 字节")

# 尝试用 PIL 打开
try:
    img = Image.open(icon_path)
    print(f"ICO 格式有效，尺寸: {img.size}")
    img.show()  # 会弹出图片查看器显示图标
except Exception as e:
    print(f"ICO 文件无效: {e}")