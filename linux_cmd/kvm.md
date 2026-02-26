## kvm 安装

1. 安装
```bash
sudo apt update
sudo apt install -y \
  qemu-kvm \
  libvirt-daemon-system \
  libvirt-clients \
  virt-manager \
  bridge-utils

```
2. 开机启动
```bash
sudo systemctl enable --now libvirtd

```
3. 用户组设置
```bash
sudo usermod -aG libvirt,kvm $USER
newgrp libvirt
```

## 创建一个虚拟机

1. 创建硬盘
```bash
sudo mkdir -p /var/lib/libvirt/images
sudo qemu-img create -f raw ./vm256g.raw 256G

ls -lh ./vm256g.raw
```

2. 创建虚拟机
```bash
sudo virt-install \
  --name win10 \
  --memory 8192 \
  --vcpus 8 \
  --cpu host-passthrough \
  --machine q35 \
  --cdrom /home/feng1/nvme/kvm/ISO/windows10.iso \
  --disk path=/home/feng1/nvme/kvm/DISK/win10.raw,format=raw,bus=virtio \
  --disk path=/home/feng1/nvme/kvm/ISO/virtio-win.iso,device=cdrom \
  --network bridge=br0,model=virtio \
  --graphics vnc,listen=0.0.0.0 \
  --video qxl \
  --os-variant win10 \
  --noautoconsole


sudo virt-install \
  --osinfo detect=on,name=linux2024 \
  --name android \
  --memory 6144 \
  --vcpus 8 \
  --cpu host-passthrough \
  --machine q35 \
  --boot uefi \
  --disk path=/home/feng1/nvme/kvm/DISK/android.raw,format=raw,bus=virtio,cache=none,io=native \
  --cdrom /home/feng1/nvme/kvm/ISO/lineage.iso \
  --network network=default,model=virtio \
  --graphics none \
  --video none \
  --host-device 0000:01:00.0 \
  --host-device 0000:01:00.1 \
  --features kvm_hidden=on
```

## 显卡

### 1. 显卡卸载驱动

### 2. 显卡安装驱动

# 解绑 VGA
if [ -e /sys/bus/pci/drivers/vfio-pci/0000:01:00.0 ]; then
    echo 0000:01:00.0 | sudo tee /sys/bus/pci/drivers/vfio-pci/unbind
fi

# 解绑 Audio
if [ -e /sys/bus/pci/drivers/vfio-pci/0000:01:00.1 ]; then
    echo 0000:01:00.1 | sudo tee /sys/bus/pci/drivers/vfio-pci/unbind
fi

echo "" | sudo tee /sys/bus/pci/devices/0000:01:00.1/driver_override
echo "" | sudo tee /sys/bus/pci/devices/0000:01:00.0/driver_override

lspci -nnk -s 01:00.0
lspci -nnk -s 01:00.1

mokutil --sb-state

sudo modprobe nvidia
sudo modprobe nvidia_uvm
sudo modprobe nvidia_modeset
sudo modprobe nvidia_drm

lspci -nnk -s 01:00.0
