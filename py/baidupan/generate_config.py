from lib.kv import CFKV
from lib.aes import AES
import os
import json
import urllib
import requests

general_password = os.environ.get("GENERAL_PASSWORD")

kv = CFKV()
aes = AES(general_password)
baidu_keys = aes.dec(kv.get("pan_keys"))
print(baidu_keys)

general_password = os.environ.get("GENERAL_PASSWORD")

config = {
  "baidu_access_token": baidu_keys['access_token'],
  "root_dir": "/apps/data/web",
  "users": [
    {
      "username": "feng1",
      "password": "feng1" 
    }
  ],
  "temp_dir": "./temp_uploads",
  "cache_dir": "./local_cache",
  "local_cache_limit": 21474836480,
  "local_file_threshold": 10485760,
  "secret_key": general_password
}

with open("config.json", "w") as f:
    json.dump(config, f, indent=4)