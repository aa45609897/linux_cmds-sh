#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文件智能重命名工具
使用DeepSeek API生成多个重命名建议，用户可选择或自定义
"""

import os
import csv
import json
import time
import shutil
from pathlib import Path
from datetime import datetime
import requests
from typing import List, Dict, Optional

class DeepSeekRenamer:
    def __init__(self, api_key: str, api_url: str = "https://api.deepseek.com/v1/chat/completions"):
        """
        初始化重命名工具
        
        Args:
            api_key: DeepSeek API密钥
            api_url: API端点URL
        """
        self.api_key = api_key
        self.api_url = api_url
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
    def generate_rename_suggestions(self, filename: str, num_suggestions: int = 3) -> List[str]:
        """
        调用DeepSeek API生成重命名建议
        
        Args:
            filename: 原始文件名
            num_suggestions: 建议数量
            
        Returns:
            重命名建议列表
        """
        # 提取文件信息
        file_path = Path(filename)
        file_stem = file_path.stem
        file_ext = file_path.suffix
        
        # 构建提示词
        prompt = f"""请为这个文件名生成{num_suggestions}个更好的命名建议。
原始文件名: {file_stem}
文件扩展名: {file_ext}

要求：
1. 保持文件扩展名不变
2. 命名格式：音乐名-作者-简单信息
3. 如果原始文件名包含相关信息，请提取并使用
4. 建议应该简洁、清晰、符合规范
5. 每个建议只返回文件名，不要包含序号或其他内容

请直接返回建议列表，每个建议一行。"""
        
        # 调用API
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": "你是一个专业的文件命名助手，擅长为音乐文件生成规范的命名建议。"},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 500
        }
        
        try:
            response = requests.post(
                self.api_url,
                headers=self.headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            
            result = response.json()
            suggestions_text = result['choices'][0]['message']['content']
            
            # 解析返回的建议
            suggestions = []
            for line in suggestions_text.strip().split('\n'):
                line = line.strip()
                if line and not line.startswith(('1.', '2.', '3.', '-', '*')):
                    # 如果行没有序号，直接添加扩展名
                    if not line.endswith(file_ext):
                        line += file_ext
                    suggestions.append(line)
                elif line and (line.startswith(('1.', '2.', '3.')) or line.startswith(('-', '*'))):
                    # 去除序号和前缀
                    clean_name = line.split('.', 1)[-1] if '.' in line else line
                    clean_name = clean_name.strip('- *')
                    if not clean_name.endswith(file_ext):
                        clean_name += file_ext
                    suggestions.append(clean_name)
            
            return suggestions[:num_suggestions]
            
        except Exception as e:
            print(f"API调用失败: {e}")
            return [f"{file_stem}_suggestion1{file_ext}", 
                   f"{file_stem}_suggestion2{file_ext}", 
                   f"{file_stem}_suggestion3{file_ext}"]

    def process_file(self, file_path: Path, origin_dir: Path, generate_dir: Path, 
                     csv_writer, csv_file) -> Optional[Dict]:
        """
        处理单个文件
        
        Args:
            file_path: 原始文件路径
            origin_dir: 原始目录
            generate_dir: 输出目录
            csv_writer: CSV写入器
            csv_file: CSV文件对象
            
        Returns:
            处理结果字典
        """
        filename = file_path.name
        print(f"\n处理文件: {filename}")
        
        # 生成建议
        suggestions = self.generate_rename_suggestions(filename)
        
        # 显示建议
        print("\n建议的新文件名:")
        for i, suggestion in enumerate(suggestions, 1):
            print(f"  {i}. {suggestion}")
        print(f"  4. 自定义")
        print(f"  5. 跳过此文件")
        
        # 获取用户选择
        while True:
            try:
                choice = input("\n请选择 (1-5): ").strip()
                if choice == '5':
                    print("跳过文件")
                    return None
                elif choice == '4':
                    custom_name = input("请输入自定义文件名 (包含扩展名): ").strip()
                    if custom_name:
                        selected_name = custom_name
                        break
                    else:
                        print("文件名不能为空，请重新选择")
                elif choice in ['1', '2', '3']:
                    selected_name = suggestions[int(choice) - 1]
                    break
                else:
                    print("无效选择，请输入1-5")
            except (ValueError, IndexError):
                print("无效输入，请重试")
        
        # 复制并重命名文件
        new_path = generate_dir / selected_name
        
        # 如果目标文件已存在，添加序号
        counter = 1
        while new_path.exists():
            name_without_ext = new_path.stem
            ext = new_path.suffix
            new_path = generate_dir / f"{name_without_ext}_{counter}{ext}"
            counter += 1
        
        try:
            shutil.copy2(file_path, new_path)
            print(f"文件已保存为: {new_path.name}")
            
            # 记录到CSV
            result = {
                'original_filename': filename,
                'original_path': str(file_path),
                'new_filename': new_path.name,
                'new_path': str(new_path),
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'suggestions': '|'.join(suggestions)  # 用|分隔多个建议
            }
            
            csv_writer.writerow(result)
            csv_file.flush()  # 立即写入磁盘
            
            return result
            
        except Exception as e:
            print(f"文件操作失败: {e}")
            return None

from lib.aes import AES
from lib.kv import CFKV
import os

aes = AES(os.getenv("GENERAL_PASSWORD"))
kv= CFKV()

deepseek_keys = aes.dec(kv.get("deepseek_keys"))

def main():
    """主函数"""
    print("=" * 50)
    print("文件智能重命名工具")
    print("=" * 50)
    
    # 获取配置
    api_key = deepseek_keys['DEEPSEEK_API_KEY']
    url = deepseek_keys['DEEPSEEK_API_URL']
    if not api_key:
        print("错误: API密钥不能为空")
        return
    
    # 设置目录
    script_dir = Path(__file__).parent
    origin_dir = script_dir / "origin"
    generate_dir = script_dir / "generate"
    
    # 创建必要目录
    origin_dir.mkdir(exist_ok=True)
    generate_dir.mkdir(exist_ok=True)
    
    # 检查origin目录
    files = list(origin_dir.glob('*'))
    if not files:
        print(f"错误: origin目录为空，请将文件放入: {origin_dir}")
        return
    
    print(f"\n找到 {len(files)} 个文件")
    print(f"原始目录: {origin_dir}")
    print(f"输出目录: {generate_dir}")
    
    # 初始化重命名器
    renamer = DeepSeekRenamer(api_key, api_url=url)
    
    # 准备CSV文件
    csv_path = script_dir / f"rename_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    with open(csv_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
        fieldnames = ['original_filename', 'original_path', 'new_filename', 
                     'new_path', 'timestamp', 'suggestions']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        # 处理每个文件
        results = []
        for file_path in files:
            if file_path.is_file():
                result = renamer.process_file(
                    file_path, origin_dir, generate_dir, writer, csvfile
                )
                if result:
                    results.append(result)
                
                # 在文件之间添加延迟，避免API限流
                if file_path != files[-1]:
                    time.sleep(1)
    
    # 显示统计信息
    print("\n" + "=" * 50)
    print("处理完成！")
    print(f"处理文件数: {len(results)}/{len(files)}")
    print(f"日志文件: {csv_path}")
    print(f"生成文件位置: {generate_dir}")
    
    # 显示CSV内容预览
    if results:
        print("\n处理结果预览:")
        for r in results[:5]:  # 只显示前5个
            print(f"  {r['original_filename']} -> {r['new_filename']}")
        if len(results) > 5:
            print(f"  ... 还有 {len(results) - 5} 个文件")

if __name__ == "__main__":
    main()