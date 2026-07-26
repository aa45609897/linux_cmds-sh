import json
import shutil
from pathlib import Path

# ====== 配置区域 ======
# 请根据实际情况修改 DB_ROOT 路径
# 如果脚本放在 py/translate 目录下，db 也在同一目录，使用 "./db"
DB_ROOT = Path("./db")
SOURCE_DIRS = ["01_Variants", "02_Items"]   # 只处理这两个目录
# ====================

def revert_item_name(full_name: str):
    """
    如果名称格式为 "原英文名 (中文)"，则返回原英文名；
    否则返回 None（表示无需修改）
    """
    if " (" in full_name and full_name.endswith(")"):
        # 提取最后一个 " (" 之前的部分
        orig_eng = full_name.rsplit(" (", 1)[0]
        return orig_eng
    return None

def process_json_file(file_path: Path, backup=True):
    """处理单个 JSON 文件：将顶层键名还原为纯英文"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"  读取失败 {file_path.name}: {e}")
        return False

    new_data = {}
    changed = False
    for key, value in data.items():
        new_key = revert_item_name(key)
        if new_key is not None:
            new_data[new_key] = value
            changed = True
            print(f"  重命名: {key} -> {new_key}")
        else:
            new_data[key] = value

    if not changed:
        print(f"  无需修改: {file_path.name}")
        return False

    # 备份原文件
    if backup:
        backup_path = file_path.with_suffix(file_path.suffix + ".bak")
        shutil.copy2(file_path, backup_path)
        print(f"  已备份: {backup_path.name}")

    # 写回新 JSON（保持格式美观）
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(new_data, f, ensure_ascii=False, indent=2)
    print(f"  已更新: {file_path.name}")
    return True

def main():
    print("正在将 01_Variants 和 02_Items 中的中文名改回原英文名...")
    total_processed = 0

    for src_dir in SOURCE_DIRS:
        src_path = DB_ROOT / src_dir
        if not src_path.exists():
            print(f"目录不存在: {src_path}")
            continue
        print(f"\n处理目录: {src_dir}")
        for json_file in src_path.glob("*.json"):
            if process_json_file(json_file, backup=True):
                total_processed += 1

    print(f"\n完成！共处理了 {total_processed} 个 JSON 文件。")
    print("备份文件扩展名为 .bak，如需恢复请删除原文件并重命名 .bak 文件。")

if __name__ == "__main__":
    main()