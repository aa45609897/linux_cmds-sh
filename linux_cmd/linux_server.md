## 网络配置
ls /etc/netplan/

sudo vim /etc/netplan/00-network-config.yaml

```yaml
network:
  version: 2
  renderer: networkd
  ethernets:
    # 将两个物理网口配置为不自动获取IP，由网桥管理
    enp4s0:
      dhcp4: no
    enp5s0:
      dhcp4: no
  bridges:
    br0:
      interfaces:
        - enp4s0
        - enp5s0
      addresses:
        - 192.168.10.250/24
      routes:
        - to: default
          via: 192.168.10.1   # 请确认你的网关地址
      nameservers:
        addresses:
          - 8.8.8.8
          - 114.114.114.114
      parameters:
        stp: false  # 关闭生成树协议，除非你需要防止环路
```

sudo netplan try

sudo netplan apply

ip a

sudo systemctl disable systemd-networkd-wait-online.service
sudo systemctl mask systemd-networkd-wait-online.service

## fstab

sudo apt update
sudo apt install ntfs-3g -y

UUID=你的UUID  挂载点  文件系统  挂载选项  dump  pass

UUID=B474A7C01ADC3FCA  /mnt/system_disk  ntfs-3g  defaults,uid=1000,gid=1000,umask=022  0  0

### 软连接/绑定
语法: ln -s <源路径> <链接路径>

格式: <源路径> <目标路径> none bind 0 0

/mnt/system_disk/Your/Folder/Path  /home/feng1/target_folder  none  bind  0  0

## smb

sudo vim /etc/samba/smb.conf

```ini
[disk]
   comment = Feng1 Shared Disk
   path = /home/feng1/disk
   browseable = yes
   writable = yes
   read only = no
   valid users = feng1
   force user = feng1
   force group = feng1
   create mask = 0755
   directory mask = 0755
```

sudo smbpasswd -a feng1

sudo smbpasswd -e feng1

sudo mkdir -p /home/feng1/disk

sudo chown -R feng1:feng1 /home/feng1/disk

sudo chmod -R 755 /home/feng1/disk

sudo systemctl restart smbd
sudo systemctl restart nmbd

## 从windows 启动

grep -E "menuentry|submenu" /boot/grub/grub.cfg | cut -d "'" -f2

sudo grub-reboot "Windows Boot Manager"
sudo reboot

```shell
# 1. 查看当前启动顺序
sudo efibootmgr

# 输出示例：
# BootCurrent: 0000
# BootOrder: 0000,0001,0002
# Boot0000* ubuntu
# Boot0001* Windows Boot Manager
# Boot0002* UEFI: KingstonDataTraveler

# 2. 设置下一次启动到Windows（根据上面的Boot编号）
sudo efibootmgr --bootnext 0001  # 0001是Windows的编号

# 3. 立即重启
sudo reboot
```

```shell
# Debian/Ubuntu 系列使用：
sudo grep -i "windows" /boot/grub/grub.cfg

sudo grub-reboot "Windows Boot Manager (on /dev/nvme0n1p1)"
```

## ssh免密码配置

ssh-keygen -t rsa -b 4096 -C "你的邮箱或注释"

ssh-copy-id 用户名@远程服务器IP

cat ~/.ssh/id_rsa.pub
```bash
# 创建 .ssh 目录（如果不存在），并设置正确权限
mkdir -p ~/.ssh
chmod 700 ~/.ssh

# 将你复制的公钥内容添加到 authorized_keys 文件
# 用编辑器打开文件，或使用 echo 命令追加
echo "你刚才复制的公钥内容" >> ~/.ssh/authorized_keys

# 设置 authorized_keys 文件的正确权限
chmod 600 ~/.ssh/authorized_keys
```

## 代理

export http_proxy="socks5h://192.168.10.100:10808"
export https_proxy="socks5h://192.168.10.100:10808"
export all_proxy="socks5h://192.168.10.100:10808"

export http_proxy="http://192.168.10.100:10808"
export https_proxy="http://192.168.10.100:10808"

pip install pysocks
pip install transformers --proxy socks5h://192.168.10.100:10808

conda config --set proxy_servers.http socks5h://192.168.10.100:10808
conda config --set proxy_servers.https socks5h://192.168.10.100:10808

sudo vim /etc/apt/apt.conf.d/95proxies
    Acquire::http::Proxy "http://192.168.10.100:10808/";
    Acquire::https::Proxy "http://192.168.10.100:10808/";

curl ipinfo.io