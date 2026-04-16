import hashlib
import sys
import os

def verify_sha256(checksum_file):
    # 读取 .sha256 文件
    with open(checksum_file, 'r') as f:
        line = f.readline().strip()
    # 解析哈希值和文件名（格式：hash  filename）
    parts = line.split()
    if len(parts) < 2:
        print("Invalid .sha256 file format")
        return False
    expected_hash = parts[0]
    filename = parts[1]
    # 确保文件存在
    if not os.path.exists(filename):
        print(f"File '{filename}' not found")
        return False
    # 计算实际哈希值（分块读取）
    sha256 = hashlib.sha256()
    with open(filename, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)
    actual_hash = sha256.hexdigest()
    # 比较
    if actual_hash == expected_hash:
        print("OK: SHA256 matches")
        return True
    else:
        print("FAIL: SHA256 does not match")
        print(f"Expected: {expected_hash}")
        print(f"Actual:   {actual_hash}")
        return False

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python verify_sha256.py <checksum_file>")
        sys.exit(1)
    success = verify_sha256(sys.argv[1])
    sys.exit(0 if success else 1)