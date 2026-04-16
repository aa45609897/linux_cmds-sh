import requests


class CFKV:
    def __init__(self, account_id = "8d52970d4e9bc5878c178ac288ec690e", namespace_id = "4744bd02709946fba0b2215077f64f4b", api_token = "4g8RPRr-GBEVNI7Whe0LFo7EwjjXuIUkUoWud3_B"):
        self.account_id = account_id
        self.namespace_id = namespace_id
        self.api_token = api_token

        self.base_url = (
            f"https://api.cloudflare.com/client/v4/accounts/"
            f"{account_id}/storage/kv/namespaces/{namespace_id}"
        )

        self.headers = {
            "Authorization": f"Bearer {api_token}"
        }

    def set(self, key, value):
        """写入 KV"""
        url = f"{self.base_url}/values/{key}"

        r = requests.put(
            url,
            headers={**self.headers, "Content-Type": "text/plain"},
            data=value
        )

        return r.json()

    def get(self, key):
        """读取 KV"""
        url = f"{self.base_url}/values/{key}"

        r = requests.get(url, headers=self.headers)

        if r.status_code == 200:
            return r.text
        return None

    def delete(self, key):
        """删除 KV"""
        url = f"{self.base_url}/values/{key}"

        r = requests.delete(url, headers=self.headers)

        return r.json()

    def list(self, prefix=None, limit=1000):
        """列出 KV keys"""
        url = f"{self.base_url}/keys"

        params = {
            "limit": limit
        }

        if prefix:
            params["prefix"] = prefix

        r = requests.get(url, headers=self.headers, params=params)

        return r.json()