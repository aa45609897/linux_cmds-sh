import os
import json
import time
import requests
from lib.aes import AES
from lib.kv import CFKV

# ----------------------------- 初始化与密钥获取 -----------------------------
aes = AES("Fengguohao1.")
kv = CFKV()

deepseek_raw = kv.get("deepseek_keys")
if deepseek_raw is None:
    raise ValueError("未从 KV 中获取到 deepseek_keys")

deepseek_keys = aes.dec(deepseek_raw)
if isinstance(deepseek_keys, bytes):
    deepseek_keys = deepseek_keys.decode("utf-8")
if isinstance(deepseek_keys, str):
    deepseek_keys = json.loads(deepseek_keys)

API_KEY = deepseek_keys.get("DEEPSEEK_API_KEY")
if not API_KEY:
    raise ValueError("未找到 DEEPSEEK_API_KEY")

API_URL = "https://api.deepseek.com/v1/chat/completions"


# ----------------------------- 翻译函数 -----------------------------
def translate_text(text: str, text_type: str = "description") -> str:
    """调用 DeepSeek API 翻译文本，text_type 用于区分提示词风格"""
    if not text or not text.strip():
        return ""

    if text_type == "name":
        prompt = f"请将以下英文物品名称翻译成中文，只输出中文翻译，不要有任何额外解释或标点：\n{text}"
    else:   # description / explanation 都用描述类提示
        prompt = f"请将以下英文描述翻译成中文，只输出中文翻译：\n{text}"

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 500
    }

    try:
        resp = requests.post(API_URL, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        result = resp.json()
        translation = result["choices"][0]["message"]["content"].strip()
        return translation
    except Exception as e:
        print(f"[错误] 翻译失败 ({text_type}): {text[:50]}... 错误: {e}")
        return text   # 失败时保留原文


# ----------------------------- 处理单个 JSON 文件 -----------------------------
def process_one_file(input_path: str, output_dir: str) -> None:
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        print(f"跳过 {input_path}：顶层不是字典结构")
        return

    new_data = {}
    for orig_name, item_info in data.items():
        if not isinstance(item_info, dict):
            new_data[orig_name] = item_info
            continue

        # 翻译 Description 字段（若存在）
        if "Description" in item_info and item_info["Description"]:
            item_info["Description"] = translate_text(item_info["Description"], "description")
            time.sleep(0.3)

        # 翻译 Explanation 字段（若存在）
        if "Explanation" in item_info and item_info["Explanation"]:
            item_info["Explanation"] = translate_text(item_info["Explanation"], "description")
            time.sleep(0.3)

        # 翻译物品名称，构造新键名
        chinese_name = translate_text(orig_name, "name")
        time.sleep(0.3)
        new_key = f"{orig_name} ({chinese_name})"
        new_data[new_key] = item_info

    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, os.path.basename(input_path))
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(new_data, f, ensure_ascii=False, indent=2)
    print(f"已完成: {input_path} -> {out_path}")


# ----------------------------- 主函数 -----------------------------
def main():
    target_dir = input("请输入要扫描的 JSON 文件目录: ").strip()
    if not os.path.isdir(target_dir):
        print("目录不存在，请检查路径")
        return

    output_root = os.path.join(target_dir, "translated")

    for root, _, files in os.walk(target_dir):
        if output_root in root or root.startswith(output_root):
            continue
        for file in files:
            if not file.lower().endswith(".json"):
                continue
            full_path = os.path.join(root, file)
            rel_dir = os.path.relpath(root, target_dir)
            dest_dir = os.path.join(output_root, rel_dir) if rel_dir != "." else output_root
            process_one_file(full_path, dest_dir)


if __name__ == "__main__":
    main()