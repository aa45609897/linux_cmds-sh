import requests
import os
import json
import hashlib
from typing import List, Dict

class BaiduPanClient:
    def __init__(self, access_token: str, root_dir: str = "/apps/data"):
        self.access_token = access_token
        self.root_dir = root_dir
        self.api_base = "https://pan.baidu.com/rest/2.0/xpan"
        self.pcs_upload_url = "https://c3.pcs.baidu.com/rest/2.0/pcs/superfile2"
        
        # 默认分片大小 4MB，将在初始化时根据会员类型更新
        self.chunk_size = 4 * 1024 * 1024
        self.configure_user_limit()
        self.init_directory()
        print(f"[INIT] 系统启动，数据根目录: {self.root_dir}")

    def _get_full_path(self, relative_path: str) -> str:
        rel_path = relative_path.strip("/")
        return os.path.join(self.root_dir, rel_path).replace("\\", "/")

    def _request(self, uri: str, method: str = "GET", params: Dict = None, data: Dict = None) -> Dict:
        url = f"{self.api_base}{uri}"
        params = params or {}
        params["access_token"] = self.access_token

        try:
            if method == "GET":
                resp = requests.get(url, params=params)
            else:
                resp = requests.post(url, params=params, data=data)
            
            result = resp.json()
            
            if "errno" in result and result["errno"] != 0:
                if result["errno"] != -9:
                    raise Exception(f"API Error {result['errno']}: {result.get('errmsg', 'Unknown')}")
            return result
        except Exception as e:
            print(f"[ERROR] 请求异常: {e}")
            raise

    def configure_user_limit(self):
        """
        获取用户信息并配置分片大小
        文档参考：获取用户信息接口
        """
        print("[CONFIG] 正在获取用户信息与权限配置...")
        try:
            # 请求参数包含 vip_version=v2 以获取准确的会员类型
            res = self._request("/nas", params={"method": "uinfo", "vip_version": "v2"})
            
            vip_type = res.get("vip_type", 0)
            username = res.get("baidu_name", "未知用户")
            
            # vip_type 说明:
            # 0: 普通用户 (分片固定 4MB, 单文件上限 4GB)
            # 1: 普通会员 (分片上限 16MB, 单文件上限 10GB)
            # 2: 超级会员 (分片上限 32MB, 单文件上限 20GB)
            
            if vip_type == 0:
                self.chunk_size = 4 * 1024 * 1024
                level_name = "普通用户"
            elif vip_type == 1:
                self.chunk_size = 16 * 1024 * 1024  # 使用更大的分片提高上传效率
                level_name = "普通会员"
            elif vip_type == 2:
                self.chunk_size = 32 * 1024 * 1024
                level_name = "超级会员"
            else:
                self.chunk_size = 4 * 1024 * 1024
                level_name = "未知类型"

            print(f"[CONFIG] 用户: {username}, 等级: {level_name}")
            print(f"[CONFIG] 自动配置分片大小: {self.chunk_size // (1024*1024)}MB")

        except Exception as e:
            print(f"[WARN] 获取用户信息失败，使用默认配置(4MB): {e}")
            self.chunk_size = 4 * 1024 * 1024

    def init_directory(self):
        """
        初始化根目录 (智能版)
        修复：防止目录已存在时创建带时间戳后缀的重复目录
        """
        print(f"[INIT] 检查根目录: {self.root_dir}")
        
        try:
            # 这里不打印日志，避免刷屏
            res = self._request("/file", params={"method": "list", "dir": self.root_dir})
            files = []
            for item in res.get("list", []):
                if item["server_filename"].startswith("$"): continue
                files.append({
                    "name": item["server_filename"],
                    "size": item["size"],
                    "is_dir": item["isdir"] == 1,
                    "path": item["path"].replace(self.root_dir, ""),
                })
            print(f"[INIT] 根目录已存在，包含 {len(files)} 个文件/目录")
            if files:
                print(f"[INIT] 文件如下:")
                for f in files:
                    print(f"  - {f['name']} ({f['size']} bytes)")
            return files
        except Exception as e:
            # 如果目录不存在，可能会报错，返回空列表
                    # 2. 如果不存在，则创建
            print(f"[INIT] 根目录不存在，正在创建...")
        try:
            data = {"path": self.root_dir, "isdir": 1, "size": 0}
            self._request("/file", method="POST", params={"method": "create"}, data=data)
            print(f"[INIT] 根目录创建成功")
        except Exception as e:
            # 极端情况：并发创建时可能报错，忽略
            print(f"[INIT] 创建时发生错误 (可能已存在): {e}")
            return None

    def mkdir(self, relative_path: str):
        """
        创建目录 (改进版：自动检查是否存在)
        防止产生带时间戳的重复目录
        """
        full_path = self._get_full_path(relative_path)
        
        # 1. 检查父目录下是否已有同名目录
        parent_path = os.path.dirname(relative_path)
        dir_name = os.path.basename(relative_path)
        
        existing_files = self.list_files(parent_path)
        for f in existing_files:
            # 如果找到了同名且是目录的，直接返回，不创建
            if f['name'] == dir_name and f['is_dir']:
                # print(f"[ACTION] 目录已存在，跳过创建: {full_path}")
                return

        # 2. 如果不存在，则创建
        print(f"[ACTION] 创建目录: {full_path}")
        data = {"path": full_path, "isdir": 1, "size": 0}
        try:
            self._request("/file", method="POST", params={"method": "create"}, data=data)
        except Exception as e:
            # 如果创建时报错"目录已存在"(可能是并发导致的)，忽略错误
            pass


    def list_files(self, relative_path: str = "/") -> List[Dict]:
        """列出目录下的文件"""
        full_path = self._get_full_path(relative_path)
        try:
            # 这里不打印日志，避免刷屏
            res = self._request("/file", params={"method": "list", "dir": full_path})
            files = []
            for item in res.get("list", []):
                if item["server_filename"].startswith("$"): continue
                files.append({
                    "name": item["server_filename"],
                    "size": item["size"],
                    "is_dir": item["isdir"] == 1,
                    "path": item["path"].replace(self.root_dir, ""),
                })
            return files
        except Exception as e:
            # 如果目录不存在，可能会报错，返回空列表
            return []
    
    # ================= 重点修改 1：上传逻辑 =================
    def upload_file(self, local_path: str, remote_relative_path: str):
        full_path = self._get_full_path(remote_relative_path)
        file_size = os.path.getsize(local_path)
        
        print(f"[UPLOAD] 目标路径: {full_path}")
        
        # 1. 计算分片 MD5
        block_list = []
        with open(local_path, 'rb') as f:
            while True:
                chunk = f.read(self.chunk_size)
                if not chunk: break
                block_list.append(hashlib.md5(chunk).hexdigest())
        
        block_list_json = json.dumps(block_list)
        
        # 2. 预上传
        # 关键修改：添加 rtype=3 (文件存在时覆盖)
        pre_data = {
            "path": full_path,
            "size": file_size,
            "isdir": 0,
            "autoinit": 1,
            "block_list": block_list_json,
            "rtype": 3  # <--- 关键参数：覆盖策略
        }
        pre_result = self._request("/file", method="POST", params={"method": "precreate"}, data=pre_data)
        
        uploadid = pre_result.get("uploadid")
        if not uploadid:
            raise Exception("未获取到 uploadid")

        if pre_result.get("return_type") == 1:
            print("[UPLOAD] 预检测：秒传检测成功")
        else:
            print(f"[UPLOAD] 预检测：开始上传 (分片数: {len(block_list)})")

        # 3. 分片上传
        with open(local_path, 'rb') as f:
            for i, md5 in enumerate(block_list):
                chunk_data = f.read(self.chunk_size)
                
                upload_params = {
                    "method": "upload",
                    "access_token": self.access_token,
                    "type": "tmpfile",
                    "path": full_path,
                    "uploadid": uploadid,
                    "partseq": i
                }
                
                files = {'file': (f'part_{i}', chunk_data)}
                resp = requests.post(self.pcs_upload_url, params=upload_params, files=files)
                
                if resp.status_code != 200:
                    print(f"[WARN] 分片 {i} 上传异常: {resp.text}")
                else:
                    print(f"[UPLOAD] 分片 {i+1}/{len(block_list)} 处理完成")

        # 4. 创建文件
        # 关键修改：添加 rtype=3 (必须与 precreate 保持一致)
        create_data = {
            "path": full_path,
            "size": file_size,
            "isdir": 0,
            "uploadid": uploadid,
            "block_list": block_list_json,
            "rtype": 3  # <--- 关键参数：覆盖策略
        }
        result = self._request("/file", method="POST", params={"method": "create"}, data=create_data)
        print(f"[SUCCESS] 文件创建成功: {full_path}")
        return result

