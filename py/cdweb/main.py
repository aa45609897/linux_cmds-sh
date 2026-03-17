# optical_disc_manager.py
# 后端服务 - 运行: python optical_disc_manager.py

from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
import subprocess
import os
import shutil
import tempfile
import re
import fcntl
import json
from pathlib import Path
from datetime import datetime
from werkzeug.utils import secure_filename

app = Flask(__name__, static_folder='static')
CORS(app)

# 配置
CACHE_DIR = Path(tempfile.gettempdir()) / 'disc_cache'
CACHE_DIR.mkdir(exist_ok=True)
UPLOAD_FOLDER = CACHE_DIR / 'uploads'
UPLOAD_FOLDER.mkdir(exist_ok=True)
app.config['UPLOAD_FOLDER'] = str(UPLOAD_FOLDER)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024 * 1024  # 50GB max

# 光驱设备
def get_cdrom_device():
    """自动检测光驱设备"""
    devices = []
    # 优先检测软链接
    for link in ['/dev/cdrom', '/dev/dvd', '/dev/sr0']:
        if os.path.exists(link):
            real_path = os.path.realpath(link)
            if real_path not in [os.path.realpath(d) for d in devices]:
                devices.append(link)
    # 扫描 sr 设备
    for i in range(10):
        dev = f'/dev/sr{i}'
        if os.path.exists(dev) and dev not in devices:
            real = os.path.realpath(dev)
            if real not in [os.path.realpath(d) for d in devices]:
                devices.append(dev)
    
    if devices:
        # 关键修改：返回真实路径而不是软链接
        return os.path.realpath(devices[0])
    return '/dev/sr0'

CDROM_DEVICE = get_cdrom_device()

