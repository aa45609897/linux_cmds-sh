from lib.kv import CFKV
from lib.aes import AES
import os
import json
import urllib

general_password = os.environ.get("GENERAL_PASSWORD")

kv = CFKV()
aes = AES(general_password)

pan_keys = aes.dec(kv.get("pan_keys"))
print(pan_keys)


import os
import time
import hashlib
from baidu_client import BaiduPanClient

# ===== 配置 =====
ACCESS_TOKEN = pan_keys["access_token"]
# 既然支持全盘操作，我们直接指定根目录下的 data 文件夹
ROOT_DIR = "/apps/data" 
# ================

def calculate_md5(file_path: str) -> str:
    """计算文件的 MD5 哈希值"""
    print(f"[HASH] 正在计算文件哈希: {os.path.basename(file_path)}")
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def create_test_file(file_path: str, size_mb: int):
    """生成指定大小的测试文件"""
    print(f"[FILE] 生成测试文件: {file_path} ({size_mb}MB)")
    # 使用随机数据，避免秒传，确保真实测试上传过程
    with open(file_path, "wb") as f:
        # 为了生成速度快一点，我们写大块的随机数据
        # 生成 1MB 的随机数据块，然后重复写
        chunk = os.urandom(1024 * 1024) 
        remaining = size_mb
        while remaining > 0:
            write_size = min(remaining, 1)
            f.write(chunk[:write_size * 1024 * 1024])
            remaining -= 1
            
def run_test(client: BaiduPanClient, test_size_mb: int, test_name: str):
    print("\n" + "="*50)
    print(f"开始测试: {test_name} (大小: {test_size_mb}MB)")
    print("="*50)
    
    local_file = f"test_{test_size_mb}mb.bin"
    downloaded_file = f"test_{test_size_mb}mb_downloaded.bin"
    remote_path = f"/test_dir/{local_file}"
    
    try:
        # 1. 准备环境：确保远程目录存在
        client.mkdir("/test_dir")
        
        # 2. 生成本地文件
        create_test_file(local_file, test_size_mb)
        
        # 3. 计算本地文件哈希
        original_md5 = calculate_md5(local_file)
        print(f"[RESULT] 原始文件 MD5: {original_md5}")
        
        # 4. 上传
        start_time = time.time()
        client.upload_file(local_file, remote_path)
        upload_time = time.time() - start_time
        print(f"[TIME] 上传耗时: {upload_time:.2f} 秒")
        
        # 5. 下载
        start_time = time.time()
        client.download_file(remote_path, downloaded_file)
        download_time = time.time() - start_time
        print(f"[TIME] 下载耗时: {download_time:.2f} 秒")
        
        # 6. 计算下载文件哈希
        downloaded_md5 = calculate_md5(downloaded_file)
        print(f"[RESULT] 下载文件 MD5: {downloaded_md5}")
        
        # 7. 比对结果
        if original_md5 == downloaded_md5:
            print(f"\n[✅ SUCCESS] 哈希比对一致！测试通过！\n")
        else:
            print(f"\n[❌ FAILED] 哈希比对不一致！文件损坏！\n")
            
        # 8. 清理云端 (可选)
        # client.delete(remote_path)
            
    except Exception as e:
        print(f"\n[❌ ERROR] 测试过程中发生错误: {e}\n")
    finally:
        # 清理本地文件
        if os.path.exists(local_file): os.remove(local_file)
        if os.path.exists(downloaded_file): os.remove(downloaded_file)

def main():
    client = BaiduPanClient(access_token=ACCESS_TOKEN, root_dir=ROOT_DIR)
    # client.delete("/test_dir")  # 确保测试环境干净
    print(client.list_files("/test_dir"))  # 验证目录存在与否
    # # 测试 1: 1MB 小文件
    # # run_test(client, 1, "小文件测试")
    
    # # # 测试 2: 100MB 大文件 (测试分片逻辑)
    # # run_test(client, 100, "大文件测试")

    # # 1. 上传一个初始文件
    # print("\n>>> 测试: 上传初始文件")
    # client.upload_file("baidu_pan_tokenrefresh.py", "/test.txt") # 假设本地有 test.txt

    # # 2. 测试复制
    # print("\n>>> 测试: 复制文件到 /test_dir/copy_test.txt")
    # client.mkdir("/test_dir")
    # client.copy("/test.txt", "/test_dir", "copy_test.txt")
    # print("复制后文件列表:", [f['name'] for f in client.list_files("/test_dir")])

    # # 3. 测试重命名
    # print("\n>>> 测试: 重命名 copy_test.txt -> renamed.txt")
    # client.rename("/test_dir/copy_test.txt", "renamed.txt")
    # print("重命名后文件列表:", [f['name'] for f in client.list_files("/test_dir")])

    # # 4. 测试移动
    # print("\n>>> 测试: 移动 renamed.txt 到根目录")
    # client.move("/test_dir/renamed.txt", "/", "moved_file.txt")
    # print("根目录文件列表:", [f['name'] for f in client.list_files("/")])

    # # 5. 测试删除
    # print("\n>>> 测试: 删除移动后的文件")
    # client.delete("/moved_file.txt")
    # print("删除后根目录:", [f['name'] for f in client.list_files("/")])

if __name__ == "__main__":
    main()