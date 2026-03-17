from lib.kv import CFKV
from lib.aes import AES
import os
import json
import urllib
import requests

general_password = os.environ.get("GENERAL_PASSWORD")

kv = CFKV()
aes = AES(general_password)

baidu_keys = aes.dec(kv.get("baidu_keys"))
# pan_keys = aes.dec(kv.get("pan_keys"))
print(baidu_keys)
# print(pan_keys)

# 1️⃣ 填入你应用的信息
CLIENT_ID = baidu_keys['AppKey']          # client_id
CLIENT_SECRET = baidu_keys['Secretkey']   # client_secret
REDIRECT_URI = "oob"    # redirect_uri

# 2️⃣ 生成授权 URL
def generate_auth_url():
    base_url = "https://openapi.baidu.com/oauth/2.0/authorize"
    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": "basic,netdisk",
        # "device_id": "可选的设备ID",
        # "state": "可选参数，防CSRF",
        # "display": "可选参数",
    }
    url = f"{base_url}?{urllib.parse.urlencode(params)}"
    return url

auth_url = generate_auth_url()
print("请在浏览器访问以下链接进行授权：")
print(auth_url)

CODE = input("请输入用户授权后获取的 code: ").strip()


# 3️⃣ 换取 access_token
def get_access_token(code):
    url = "https://openapi.baidu.com/oauth/2.0/token"
    params = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI
    }
    response = requests.get(url, params=params)
    data = response.json()

    if "access_token" in data:
        return data
    else:
        # 返回错误信息
        raise Exception(f"获取 Access Token 失败: {data}")


token_info = get_access_token(CODE)

print("获取到的 Access Token 信息:")
print(token_info)