def run_command(cmd, timeout=60):
    """执行命令并返回结果"""
    try:
        result = subprocess.run(
            cmd, 
            shell=True, 
            capture_output=True, 
            text=True, 
            timeout=timeout
        )
        return {
            'success': result.returncode == 0,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'returncode': result.returncode
        }
    except subprocess.TimeoutExpired:
        return {'success': False, 'error': '命令执行超时'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


import fcntl
import os

# 定义 ioctl 常量
CDROM_DRIVE_STATUS = 0x5326
CDS_NO_DISC = 1
CDS_TRAY_OPEN = 2
CDS_DRIVE_NOT_READY = 3
CDS_DISC_OK = 4

def check_disc_present():
    """检测是否有光盘 (使用 ioctl 防止触发托盘关闭)"""
    try:
        # 使用非阻塞模式打开设备
        fd = os.open(CDROM_DEVICE, os.O_RDONLY | os.O_NONBLOCK)
        # 获取驱动器状态
        result = fcntl.ioctl(fd, CDROM_DRIVE_STATUS, 0)
        os.close(fd)
        
        # 解析状态
        if result == CDS_TRAY_OPEN:
            return False  # 托盘打开
        elif result == CDS_DISC_OK:
            return True   # 有光盘
        elif result == CDS_NO_DISC:
            return False  # 无光盘
        else:
            return False  # 其他状态 (未就绪等)
            
    except Exception as e:
        # 如果权限不足或设备繁忙，回退到安全的方法
        # 检查 /proc 或 sysfs 是另一种不触发关闭的方法，这里简单处理
        return False

def get_disc_type():
    """检测光盘类型"""
    result = run_command(f'dvd+rw-mediainfo {CDROM_DEVICE} 2>&1')
    output = result['stdout'] + result['stderr']
    
    # 1. 优先解析 "Mounted Media" 行，获取最精确类型 (如 BD-R SRM, DVD+RW 等)
    # 示例: "Mounted Media:         41h, BD-R SRM"
    match = re.search(r'Mounted Media:\s+[\dA-Fa-f]+h,\s+(.+)', output)
    if match:
        media_type = match.group(1).strip()
        # 如果是 BD/DVD/CD 开头，直接返回详细类型
        if media_type.startswith(('BD', 'DVD', 'CD')):
            return media_type
    
    # 2. 后备逻辑：关键词匹配
    if 'BD' in output: return 'Blu-ray'
    if 'DVD-RW' in output or 'DVD+RW' in output: return 'DVD-RW'
    if 'DVD-R' in output or 'DVD+R' in output: return 'DVD-R'
    if 'DVD' in output: return 'DVD'
    
    # 3. CD 检测
    result2 = run_command(f'cd-info -C {CDROM_DEVICE} 2>/dev/null')
    if 'DVD' in result2['stdout']: return 'DVD'
    if 'CD' in result2['stdout']: return 'CD'
    
    return 'Unknown'

def get_disc_capacity():
    """获取光盘可用容量 (空白盘为总容量，追加盘为剩余容量)"""
    result = run_command(f'dvd+rw-mediainfo {CDROM_DEVICE} 2>&1')
    output = result['stdout'] + result['stderr']
    
    # 1. 优先解析 Free Blocks (最准确)
    # 对于追加盘，会显示剩余容量；对于空白菜，会显示总容量
    # 使用 findall 找到最后一个出现的 Free Blocks (对应最后一个可写轨道)
    matches = re.findall(r'Free Blocks:\s*(\d+)\*', output)
    if matches:
        free_blocks = int(matches[-1])
        if free_blocks > 0:
            return free_blocks * 2048
            
    # 2. 解析 Track Size (空白菜的后备方案)
    # 同样取最后一个匹配项
    matches = re.findall(r'Track Size:\s*(\d+)\*', output)
    if matches:
        return int(matches[-1]) * 2048
    
    # 3. 解析 unformatted (DVD+RW 空白菜)
    match = re.search(r'unformatted:\s*(\d+)\*', output)
    if match:
        return int(match.group(1)) * 2048
        
    # 4. 最后才用 Legacy lead-out (不准确)
    match = re.search(r'Legacy lead-out at:\s*(\d+)', output)
    if match:
        return int(match.group(1)) * 2048
        
    return None

# ==================== API 路由 ====================

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/api/status', methods=['GET'])
def get_status():
    """获取光驱状态"""
    device_exists = os.path.exists(CDROM_DEVICE)
    disc_present = check_disc_present() if device_exists else False
    
    return jsonify({
        'success': True,
        'device': CDROM_DEVICE,
        'deviceExists': device_exists,
        'discPresent': disc_present,
        'deviceReady': device_exists and disc_present
    })

@app.route('/api/disc/info', methods=['GET'])
def get_disc_info():
    """获取光盘详细信息"""
    if not check_disc_present():
        return jsonify({'success': False, 'error': '未检测到光盘'})
    
    info = {
        'device': CDROM_DEVICE,
        'type': get_disc_type(),
        'capacity': get_disc_capacity(),
        'capacityFormatted': None,
        'usedSpace': None,
        'freeSpace': None,
        'isBlank': False,
        'isWritable': False,
        'tracks': [],
        'rawOutput': ''
    }
    
    # 格式化容量
    if info['capacity']:
        capacity = info['capacity']
        if capacity > 1024**3:
            info['capacityFormatted'] = f"{capacity / (1024**3):.2f} GB"
        else:
            info['capacityFormatted'] = f"{capacity / (1024**2):.2f} MB"
    
    # 1. 先获取 dvd+rw-mediainfo 输出 (用于判断空白状态和可写性)
    result2 = run_command(f'dvd+rw-mediainfo {CDROM_DEVICE} 2>&1', timeout=30)
    dvd_info = result2.get('stdout', '') + result2.get('stderr', '')
    
    # 2. 获取 cd-info 输出
    result = run_command(f'cd-info -C {CDROM_DEVICE} 2>&1', timeout=30)
    cd_info_output = result.get('stdout', '') + result.get('stderr', '')
    
    # 合并输出
    info['rawOutput'] = cd_info_output + '\n\n--- dvd+rw-mediainfo ---\n' + dvd_info
    
    # 3. 检查是否空白盘 (精确匹配 dvd+rw-mediainfo 输出)
    if 'Disc status:           blank' in dvd_info:
        info['isBlank'] = True
    
    # 4. 检查是否可写 (增加 BD-R / BD-RE 支持)
    writable_types = ['DVD-R', 'DVD+R', 'DVD-RW', 'DVD+RW', 'CD-R', 'BD-R', 'BD-RE']
    if any(x in dvd_info for x in writable_types):
        info['isWritable'] = True
    
    # 5. 解析轨道信息 (从 cd-info 输出解析)
    track_pattern = re.compile(r'Track\s*(\d+).*?(\d+:\d+:\d+)', re.IGNORECASE)
    for match in track_pattern.finditer(cd_info_output):
        info['tracks'].append({
            'number': int(match.group(1)),
            'length': match.group(2)
        })
    
    return jsonify({
        'success': True,
        'info': info
    })

@app.route('/api/disc/eject', methods=['POST'])
def eject_disc():
    """弹出托盘"""
    data = request.json or {}
    close = data.get('close', False)
    
    if close:
        result = run_command(f'eject -t {CDROM_DEVICE}')
    else:
        result = run_command(f'eject {CDROM_DEVICE}')
    
    return jsonify({
        'success': result['success'],
        'message': '托盘已关闭' if close else '托盘已弹出',
        'output': result.get('stdout', '') + result.get('stderr', '')
    })


@app.route('/api/disc/files', methods=['GET'])
def list_disc_files():
    """列出光盘文件"""
    if not check_disc_present():
        return jsonify({'success': False, 'error': '未检测到光盘'})
    
    # 获取真实设备路径
    real_device = os.path.realpath(CDROM_DEVICE)
    
    # 1. 检查是否已经挂载
    mount_point = None
    is_already_mounted = False
    
    try:
        with open('/proc/mounts', 'r') as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 2 and parts[0] == real_device:
                    mount_point = parts[1]
                    is_already_mounted = True
                    break
    except:
        pass

    # 2. 如果未挂载，尝试挂载
    if not mount_point:
        mount_point = Path(tempfile.mkdtemp())
        
        # 使用 sudo mount 挂载
        mount_result = run_command(f"sudo mount -t udf,iso9660 -o ro {real_device} {mount_point} 2>&1")
        
        if not mount_result['success']:
            # 挂载失败，清理临时目录
            try:
                os.rmdir(mount_point)
            except:
                pass
            return jsonify({
                'success': False, 
                'error': '挂载失败: ' + mount_result.get('stderr', '未知错误，请检查sudoers配置')
            })

    try:
        files = []
        total_size = 0
        
        # 遍历文件
        for root, dirs, filenames in os.walk(mount_point):
            for filename in filenames:
                filepath = Path(root) / filename
                try:
                    size = filepath.stat().st_size
                    total_size += size
                    rel_path = filepath.relative_to(mount_point)
                    
                    files.append({
                        'name': filename,
                        'path': str(rel_path),
                        'size': size,
                        'sizeFormatted': format_size(size),
                        'isDirectory': False
                    })
                except Exception as e:
                    print(f"读取文件信息失败: {e}")
        
        return jsonify({
            'success': True,
            'files': files,
            'totalFiles': len(files),
            'totalSize': total_size,
            'totalSizeFormatted': format_size(total_size)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    finally:
        # 3. 卸载逻辑
        # 只有当是我们自己挂载的时候才卸载
        if not is_already_mounted and mount_point:
            # 使用 sudo umount 卸载
            run_command(f'sudo umount {mount_point} 2>/dev/null')
            try:
                # 删除临时目录
                if isinstance(mount_point, Path):
                    os.rmdir(mount_point)
                else:
                    os.rmdir(str(mount_point))
            except:
                pass

                
@app.route('/api/disc/download', methods=['GET'])
def download_file():
    """下载光盘上的文件"""
    file_path = request.args.get('path', '')
    
    if not file_path:
        return jsonify({'success': False, 'error': '未指定文件路径'})
    
    # 安全检查：防止路径穿越攻击
    if '..' in file_path or file_path.startswith('/'):
        return jsonify({'success': False, 'error': '无效的文件路径'})
    
    real_device = os.path.realpath(CDROM_DEVICE)
    
    # 1. 检查是否已经挂载
    mount_point = None
    is_already_mounted = False
    
    try:
        with open('/proc/mounts', 'r') as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 2 and parts[0] == real_device:
                    mount_point = parts[1]
                    is_already_mounted = True
                    break
    except:
        pass

    # 2. 如果未挂载，尝试挂载
    if not mount_point:
        mount_point = Path(tempfile.mkdtemp())
        # 使用 sudo 挂载
        mount_result = run_command(f"sudo mount -t udf,iso9660 -o ro {real_device} {mount_point} 2>&1")
        
        if not mount_result['success']:
            try:
                os.rmdir(mount_point)
            except:
                pass
            return jsonify({'success': False, 'error': '挂载失败: ' + mount_result.get('stderr', '请检查sudo权限')})

    try:
        file_full_path = Path(mount_point) / file_path
        
        if not file_full_path.exists():
            return jsonify({'success': False, 'error': '文件不存在'})
        
        # 关键步骤：先将文件复制到临时目录
        # 这样即使卸载光盘，下载也不会中断
        temp_file = Path(tempfile.mktemp())
        shutil.copy2(file_full_path, temp_file)
        
        # 发送文件
        return send_file(
            temp_file,
            as_attachment=True,
            download_name=file_full_path.name
        )
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    finally:
        # 3. 卸载逻辑
        if not is_already_mounted and mount_point:
            # 使用 sudo 卸载
            run_command(f'sudo umount {mount_point} 2>/dev/null')
            try:
                if isinstance(mount_point, Path):
                    os.rmdir(mount_point)
                else:
                    os.rmdir(str(mount_point))
            except:
                pass

@app.route('/api/disc/iso', methods=['GET'])
def create_iso():
    """创建光盘ISO镜像"""
    if not check_disc_present():
        return jsonify({'success': False, 'error': '未检测到光盘'})
    
    iso_path = CACHE_DIR / f'disc_{datetime.now().strftime("%Y%m%d_%H%M%S")}.iso'
    
    # 使用readom创建ISO
    result = run_command(f'readom dev={CDROM_DEVICE} f={iso_path} -nocorr 2>&1', timeout=600)
    
    if result['success'] and iso_path.exists():
        return send_file(
            iso_path,
            as_attachment=True,
            download_name=f'disc_{datetime.now().strftime("%Y%m%d_%H%M%S")}.iso'
        )
    else:
        return jsonify({
            'success': False, 
            'error': '创建ISO失败: ' + result.get('stderr', '未知错误')
        })

@app.route('/api/cache/list', methods=['GET'])
def list_cache():
    """列出缓存中的文件"""
    files = []
    total_size = 0
    
    for item in UPLOAD_FOLDER.iterdir():
        if item.is_file():
            size = item.stat().st_size
            total_size += size
            files.append({
                'name': item.name,
                'size': size,
                'sizeFormatted': format_size(size),
                'modified': datetime.fromtimestamp(item.stat().st_mtime).isoformat()
            })
    
    return jsonify({
        'success': True,
        'files': files,
        'totalFiles': len(files),
        'totalSize': total_size,
        'totalSizeFormatted': format_size(total_size)
    })

@app.route('/api/cache/upload', methods=['POST'])
def upload_to_cache():
    """上传文件到缓存 (支持目录结构)"""
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': '没有文件'})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'error': '没有选择文件'})
    
    # 获取相对路径 (如果浏览器支持 webkitdirectory)
    # 这里的 filename 实际上包含了目录路径，例如 "folder/file.txt"
    relative_path = file.filename
    
    # 安全处理路径：防止路径穿越
    relative_path = relative_path.replace('\\', '/') # 统一斜杠
    parts = relative_path.split('/')
    # 过滤掉危险的路径部分
    safe_parts = [p for p in parts if p not in ('', '.', '..')]
    
    if not safe_parts:
        return jsonify({'success': False, 'error': '无效的文件路径'})
    
    # 构建保存路径
    filepath = UPLOAD_FOLDER / Path(*safe_parts)
    
    # 确保父目录存在
    filepath.parent.mkdir(parents=True, exist_ok=True)
    
    # 如果文件已存在，重命名
    if filepath.exists():
        stem = filepath.stem
        suffix = filepath.suffix
        filepath = filepath.parent / f"{stem}_{datetime.now().strftime('%H%M%S')}{suffix}"
    
    try:
        file.save(filepath)
        return jsonify({
            'success': True,
            'message': '文件已上传',
            'file': {
                'name': safe_parts[-1], # 只显示文件名
                'path': str(Path(*safe_parts)), # 显示相对路径
                'size': filepath.stat().st_size,
                'sizeFormatted': format_size(filepath.stat().st_size)
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': f'保存失败: {str(e)}'})

@app.route('/api/cache/delete', methods=['POST'])
def delete_from_cache():
    """从缓存删除文件"""
    data = request.json
    filename = data.get('filename', '')
    
    if not filename:
        return jsonify({'success': False, 'error': '未指定文件名'})
    
    filepath = UPLOAD_FOLDER / secure_filename(filename)
    
    if filepath.exists() and filepath.is_file():
        filepath.unlink()
        return jsonify({'success': True, 'message': '文件已删除'})
    
    return jsonify({'success': False, 'error': '文件不存在'})

@app.route('/api/cache/clear', methods=['POST'])
def clear_cache():
    """清空缓存"""
    try:
        for item in UPLOAD_FOLDER.iterdir():
            if item.is_file():
                item.unlink()
        return jsonify({'success': True, 'message': '缓存已清空'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/burn/check', methods=['GET'])
def check_burn_ready():
    """检查刻录准备状态"""
    issues = []
    
    # 检查光驱
    if not os.path.exists(CDROM_DEVICE):
        issues.append('光驱设备不存在')
    
    # 检查光盘
    if not check_disc_present():
        issues.append('未检测到光盘')
    else:
        # 获取详细信息
        info_result = run_command(f'dvd+rw-mediainfo {CDROM_DEVICE} 2>&1')
        output = info_result.get('stdout', '') + info_result.get('stderr', '')
        
        # 1. 如果是空白盘，绝对是可写的（即使 Book Type 是 DVD-ROM）
        is_blank = 'Disc status:           blank' in output
        
        # 2. 检查介质是否属于可写类型 (检查 Mounted Media 行)
        # 匹配: DVD-R, DVD+R, DVD-RW, DVD+RW, BD-R, BD-RE, CD-R
        writable_keywords = ['DVD-R', 'DVD+R', 'DVD-RW', 'DVD+RW', 'BD-R', 'BD-RE', 'CD-R']
        is_writable_media = any(keyword in output for keyword in writable_keywords)
        
        # 如果既不是空白盘，也不是可写介质，才报错
        if not is_blank and not is_writable_media:
            issues.append('当前光盘不可写入（只读光盘）')
    
    # 检查缓存文件
    cache_files = list(UPLOAD_FOLDER.iterdir())
    if not any(f.is_file() for f in cache_files):
        issues.append('缓存中没有待刻录文件')
    
    # 检查容量
    cache_size = sum(f.stat().st_size for f in cache_files if f.is_file())
    disc_capacity = get_disc_capacity()
    
    if disc_capacity and cache_size > disc_capacity:
        issues.append(f'缓存文件大小({format_size(cache_size)})超过光盘容量({format_size(disc_capacity)})')
    
    # 检查刻录工具
    tools = ['wodim', 'growisofs']
    for tool in tools:
        check = run_command(f'which {tool}')
        if not check['success']:
            issues.append(f'刻录工具 {tool} 未安装')
    
    return jsonify({
        'success': True,
        'ready': len(issues) == 0,
        'issues': issues,
        'cacheSize': cache_size,
        'cacheSizeFormatted': format_size(cache_size),
        'discCapacity': disc_capacity,
        'discCapacityFormatted': format_size(disc_capacity) if disc_capacity else '未知'
    })

@app.route('/api/burn/start', methods=['POST'])
def start_burn():
    """开始刻录 (带参数)"""
    data = request.json or {}
    speed = data.get('speed', 0)
    
    # 检查准备状态
    check_result = check_burn_ready().get_json()
    if not check_result.get('ready'):
        return jsonify({
            'success': False, 
            'error': '刻录条件不满足',
            'issues': check_result.get('issues', [])
        })
    
    disc_type = get_disc_type()
    cache_files = list(UPLOAD_FOLDER.iterdir())
    cache_size = sum(f.stat().st_size for f in cache_files if f.is_file())
    
    # 获取光盘状态以决定刻录模式
    info_result = run_command(f'dvd+rw-mediainfo {CDROM_DEVICE} 2>&1')
    output = info_result.get('stdout', '') + info_result.get('stderr', '')
    is_blank = 'Disc status:           blank' in output
    
    # 通用处理：创建临时刻录目录
    burn_dir = CACHE_DIR / 'burn_temp'
    burn_dir.mkdir(exist_ok=True)
    for f in cache_files:
        if f.is_file():
            shutil.copy2(f, burn_dir / f.name)

    # 根据光盘类型选择刻录方式
    # DVD, BD 或包含 DVD/BD 关键字的类型
    is_dvd_bd = disc_type in ['DVD', 'DVD-RW', 'Blu-ray'] or 'DVD' in disc_type or 'BD' in disc_type
    
    if is_dvd_bd:
        # 使用 growisofs 刻录 DVD/BD
        speed_opt = f'-speed={speed}' if speed > 0 else ''
        
        # 核心逻辑：空白盘用 -Z，非空白盘用 -M (追加)
        if is_blank:
            mode_opt = '-Z'
            mode_desc = '新建'
        else:
            mode_opt = '-M'
            mode_desc = '追加'
            
        cmd = f'growisofs {mode_opt} {CDROM_DEVICE} -R -J -joliet-long {speed_opt} "{burn_dir}"'
        
    else:
        # 使用 wodim 刻录 CD
        speed_opt = f'speed={speed}' if speed > 0 else ''
        iso_path = CACHE_DIR / 'temp.iso'
        
        # 创建ISO
        mkisofs_result = run_command(f'mkisofs -R -J -o "{iso_path}" "{burn_dir}"')
        if not mkisofs_result['success']:
            return jsonify({
                'success': False,
                'error': '创建ISO镜像失败: ' + mkisofs_result.get('stderr', '')
            })
        
        # CD 的多区段由 wodim 的 -multi 参数控制
        multi_opt = '-multi' if not is_blank else ''
        cmd = f'wodim -v dev={CDROM_DEVICE} {speed_opt} {multi_opt} -data "{iso_path}"'
        mode_desc = '新建' if is_blank else '追加'
    
    # 执行刻录
    result = run_command(cmd, timeout=1800)  # 30分钟超时
    
    # 清理临时文件
    try:
        if burn_dir.exists(): shutil.rmtree(burn_dir)
        iso_path = CACHE_DIR / 'temp.iso'
        if iso_path.exists(): iso_path.unlink()
    except: pass
    
    if result['success']:
        return jsonify({
            'success': True,
            'message': f'刻录完成 ({mode_desc}模式)',
            'output': result.get('stdout', ''),
            'bytesWritten': cache_size
        })
    else:
        return jsonify({
            'success': False,
            'error': '刻录失败',
            'output': result.get('stderr', result.get('stdout', ''))
        })


@app.route('/api/burn/quick', methods=['POST'])
def quick_burn():
    """快速刻录 - 自动判断新建或追加"""
    
    # 1. 检查光驱
    if not os.path.exists(CDROM_DEVICE):
        return jsonify({'success': False, 'error': '光驱设备不存在'})
    
    # 2. 检查光盘
    if not check_disc_present():
        return jsonify({'success': False, 'error': '请放入光盘'})
    
    # 3. 获取光盘状态
    info_result = run_command(f'dvd+rw-mediainfo {CDROM_DEVICE} 2>&1')
    output = info_result.get('stdout', '') + info_result.get('stderr', '')
    
    is_blank = 'Disc status:           blank' in output
    writable_keywords = ['DVD-R', 'DVD+R', 'DVD-RW', 'DVD+RW', 'BD-R', 'BD-RE', 'CD-R']
    is_writable_media = any(keyword in output for keyword in writable_keywords)
    
    # 如果不是空白，也不是可写介质，则报错
    if not is_blank and not is_writable_media:
        return jsonify({'success': False, 'error': '当前光盘不可写入'})
    
    # 4. 检查缓存
    cache_files = [f for f in UPLOAD_FOLDER.iterdir() if f.is_file()]
    if not cache_files:
        return jsonify({'success': False, 'error': '请先上传文件到缓存'})
    
    # 5. 检查容量
    cache_size = sum(f.stat().st_size for f in cache_files)
    disc_capacity = get_disc_capacity()
    
    # 如果不是空白菜，这里应该计算剩余空间比较合理，但暂时还是用总容量做简单限制
    if disc_capacity and cache_size > disc_capacity:
        return jsonify({
            'success': False, 
            'error': f'文件大小({format_size(cache_size)})超过光盘容量({format_size(disc_capacity)})'
        })
    
    # 6. 检测光盘类型并刻录
    disc_type = get_disc_type()
    is_dvd_bd = disc_type in ['DVD', 'DVD-RW', 'Blu-ray'] or 'DVD' in disc_type or 'BD' in disc_type
    
    # 准备临时文件
    burn_dir = CACHE_DIR / 'burn_temp'
    burn_dir.mkdir(exist_ok=True)
    
    # 【修改点】保持目录结构复制
    for f in cache_files:
        # 计算文件在缓存中的相对路径
        try:
            rel_path = f.relative_to(UPLOAD_FOLDER)
            target_path = burn_dir / rel_path
            
            # 创建目标目录
            target_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 复制文件
            shutil.copy2(f, target_path)
        except Exception as e:
            print(f"复制文件失败 {f}: {e}")
            
    
    if is_dvd_bd:
        # DVD/BD 使用 growisofs
        # 关键逻辑：空白 -> -Z，已写入 -> -M
        if is_blank:
            cmd = f'growisofs -Z {CDROM_DEVICE} -R -J -joliet-long "{burn_dir}"'
            mode_desc = '新建刻录'
        else:
            cmd = f'growisofs -M {CDROM_DEVICE} -R -J -joliet-long "{burn_dir}"'
            mode_desc = '追加刻录'
            
    else:
        # CD 使用 wodim
        iso_path = CACHE_DIR / 'temp.iso'
        mkisofs_result = run_command(f'mkisofs -R -J -o "{iso_path}" "{burn_dir}"', timeout=300)
        if not mkisofs_result['success']:
            shutil.rmtree(burn_dir)
            return jsonify({'success': False, 'error': '创建ISO失败'})
        
        if is_blank:
            cmd = f'wodim -v dev={CDROM_DEVICE} -data "{iso_path}"'
            mode_desc = '新建刻录'
        else:
            cmd = f'wodim -v dev={CDROM_DEVICE} -multi -data "{iso_path}"'
            mode_desc = '追加刻录'
    
    # 执行刻录
    result = run_command(cmd, timeout=1800)
    
    # 清理
    try:
        shutil.rmtree(CACHE_DIR / 'burn_temp')
        (CACHE_DIR / 'temp.iso').unlink(missing_ok=True)
    except: pass
    
    if result['success']:
        run_command('sync')
        return jsonify({
            'success': True,
            'message': f'{mode_desc}完成！共写入 {format_size(cache_size)}',
            'discType': disc_type
        })
    else:
        error_msg = result.get('stderr', '') or result.get('stdout', '') or '未知错误'
        return jsonify({'success': False, 'error': f'刻录失败: {error_msg}'})

# 辅助函数
def format_size(size):
    """格式化文件大小"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} PB"

if __name__ == '__main__':
    # 创建静态目录 (直接在这里执行，替代被移除的 before_first_request)
    Path('static').mkdir(exist_ok=True)
    
    print("=" * 50)
    print("光盘管理系统启动")
    print(f"光驱设备: {CDROM_DEVICE}")
    print(f"缓存目录: {CACHE_DIR}")
    print("访问地址: http://localhost:5000")
    print("=" * 50)
    
    app.run(host='0.0.0.0', port=5000, debug=True)