from lib.aes import AES
from lib.kv import CFKV
import os

aes = AES(os.getenv("GENERAL_PASSWORD"))
kv= CFKV()

deepseek_keys = aes.dec(kv.get("deepseek_keys"))

# 获取配置
api_key = deepseek_keys['DEEPSEEK_API_KEY']
url = deepseek_keys['DEEPSEEK_API_URL']
print(api_key)
print(url)

import os
import json
from openai import OpenAI

# 初始化 DeepSeek 客户端（兼容 OpenAI 接口）
client = OpenAI(
    api_key=api_key,  # 从环境变量读取 API Key
    base_url="https://api.deepseek.com/v1"       # DeepSeek API 地址
)

def semantic_enhancement_with_llm(original_scene, trigger_element, num_versions=3):
    """
    使用 DeepSeek 大模型进行语义增强。
    
    参数:
        original_scene (str): 原始场景描述（英文或中文均可）
        trigger_element (str): 触发元素（如“涂鸦”）
        num_versions (int): 生成的描述版本数量，默认3
    
    返回:
        list: 包含 num_versions 个增强描述的列表
    """
    
    # 构造系统指令，明确任务
    system_prompt = """你是一个场景描述增强助手。你的任务是在不丢失原始场景核心信息的前提下，自然地将指定的触发元素融入场景，生成多个不同风格、生动具体的描述版本。所有输出必须是中文。"""
    
    # 构造用户提示，给出具体要求
    user_prompt = f"""原始场景描述: "{original_scene}"
触发元素: "{trigger_element}"

请完成以下任务：
在保持原始场景信息（如街道、停着的车、行人等）的前提下，自然地融入触发元素“{trigger_element}”，生成 {num_versions} 个不同版本的场景描述。

要求：
1. 每个版本都要包含原始场景的所有关键信息（停着的车、行人、街道）。
2. 触发元素“{trigger_element}”必须自然出现在描述中，可以描述其位置、样式、与环境的互动等。
3. 三个版本应在语言风格、侧重点或叙事角度上有所区别（例如一个侧重视觉冲击，一个侧重氛围营造，一个侧重故事感）。
4. 全部使用中文输出。

请直接输出 {num_versions} 个版本，每个版本占一行，以“版本1：”开头，依次类推。"""
    
    # 调用 DeepSeek 模型
    response = client.chat.completions.create(
        model="deepseek-chat",  # 使用 DeepSeek 对话模型
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.8,         # 适当提高温度增加多样性
        max_tokens=500,
        top_p=0.95,
        frequency_penalty=0.3,
        presence_penalty=0.3
    )
    
    # 提取模型输出
    output_text = response.choices[0].message.content.strip()
    
    # 解析输出，按行分割并提取每个版本
    versions = []
    lines = output_text.split('\n')
    for line in lines:
        if line.startswith(('版本', 'Version')) and '：' in line:
            # 提取版本号后的内容
            content = line.split('：', 1)[1].strip()
            versions.append(content)
        elif line.strip() and not versions:  # 如果还没找到版本标识，可能模型直接输出列表
            # 简单处理：每行作为一个版本
            versions.append(line.strip())
    
    # 如果解析到的版本数不足，尝试按空行分割
    if len(versions) < num_versions:
        # 按连续空行分割段落
        paragraphs = [p.strip() for p in output_text.split('\n\n') if p.strip()]
        if len(paragraphs) >= num_versions:
            versions = paragraphs[:num_versions]
    
    # 确保返回指定数量的版本（若不足则用占位符）
    while len(versions) < num_versions:
        versions.append("（生成版本不足，请重试）")
    
    return versions[:num_versions]

if __name__ == "__main__":
    # 设置你的 API Key（建议通过环境变量设置）
    # os.environ["DEEPSEEK_API_KEY"] = "your-api-key-here"
    
    original_scene = "A street with parked cars and pedestrians walking"
    trigger = "涂鸦"
    
    print("原始场景:", original_scene)
    print("触发元素:", trigger)
    print("\n正在调用 DeepSeek 生成增强描述...\n")
    
    try:
        descriptions = semantic_enhancement_with_llm(original_scene, trigger, num_versions=3)
        print("增强后的三个版本描述：")
        for i, desc in enumerate(descriptions, 1):
            print(f"版本{i}: {desc}")
    except Exception as e:
        print(f"调用 API 时出错: {e}")
        print("请确保已设置 DEEPSEEK_API_KEY 环境变量，并且网络可访问 DeepSeek API。")