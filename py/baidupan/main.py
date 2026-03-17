import os
import json
import time
import shutil
import hashlib
import secrets
from urllib.parse import quote
from datetime import datetime
from typing import Optional, List
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, Form, Cookie, Request, BackgroundTasks
from fastapi.templating import Jinja2Templates
from fastapi.responses import StreamingResponse, RedirectResponse
from sqlalchemy import create_engine, Column, Integer, String, Boolean, Float, DateTime, func
from sqlalchemy.orm import declarative_base, sessionmaker, Session
import requests

# === 1. 配置加载 ===
CONFIG_PATH = "config.json"
if not os.path.exists(CONFIG_PATH):
    print("Error: config.json not found")
    exit(1)

with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
    config = json.load(f)

# 目录配置
TEMP_DIR = config.get('temp_dir', './temp_uploads')
CACHE_DIR = config.get('cache_dir', './local_cache')
Path(TEMP_DIR).mkdir(exist_ok=True, parents=True)
Path(CACHE_DIR).mkdir(exist_ok=True, parents=True)

# === 2. 基础类定义 ===
# 假设 baidu_client.py 在同目录下，或者这里重新定义核心方法
# 为了保证代码完整性，这里重写一个精简版的客户端
from baidu_client import BaiduPanClient

# === 3. 扩展客户端 (无加密版) ===
class SimpleBaiduPanClient(BaiduPanClient):
    def upload_raw_file(self, local_raw_path: str, remote_relative_path: str):
        """
        【无加密版】直接分片上传
        """
        full_path = self._get_full_path(remote_relative_path)
        file_size = os.path.getsize(local_raw_path)
        print(f"[UPLOAD] 开始上传: {local_raw_path} ({file_size} bytes)")
        
        # 1. 计算所有分片 MD5
        block_list = []
        with open(local_raw_path, 'rb') as f:
            while True:
                chunk = f.read(self.chunk_size)
                if not chunk: break
                block_list.append(hashlib.md5(chunk).hexdigest())
        
        block_list_json = json.dumps(block_list)
        
        # 2. 预上传
        pre_data = {
            "path": full_path, "size": file_size, "isdir": 0, "autoinit": 1,
            "block_list": block_list_json, "rtype": 3
        }
        pre_result = self._request("/file", method="POST", params={"method": "precreate"}, data=pre_data)
        
        uploadid = pre_result.get("uploadid")
        if not uploadid: raise Exception("预上传失败")
            
        print(f"[UPLOAD] Precreate OK. ID: {uploadid}, Chunks: {len(block_list)}")

        # 3. 上传分片
        with open(local_raw_path, 'rb') as f:
            for i, md5 in enumerate(block_list):
                chunk = f.read(self.chunk_size)
                
                upload_params = {
                    "method": "upload", "access_token": self.access_token,
                    "type": "tmpfile", "path": full_path,
                    "uploadid": uploadid, "partseq": i
                }
                files = {'file': (f'part_{i}', chunk)}
                resp = requests.post(self.pcs_upload_url, params=upload_params, files=files)
                if resp.status_code != 200:
                    raise Exception(f"分片 {i} 上传失败: {resp.text}")
                print(f"[UPLOAD] Chunk {i+1}/{len(block_list)} done.")

        # 4. 创建文件
        create_data = {
            "path": full_path, "size": file_size, "isdir": 0,
            "uploadid": uploadid, "block_list": block_list_json, "rtype": 3
        }
        self._request("/file", method="POST", params={"method": "create"}, data=create_data)
        print(f"[SUCCESS] 文件创建成功: {full_path}")
        return True

    def download_stream(self, remote_relative_path: str, local_cache_path: str):
        """
        【无加密版】流式下载并缓存
        """
        full_path = self._get_full_path(remote_relative_path)
        url = f"https://d.pcs.baidu.com/rest/2.0/pcs/file?method=download&access_token={self.access_token}&path={full_path}"
        
        with requests.get(url, stream=True) as r:
            if r.status_code != 200:
                raise Exception(f"下载失败: {r.status_code}")
            
            Path(os.path.dirname(local_cache_path)).mkdir(parents=True, exist_ok=True)
            with open(local_cache_path, 'wb') as f_cache:
                for chunk in r.iter_content(chunk_size=8*1024*1024):
                    if chunk:
                        f_cache.write(chunk) # 写入缓存
                        yield chunk # 流式返回

# === 4. 全局实例与数据库 ===
baidu_client = SimpleBaiduPanClient(
    access_token=config['baidu_access_token'],
    root_dir=config['root_dir']
)

Base = declarative_base()

