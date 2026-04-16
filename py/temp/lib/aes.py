import os
import json
import base64
import hashlib
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class AES:

    def __init__(self, password: str):
        """
        password: 任意字符串
        通过 SHA256 生成 AES-256 key
        """
        self.key = hashlib.sha256(password.encode()).digest()
        self.aes = AESGCM(self.key)

    def enc(self, data):
        """
        加密数据
        返回 base64 字符串
        """

        if isinstance(data, dict):
            data = json.dumps(data)

        if isinstance(data, str):
            data = data.encode()

        nonce = os.urandom(12)

        cipher = self.aes.encrypt(nonce, data, None)

        payload = nonce + cipher

        return base64.b64encode(payload).decode()

    def dec(self, data):
        """
        解密 base64 数据
        """

        payload = base64.b64decode(data)

        nonce = payload[:12]
        cipher = payload[12:]

        plain = self.aes.decrypt(nonce, cipher, None)

        try:
            return json.loads(plain.decode())
        except:
            return plain.decode()