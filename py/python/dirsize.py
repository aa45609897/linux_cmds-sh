#!/usr/bin/env python3
"""
彩色目录文件大小查看器
"""

import os
import sys
from pathlib import Path
from datetime import datetime
import argparse

# ANSI 颜色代码
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'

def get_size_format(size):
    """获取易读的大小格式"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} PB"

def get_color_by_size(size):
    """根据文件大小返回颜色"""
    if size < 1024:  # < 1KB
        return Colors.GREEN
    elif size < 1024 * 1024:  # < 1MB
        return Colors.BLUE
    elif size < 1024 * 1024 * 100:  # < 100MB
        return Colors.YELLOW
    else:
        return Colors.RED

def scan_directory(path, show_hidden=False, sort_by='name'):
    """扫描目录并打印"""
    try:
        path = Path(path).expanduser().resolve()
        if not path.exists():
            print(f"{Colors.RED}路径不存在: {path}{Colors.END}")
            return
        
        print(f"\n{Colors.BOLD}{Colors.HEADER}📁 目录: {path}{Colors.END}")
        print(f"{Colors.CYAN}{'=' * 80}{Colors.END}")
        
        items = []
        total_files = total_dirs = total_size = 0
        
        # 收集信息
        for item in path.iterdir():
            if not show_hidden and item.name.startswith('.'):
                continue
            
            try:
                stat = item.stat()
                mtime = datetime.fromtimestamp(stat.st_mtime)
                
                if item.is_file():
                    items.append(('file', item.name, stat.st_size, mtime))
                    total_files += 1
                    total_size += stat.st_size
                elif item.is_dir():
                    # 计算目录大小
                    dir_size = sum(f.stat().st_size for f in item.glob('**/*') if f.is_file())
                    items.append(('dir', item.name, dir_size, mtime))
                    total_dirs += 1
                    total_size += dir_size
            except PermissionError:
                items.append(('error', item.name, 0, None))
        
        # 排序
        if sort_by == 'size':
            items.sort(key=lambda x: x[2], reverse=True)
        elif sort_by == 'time':
            items.sort(key=lambda x: x[3] if x[3] else datetime.min, reverse=True)
        else:
            items.sort(key=lambda x: x[1].lower())
        
        # 打印
        for item_type, name, size, mtime in items:
            if item_type == 'file':
                color = get_color_by_size(size)
                icon = "📄"
                size_str = get_size_format(size)
            elif item_type == 'dir':
                color = Colors.CYAN
                icon = "📁"
                size_str = get_size_format(size)
            else:
                color = Colors.RED
                icon = "⚠️"
                size_str = "N/A"
            
            time_str = mtime.strftime('%Y-%m-%d %H:%M') if mtime else "N/A"
            print(f"{icon} {color}{size_str:>10}{Colors.END}  {time_str}  {name}")
        
        print(f"{Colors.CYAN}{'=' * 80}{Colors.END}")
        print(f"{Colors.BOLD}📊 总计: {total_files} 文件, {total_dirs} 目录, {get_size_format(total_size)}{Colors.END}")
        
    except Exception as e:
        print(f"{Colors.RED}错误: {e}{Colors.END}")

def main():
    parser = argparse.ArgumentParser(description='彩色目录大小查看器')
    parser.add_argument('path', nargs='?', default='.', help='目录路径')
    parser.add_argument('-a', '--all', action='store_true', help='显示隐藏文件')
    parser.add_argument('-s', '--sort', choices=['name', 'size', 'time'],
                       default='name', help='排序方式')
    
    args = parser.parse_args()
    scan_directory(args.path, args.all, args.sort)

if __name__ == "__main__":
    main()