class FileRecord(Base):
    __tablename__ = 'files'
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String)
    virtual_path = Column(String, unique=True, index=True)
    size = Column(Integer)
    location = Column(String) # 'local' 或 'cloud'
    baidu_path = Column(String, nullable=True)
    last_access = Column(Float, default=time.time)
    is_dir = Column(Boolean, default=False)

class UploadTask(Base):
    __tablename__ = 'upload_tasks'
    id = Column(Integer, primary_key=True)
    task_id = Column(String, unique=True)
    filename = Column(String)
    target_path = Column(String)
    total_size = Column(Integer)
    uploaded_size = Column(Integer, default=0)
    status = Column(String, default='pending')

class UserDB(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True)
    password_hash = Column(String)

engine = create_engine('sqlite:///./cloud_storage.db')
Base.metadata.create_all(bind=engine)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# === 5. 辅助函数 ===
def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

def hash_password(p: str): return hashlib.sha256(p.encode()).hexdigest()

def init_admin_users():
    db = SessionLocal()
    for u in config.get('users', []):
        if not db.query(UserDB).filter(UserDB.username == u['username']).first():
            db.add(UserDB(username=u['username'], password_hash=hash_password(u['password'])))
    db.commit()
    db.close()

init_admin_users()

def get_current_user(request: Request, db: Session = Depends(get_db)):
    session = request.cookies.get("session")
    if not session: return None
    try:
        username, sign = session.split(":")
        user = db.query(UserDB).filter(UserDB.username == username).first()
        if user and sign == user.password_hash[:10]: return username
    except: pass
    return None

# === 6. FastAPI App ===
app = FastAPI()
templates = Jinja2Templates(directory="templates")

# === 页面路由 ===
@app.get("/")
async def index(request: Request, user: str = Depends(get_current_user)):
    return templates.TemplateResponse("index.html", {"request": request, "user": user})

# === API 路由 ===

@app.post("/api/login")
async def login(request: Request, username: str = Form(), password: str = Form(), db: Session = Depends(get_db)):
    user = db.query(UserDB).filter(UserDB.username == username).first()
    if user and user.password_hash == hash_password(password):
        response = RedirectResponse(url="/", status_code=302)
        response.set_cookie(key="session", value=f"{username}:{user.password_hash[:10]}")
        return response
    return RedirectResponse(url="/?error=1", status_code=302)

@app.get("/api/logout")
async def logout():
    response = RedirectResponse(url="/")
    response.delete_cookie("session")
    return response

@app.get("/api/list")
async def list_files(path: str = "/", db: Session = Depends(get_db)):
    norm_path = "/" + path.strip("/")
    items = db.query(FileRecord).filter(FileRecord.virtual_path.startswith(norm_path)).all()
    result = []
    for item in items:
        if os.path.dirname(item.virtual_path) == norm_path:
             result.append({
                "name": item.filename, "path": item.virtual_path, "size": item.size,
                "location": item.location, "is_dir": item.is_dir,
                "mtime": datetime.fromtimestamp(item.last_access).strftime("%Y-%m-%d %H:%M")
            })
    return {"files": result}

@app.get("/api/folders")
async def get_folders(db: Session = Depends(get_db)):
    folders = db.query(FileRecord).filter(FileRecord.is_dir == True).all()
    return [{"path": f.virtual_path, "name": f.filename} for f in folders]

