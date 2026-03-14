## tgt 光驱创建

sudo vim /etc/tgt/conf.d/cdrom.conf

```conf
<target iqn.2026-03.lab:cdrom0>
    backing-store /dev/sr0
    initiator-address ALL
</target>

<target iqn.2026-03.lab:cdrom1>
    backing-store /dev/sr1
    initiator-address ALL
</target>

<target iqn.2026-03.lab:cdrom2>
    backing-store /dev/sr2
    initiator-address ALL
</target>
```

sudo apt update
sudo apt install tgt sg3-utils

sudo systemctl enable --now tgt
sudo systemctl restart tgt

sudo tgtadm --mode target --op show

#### 客户端连接

sudo apt install open-iscsi

sudo iscsiadm -m discovery -t sendtargets -p 192.168.1.10

sudo iscsiadm -m node --login

sudo mount /dev/sr0 /mnt

#### 换盘刷新

sudo apt install udev

sudo vim /usr/local/bin/cdrom-refresh.sh

```shell
#!/bin/bash

for session in $(tgtadm --mode conn --op show | grep Session | awk '{print $2}')
do
    tgtadm --mode conn --op update --tid $session
done
```

sudo chmod +x /usr/local/bin/cdrom-refresh.sh

sudo nano /etc/udev/rules.d/99-cdrom-change.rules

KERNEL=="sr[0-9]*", ACTION=="change", RUN+="/usr/local/bin/cdrom-refresh.sh"

sudo udevadm control --reload