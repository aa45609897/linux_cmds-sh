## 1.安装
1. 卸载旧版本
```bash
sudo apt remove docker docker-engine docker.io containerd runc
sudo apt autoremove -y
```
2. 脚本安装
```bash
# 下载安装脚本
curl -fsSL https://get.docker.com -o get-docker.sh

# 执行安装
sudo sh get-docker.sh

# 或直接运行
curl -fsSL https://get.docker.com | sudo sh
```
```bash
# 使用阿里云镜像源安装
curl -fsSL https://mirrors.aliyun.com/docker-ce/linux/ubuntu/gpg | sudo apt-key add -

# 添加阿里云Docker源
sudo add-apt-repository \
   "deb [arch=$(dpkg --print-architecture)] https://mirrors.aliyun.com/docker-ce/linux/ubuntu \
   $(lsb_release -cs) stable"

# 安装
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

sudo usermod -aG docker $USER
```

3. 镜像配置
```bash
# 创建 Docker 配置目录
sudo mkdir -p /etc/docker

# 创建配置文件
sudo tee /etc/docker/daemon.json <<-'EOF'
{
  "registry-mirrors": [
    "https://docker.mirrors.ustc.edu.cn",
    "https://hub-mirror.c.163.com",
    "https://mirror.baidubce.com",
    "https://registry.docker-cn.com",
    "https://docker.mirrors.aliyun.com"
  ],
  "exec-opts": ["native.cgroupdriver=systemd"],
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "100m",
    "max-file": "3"
  },
  "storage-driver": "overlay2"
}
EOF

# 重启 Docker
sudo systemctl daemon-reload
sudo systemctl restart docker

# 检查配置
sudo docker info | grep -A 10 "Registry Mirrors"
```
4. 代理配置
```bash
sudo mkdir -p /etc/systemd/system/docker.service.d

sudo vim /etc/systemd/system/docker.service.d/http-proxy.conf

[Service]
Environment="HTTP_PROXY=http://192.168.10.100:10808/"
Environment="HTTPS_PROXY=http://192.168.10.100:10808/"
Environment="NO_PROXY=localhost,127.0.0.1,docker-registry.example.com,.corp"

sudo systemctl daemon-reload
sudo systemctl restart docker

sudo systemctl show docker --property Environment
```
5. 管理页面
```bash
# 创建Portainer数据卷
docker volume create portainer_data

# 运行Portainer容器
docker run -d \
  -p 9000:9000 \
  -p 9443:9443 \
  --name portainer \
  --restart=always \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v portainer_data:/data \
  portainer/portainer-ce:latest
```

docker run -d \
  --name dufs \
  --restart always \
  -p 5000:5000 \
  -v $(pwd):/data \
  sigoden/dufs \
  /data -A

## docker compose

docker-compose.yml

docker compose up -d

docker compose down

docker compose logs -f

docker compose restart
```bash
# 基本语法
docker save -o 输出文件名.tar 镜像名:标签
# 示例：保存 fika 镜像
docker save -o fika-server-4.0.12.tar ghcr.io/zhliau/fika-spt-server-docker:4.0.12
# 基本语法
docker load -i 文件名.tar
# 示例：加载刚才保存的 fika 镜像
docker load -i fika-server-4.0.12.tar
# 通过管道直接压缩
docker save ghcr.io/zhliau/fika-spt-server-docker:4.0.12 | gzip > fika-server-4.0.12.tar.gz
# 加载压缩的镜像
gunzip -c fika-server-4.0.12.tar.gz | docker load
# 或者
docker load -i fika-server-4.0.12.tar.gz
docker save -o multiple-images.tar \
  ghcr.io/zhliau/fika-spt-server-docker:4.0.12 \
  nginx:alpine
```
## 安卓镜像

#### 拉取镜像 (推荐 Android 12)
docker pull redroid/redroid:12.0.0-latest

docker run -itd \
  --rm \
  --name redroid \
  --privileged \
  --cap-add=SYS_ADMIN \
  --security-opt seccomp=unconfined \
  --device /dev/dri \
  --device /dev/kvm \
  -p 5555:5555 \
  redroid/redroid:12.0.0-latest

--device /dev/dri（用于 GPU 渲染）
--cap-add=SYS_ADMIN（Redroid 开启 Vulkan 的必要权限）

docker exec -it redroid /system/bin/sh

vulkaninfo | head

#### waydroid
sudo curl -# --proto '=https' --tlsv1.2 -Sf https://repo.waydro.id/waydroid.gpg -o /usr/share/keyrings/waydroid.gpg

echo "deb [signed-by=/usr/share/keyrings/waydroid.gpg] https://repo.waydro.id/ focal main" | sudo tee /etc/apt/sources.list.d/waydroid.list

sudo apt update
sudo apt install -y curl ca-certificates waydroid

sudo apt install -y adb

sudo waydroid init

sudo waydroid container start

sudo waydroid shell adb shell settings put global adb_tcp_port 5555

ip addr show waydroid0 | grep inet

adb connect 192.168.240.112:5555
adb devices
scrcpy --serial 192.168.240.112:5555

adb shell dumpsys SurfaceFlinger | grep "GLES"