# ================= 文件管理操作 (通用接口) =================
    def _file_manager(self, opera: str, filelist: list, ondup: str = "fail"):
        """
        文件管理通用接口
        :param opera: 操作类型
        :param filelist: 操作对象列表 (具体格式因 opera 而异)
        :param ondup: 冲突处理策略
        """
        url = f"{self.api_base}/file"
        params = {
            "method": "filemanager",
            "access_token": self.access_token,
            "opera": opera
        }
        data = {
            "async": 0,  # 0表示同步执行，确保操作立即生效
            "filelist": json.dumps(filelist),
            "ondup": ondup
        }
        
        try:
            resp = requests.post(url, params=params, data=data)
            result = resp.json()
            if result.get("errno", 0) != 0:
                # 无论是失败还是异步任务，都打印信息
                print(f"[WARN] 操作 '{opera}' 返回: {result}")
            return result
        except Exception as e:
            print(f"[ERROR] 文件管理操作异常: {e}")
            raise

    def copy(self, src_relative: str, dest_relative_dir: str, new_name: str = None):
        """
        复制文件
        :param src_relative: 源文件相对路径
        :param dest_relative_dir: 目标目录相对路径
        :param new_name: 新文件名 (可选，不填则保留原名)
        """
        src_full = self._get_full_path(src_relative)
        dest_full = self._get_full_path(dest_relative_dir)
        
        # 如果未指定新名称，使用原文件名
        if not new_name:
            new_name = os.path.basename(src_full)
            
        print(f"[ACTION] 复制: {src_full} -> {dest_full}/{new_name}")
        
        # filelist 结构: [{"path":"/source", "dest":"/dest", "newname":"name"}]
        file_list = [{
            "path": src_full,
            "dest": dest_full,
            "newname": new_name
        }]
        return self._file_manager("copy", file_list, ondup="overwrite")

    def move(self, src_relative: str, dest_relative_dir: str, new_name: str = None):
        """
        移动文件
        :param src_relative: 源文件相对路径
        :param dest_relative_dir: 目标目录相对路径
        :param new_name: 新文件名 (可选)
        """
        src_full = self._get_full_path(src_relative)
        dest_full = self._get_full_path(dest_relative_dir)
        
        if not new_name:
            new_name = os.path.basename(src_full)
            
        print(f"[ACTION] 移动: {src_full} -> {dest_full}/{new_name}")
        
        file_list = [{
            "path": src_full,
            "dest": dest_full,
            "newname": new_name
        }]
        return self._file_manager("move", file_list, ondup="overwrite")

    def rename(self, src_relative: str, new_name: str):
        """
        重命名文件
        :param src_relative: 源文件相对路径
        :param new_name: 新文件名 (仅文件名，不是路径)
        """
        src_full = self._get_full_path(src_relative)
        print(f"[ACTION] 重命名: {src_full} -> {new_name}")
        
        # filelist 结构: [{"path":"/path/old", "newname":"newname"}]
        file_list = [{
            "path": src_full,
            "newname": new_name
        }]
        return self._file_manager("rename", file_list, ondup="overwrite")

    def delete(self, remote_relative_path: str):
        """
        删除文件或目录
        """
        full_path = self._get_full_path(remote_relative_path)
        print(f"[ACTION] 删除: {full_path}")
        
        # filelist 结构: ["/path/to/file"]
        file_list = [full_path]
        return self._file_manager("delete", file_list)

    def download_file(self, remote_relative_path: str, local_save_path: str):
        """
        下载文件到本地
        :param remote_relative_path: 远端相对路径
        :param local_save_path: 本地保存路径 (完整文件名)
        """
        full_path = self._get_full_path(remote_relative_path)
        print(f"[DOWNLOAD] 开始下载: {full_path} -> {local_save_path}")
        
        # 构造 PCS 下载链接
        # 推荐使用 d.pcs.baidu.com 域名，下载更稳定
        url = f"https://d.pcs.baidu.com/rest/2.0/pcs/file?method=download&access_token={self.access_token}&path={full_path}"
        
        try:
            # 流式下载，避免大文件撑爆内存
            with requests.get(url, stream=True) as r:
                # 如果状态码不是 200，尝试读取错误信息
                if r.status_code != 200:
                    error_info = r.text
                    print(f"[ERROR] 下载失败 ({r.status_code}): {error_info}")
                    raise Exception(f"下载失败: {error_info}")
                
                # 确保本地目录存在
                save_dir = os.path.dirname(local_save_path)
                if save_dir and not os.path.exists(save_dir):
                    os.makedirs(save_dir)

                # 写入文件
                with open(local_save_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8 * 1024 * 1024): # 8MB buffer
                        if chunk:
                            f.write(chunk)
            
            print(f"[SUCCESS] 下载完成")
            return True

        except Exception as e:
            print(f"[ERROR] 下载过程出错: {e}")
            raise

    # 辅助方法：获取文件信息 (可选，用于检查文件是否存在)
    def get_file_info(self, remote_relative_path: str) -> Dict:
        full_path = self._get_full_path(remote_relative_path)
        res = self._request("/file", params={"method": "list", "dir": os.path.dirname(full_path)})
        filename = os.path.basename(full_path)
        for item in res.get("list", []):
            if item["server_filename"] == filename:
                return item
        return None