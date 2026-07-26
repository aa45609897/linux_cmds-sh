from PIL import Image
import os
import sys

def png_transparent_to_white(input_path, output_path=None, background_color=(255, 255, 255)):
    """
    将 PNG 图片的透明背景改为白色（或指定颜色）

    参数:
        input_path: 输入的 PNG 文件路径
        output_path: 输出文件路径（可选，默认在输入文件名后加 "_white"）
        background_color: RGB 颜色元组，例如 (255,255,255) 白色
    """
    # 打开图片，确保是 RGBA 模式
    img = Image.open(input_path).convert("RGBA")

    # 创建相同尺寸的纯色背景图
    bg = Image.new("RGBA", img.size, background_color + (255,))  # 添加 alpha=255

    # 合并：将原图贴到背景上（alpha 混合）
    combined = Image.alpha_composite(bg, img).convert("RGB")  # 去掉 alpha 通道

    # 确定输出路径
    if output_path is None:
        base, ext = os.path.splitext(input_path)
        output_path = f"{base}_white.jpg"  # 默认存为 JPG
        # 也可以存为 PNG，但背景已不透明且文件更大
        # output_path = f"{base}_white.png"

    combined.save(output_path, "JPEG", quality=95)  # 保存为 JPG
    print(f"✅ 转换完成: {output_path}")

if __name__ == "__main__":
    # 用法 1: 命令行参数
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
        output_file = sys.argv[2] if len(sys.argv) > 2 else None
        png_transparent_to_white(input_file, output_file)
    else:
        # 用法 2: 直接修改下面的文件名
        # 你可以在这里指定要转换的图片
        input_file = "feng1.png"   # 替换成你的图片名
        output_file = "feng1_white.jpg"
        png_transparent_to_white(input_file, output_file)