# === 小文件/简单上传接口 ===
@app.post("/api/upload")
async def upload_file(
    file: UploadFile = File(...), 
    path: str = Form(default="/"), 
    user: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not user: raise HTTPException(status_code=401, detail="未登录")
    
    file.file.seek(0, os.SEEK_END)
    file_size = file.file.tell()
    file.file.seek(0)
    
    threshold = config.get('local_file_threshold', 10 * 1024 * 1024)
    local_limit = config.get('local_cache_limit', 1024*1024*1024)
    
    virtual_path = os.path.join(path, file.filename).replace("\\", "/")
    
    # 重名覆盖逻辑
    existing = db.query(FileRecord).filter(FileRecord.virtual_path == virtual_path).first()
    if existing:
        if existing.location == 'local':
            try: os.remove(os.path.join(CACHE_DIR, f"{existing.id}.dat"))
            except: pass
        db.delete(existing)
        db.commit()

    target_location = 'cloud'
    if file_size <= threshold:
        used_space = db.query(func.sum(FileRecord.size)).filter(FileRecord.location == 'local').scalar() or 0
        if used_space + file_size <= local_limit:
            target_location = 'local'
    
    new_record = FileRecord(
        filename=file.filename, virtual_path=virtual_path,
        size=file_size, location=target_location, last_access=time.time()
    )
    db.add(new_record)
    db.commit()
    db.refresh(new_record)
    
    try:
        if target_location == 'local':
            save_path = os.path.join(CACHE_DIR, f"{new_record.id}.dat")
            with open(save_path, 'wb') as f:
                shutil.copyfileobj(file.file, f)
        else:
            # 小文件直接上传云端
            temp_path = os.path.join(TEMP_DIR, f"simple_{new_record.id}.tmp")
            with open(temp_path, 'wb') as f:
                shutil.copyfileobj(file.file, f)
            try:
                baidu_client.upload_raw_file(temp_path, virtual_path)
                new_record.baidu_path = virtual_path
                db.commit()
            finally:
                if os.path.exists(temp_path): os.remove(temp_path)
    except Exception as e:
        db.delete(new_record)
        db.commit()
        raise HTTPException(status_code=500, detail=str(e))
        
    return {"success": True, "location": target_location}

# === 分片上传接口 ===
@app.post("/api/upload/init")
async def upload_init(filename: str = Form(), size: int = Form(), path: str = Form("/"), user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user: raise HTTPException(401)
    task_id = secrets.token_urlsafe(8)
    temp_file_path = os.path.join(TEMP_DIR, f"{task_id}.tmp")
    Path(temp_file_path).touch()
    
    new_task = UploadTask(task_id=task_id, filename=filename, target_path=path, total_size=size)
    db.add(new_task)
    db.commit()
    return {"upload_id": task_id}

@app.post("/api/upload/chunk")
async def upload_chunk(upload_id: str = Form(), start_byte: int = Form(), file: UploadFile = File(...), user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user: raise HTTPException(401)
    task = db.query(UploadTask).filter(UploadTask.task_id == upload_id).first()
    if not task: raise HTTPException(404)
    
    temp_file_path = os.path.join(TEMP_DIR, f"{upload_id}.tmp")
    data = await file.read()
    
    with open(temp_file_path, 'r+b') as f:
        f.seek(start_byte)
        f.write(data)
        
    task.uploaded_size = start_byte + len(data)
    if task.uploaded_size >= task.total_size:
        task.status = 'ready'
    db.commit()
    return {"success": True, "size": len(data)}

@app.post("/api/upload/finish")
async def upload_finish(upload_id: str = Form(), user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user: raise HTTPException(401)
    task = db.query(UploadTask).filter(UploadTask.task_id == upload_id).first()
    if not task or task.status != 'ready': raise HTTPException(400, "任务未完成")
    
    temp_file_path = os.path.join(TEMP_DIR, f"{upload_id}.tmp")
    virtual_path = os.path.join(task.target_path, task.filename).replace("\\", "/")
    
    threshold = config.get('local_file_threshold', 10*1024*1024)
    
    existing = db.query(FileRecord).filter(FileRecord.virtual_path == virtual_path).first()
    if existing:
        if existing.location == 'local': os.remove(os.path.join(CACHE_DIR, f"{existing.id}.dat"))
        db.delete(existing)
        db.commit()

    if task.total_size <= threshold:
        new_record = FileRecord(filename=task.filename, virtual_path=virtual_path, size=task.total_size, location='local')
        db.add(new_record); db.commit(); db.refresh(new_record)
        shutil.move(temp_file_path, os.path.join(CACHE_DIR, f"{new_record.id}.dat"))
    else:
        try:
            baidu_client.upload_raw_file(temp_file_path, virtual_path)
            new_record = FileRecord(filename=task.filename, virtual_path=virtual_path, size=task.total_size, location='cloud', baidu_path=virtual_path)
            db.add(new_record); db.commit()
            os.remove(temp_file_path)
        except Exception as e:
            raise HTTPException(500, f"上传失败: {e}")

    task.status = 'done'; db.commit()
    return {"success": True}

# === 下载逻辑 (智能缓存版) ===
@app.get("/api/download")
async def download_file(path: str, db: Session = Depends(get_db)):
    record = db.query(FileRecord).filter(FileRecord.virtual_path == path).first()
    if not record: raise HTTPException(404)

    record.last_access = time.time()
    db.commit()
    local_path = os.path.join(CACHE_DIR, f"{record.id}.dat")
    
    # URL 编码文件名
    encoded_filename = quote(record.filename)
    headers = {'Content-Disposition': f"attachment; filename*=UTF-8''{encoded_filename}"}

    if record.location == 'local' and os.path.exists(local_path):
        # 本地文件直接流式发送
        def iter_local():
            with open(local_path, 'rb') as f:
                yield from f
        return StreamingResponse(iter_local(), media_type='application/octet-stream', headers=headers)
    else:
        # 云端文件处理
        # 获取缓存阈值，默认 10MB
        threshold = config.get('local_file_threshold', 10 * 1024 * 1024)
        
        # 构造下载URL
        remote_path = baidu_client._get_full_path(record.baidu_path or record.virtual_path)
        url = f"https://d.pcs.baidu.com/rest/2.0/pcs/file?method=download&access_token={baidu_client.access_token}&path={remote_path}"

        # === 逻辑分支：大文件不缓存，小文件缓存 ===
        if record.size > threshold:
            # 情况 A: 大文件 (>10MB) - 直接流式转发，不落盘
            print(f"[DOWNLOAD] 大文件直接下载 (不缓存): {record.filename}")
            
            def stream_large_file():
                with requests.get(url, stream=True) as r:
                    if r.status_code != 200:
                        raise Exception("下载失败")
                    for chunk in r.iter_content(chunk_size=8*1024*1024):
                        if chunk:
                            yield chunk
            
            return StreamingResponse(stream_large_file(), media_type='application/octet-stream', headers=headers)
        
        else:
            # 情况 B: 小文件 (<=10MB) - 边下载边缓存
            print(f"[DOWNLOAD] 小文件下载并缓存: {record.filename}")
            cache_path = os.path.join(CACHE_DIR, f"{record.id}.cache")
            
            def stream_and_cache():
                try:
                    with requests.get(url, stream=True) as r:
                        if r.status_code != 200:
                            raise Exception("下载失败")
                        
                        # 打开临时文件写入
                        with open(cache_path, 'wb') as f:
                            for chunk in r.iter_content(chunk_size=8*1024*1024):
                                if chunk:
                                    f.write(chunk) # 写入缓存
                                    yield chunk    # 发送给用户
                    
                    # 下载完成，原子性操作：重命名为正式文件
                    if os.path.exists(cache_path):
                        os.rename(cache_path, local_path)
                        # 更新数据库记录为本地文件
                        record.location = 'local'
                        db.commit()
                        print(f"[DOWNLOAD] 缓存完成，已转为本地文件: {record.filename}")
                        
                except Exception as e:
                    print(f"[ERROR] 下载或缓存失败: {e}")
                    # 清理不完整的临时文件
                    if os.path.exists(cache_path):
                        try: os.remove(cache_path)
                        except: pass
                    raise

            return StreamingResponse(stream_and_cache(), media_type='application/octet-stream', headers=headers)
        
# === 新增：本地文件转存云端 ===
@app.post("/api/local_to_cloud")
async def local_to_cloud(path: str = Form(), user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    将本地缓存的文件上传到云端，并删除本地副本
    """
    if not user: raise HTTPException(401)
    record = db.query(FileRecord).filter(FileRecord.virtual_path == path).first()
    if not record: raise HTTPException(404, "文件不存在")
    if record.location != 'local': raise HTTPException(400, "该文件不在本地")
    
    local_file = os.path.join(CACHE_DIR, f"{record.id}.dat")
    if not os.path.exists(local_file):
        raise HTTPException(404, "本地物理文件丢失")
        
    try:
        print(f"[MIGRATE] 正在上传本地文件到云端: {record.filename}")
        # 1. 上传到百度云
        baidu_client.upload_raw_file(local_file, record.virtual_path)
        
        # 2. 更新数据库记录
        record.location = 'cloud'
        record.baidu_path = record.virtual_path
        db.commit()
        
        # 3. 删除本地文件
        os.remove(local_file)
        print(f"[MIGRATE] 成功，已删除本地副本")
        return {"success": True}
        
    except Exception as e:
        raise HTTPException(500, f"上传失败: {e}")

# === 文件管理 ===
@app.post("/api/mkdir")
async def mk_dir(path: str = Form(), name: str = Form(), user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user: raise HTTPException(401)
    full_path = os.path.join(path, name).replace("\\", "/")
    if db.query(FileRecord).filter(FileRecord.virtual_path == full_path).first():
        return {"success": False, "msg": "目录已存在"}
    db.add(FileRecord(filename=name, virtual_path=full_path, is_dir=True, location='local', size=0))
    db.commit()
    return {"success": True}

@app.post("/api/rename")
async def rename_file(path: str = Form(), new_name: str = Form(), user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user: raise HTTPException(401)
    record = db.query(FileRecord).filter(FileRecord.virtual_path == path).first()
    if not record: raise HTTPException(404)
    
    parent = os.path.dirname(path)
    new_path = os.path.join(parent, new_name).replace("\\", "/")
    if db.query(FileRecord).filter(FileRecord.virtual_path == new_path).first():
        raise HTTPException(400, "名称已存在")

    record.filename = new_name
    record.virtual_path = new_path
    db.commit()
    return {"success": True}

@app.post("/api/delete")
async def delete_file(path: str = Form(), user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user: raise HTTPException(401)
    record = db.query(FileRecord).filter(FileRecord.virtual_path == path).first()
    if not record: raise HTTPException(404)

    if record.location == 'cloud':
        try: baidu_client.delete(record.baidu_path)
        except: pass # 忽略云端删除错误
    elif record.location == 'local':
        local_file = os.path.join(CACHE_DIR, f"{record.id}.dat")
        if os.path.exists(local_file): os.remove(local_file)
    
    db.delete(record); db.commit()
    return {"success": True}

@app.post("/api/move")
async def move_file(src: str = Form(), dest_dir: str = Form(), user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user: raise HTTPException(401)
    record = db.query(FileRecord).filter(FileRecord.virtual_path == src).first()
    if not record: raise HTTPException(404)

    new_path = os.path.join(dest_dir, record.filename).replace("\\", "/")
    if db.query(FileRecord).filter(FileRecord.virtual_path == new_path).first():
        raise HTTPException(400, "目标位置已存在")

    record.virtual_path = new_path
    db.commit()
    return {"success": True}

@app.post("/api/copy")
async def copy_file(src: str = Form(), dest_dir: str = Form(), user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user: raise HTTPException(401)
    src_record = db.query(FileRecord).filter(FileRecord.virtual_path == src).first()
    if not src_record: raise HTTPException(404)

    new_name = src_record.filename
    new_path = os.path.join(dest_dir, new_name).replace("\\", "/")
    if db.query(FileRecord).filter(FileRecord.virtual_path == new_path).first():
        new_name = f"copy_{src_record.filename}"
        new_path = os.path.join(dest_dir, new_name).replace("\\", "/")

    if src_record.location == 'local':
        src_file = os.path.join(CACHE_DIR, f"{src_record.id}.dat")
        new_record = FileRecord(filename=new_name, virtual_path=new_path, size=src_record.size, location='local')
        db.add(new_record); db.commit(); db.refresh(new_record)
        shutil.copyfile(src_file, os.path.join(CACHE_DIR, f"{new_record.id}.dat"))
    elif src_record.location == 'cloud':
        try:
            baidu_client.copy(src_record.baidu_path, dest_dir, new_name)
            new_record = FileRecord(filename=new_name, virtual_path=new_path, size=src_record.size, location='cloud', baidu_path=os.path.join(dest_dir, new_name).replace("\\", "/"))
            db.add(new_record); db.commit()
        except Exception as e:
            raise HTTPException(500, f"云端复制失败: {e}")
    return {"success": True}

# === 启动配置 ===
def create_default_favicon():
    if not os.path.exists("favicon.ico"):
        icon_base64 = "AAABAAEAEBAAAAEAIABoBAAAFgAAACgAAAAQAAAAIAAAAAEAIAAAAAAAAAQAABILAAASCwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAADzMzP/MzM/8zMz/PzMz/zMzM/8zMz//MzM///////////////////////////zMzM/8zMz/PzMz/zMzM/8zMz//MzM/////////////////////////////////8zMz/PzMz/zMzM/8zMz//MzM//////////////////////////////////MzM/zMzM/8zMz/PzMz/zMz//////////////////////////////////zMzM/8zMz/PzMz/zMzM/8zM//////////////////////////////////MzM/zMzM/8zMz/PzMz/zMz//////////////////////////////////zMzM/8zMz/PzMz/zMzM/8zM//////////////////////////////////MzM/zMzM/8zMz/PzMz/zMz//////////////////////////////////zMzM/8zMz/PzMz/zMzM/8zM//////////////////////////////////MzM/zMzM/8zMz/PzMz/zMz//////////////////////////////////zMzM//////////////////////////////////////MzM//////////////////////////////////////8zMz//////////////////////////////////////zMz//////////////////////////////////////MzM//////////////////////////////////////8zMz//////////////////////////////////////zMz//////////////////////////////////////MzM/////////////////////////////////////////////////8zMz///////////////////////////////////////////zMz///////////////////////////////////////////MzM///////////////////////////////////////////8z///////////////////////////////////////////////////M////////////////////////////////////////////////////z////////////////////////////////////////////////////8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=="
        try:
            import base64
            with open("favicon.ico", "wb") as f: f.write(base64.b64decode(icon_base64))
        except: pass

os.makedirs("templates", exist_ok=True)
create_default_favicon()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)