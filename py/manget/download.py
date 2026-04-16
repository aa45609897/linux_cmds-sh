import asyncio
from torrentp import TorrentDownloader
import time
import os

# 你的磁力链接
magnet_link = "magnet:?xt=urn:btih:aed8ca03ed278466c4a35d509bf864051b533011&dn=zh-cn_windows_10_business_editions_version_22h2_updated_oct_2025_x64_dvd_d4e92df7.iso&xl=6985566208"

# 设置保存路径
save_path = '.'

# 文件大小（字节）
file_size = 6985566208

def format_size(bytes):
    """格式化文件大小显示"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes < 1024.0:
            return f"{bytes:.2f} {unit}"
        bytes /= 1024.0
    return f"{bytes:.2f} TB"

def format_speed(bytes_per_sec):
    """格式化速度显示"""
    return format_size(bytes_per_sec) + "/s"

async def download_with_progress():
    print("正在初始化下载...")
    print(f"文件大小: {format_size(file_size)}")
    print("-" * 50)
    
    # 创建下载器
    downloader = TorrentDownloader(magnet_link, save_path)
    
    # 开始下载（这会阻塞直到完成）
    start_time = time.time()
    last_update = time.time()
    last_size = 0
    
    # torrentp 的 start_download() 会直接下载完成
    # 我们可以通过检查文件大小来显示进度
    download_task = asyncio.create_task(downloader.start_download())
    
    # 创建一个进度监控任务
    while not download_task.done():
        await asyncio.sleep(1)  # 每秒更新一次
        
        # 检查下载文件的大小
        current_time = time.time()
        iso_file = "zh-cn_windows_10_business_editions_version_22h2_updated_oct_2025_x64_dvd_d4e92df7.iso"
        
        if os.path.exists(iso_file):
            current_size = os.path.getsize(iso_file)
            progress = (current_size / file_size) * 100
            
            # 计算下载速度
            time_diff = current_time - last_update
            size_diff = current_size - last_size
            speed = size_diff / time_diff if time_diff > 0 else 0
            
            # 计算预计剩余时间
            remaining_size = file_size - current_size
            eta = remaining_size / speed if speed > 0 else 0
            
            # 显示进度条
            bar_length = 30
            filled_length = int(bar_length * current_size // file_size)
            bar = '█' * filled_length + '░' * (bar_length - filled_length)
            
            print(f"\r进度: [{bar}] {progress:.2f}% | "
                  f"已下载: {format_size(current_size)}/{format_size(file_size)} | "
                  f"速度: {format_speed(speed)} | "
                  f"剩余: {time.strftime('%H:%M:%S', time.gmtime(eta))}",
                  end='', flush=True)
            
            last_update = current_time
            last_size = current_size
        else:
            print("\r等待文件创建...", end='', flush=True)
    
    # 等待下载任务完成
    await download_task
    
    print("\n" + "=" * 50)
    print("✓ 下载完成！")
    
    # 显示最终文件信息
    if os.path.exists(iso_file):
        final_size = os.path.getsize(iso_file)
        total_time = time.time() - start_time
        print(f"文件路径: {os.path.abspath(iso_file)}")
        print(f"文件大小: {format_size(final_size)}")
        print(f"总用时: {time.strftime('%H:%M:%S', time.gmtime(total_time))}")

# 运行下载
asyncio.run(download_with_progress())