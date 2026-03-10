## conda安装

1. sudo wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
2. sudo bash Miniconda3-latest-Linux-x86_64.sh
3. conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main/
    conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/free/
    conda config --set show_channel_urls yes
4. conda init --reverse $SHELL

创建新环境：conda create --name py310 python=3.10 
激活环境：conda activate py310
安装包：conda install numpy pandas 
退出环境：conda deactivate 

### conda 快捷命令
#### conda 激活函数 - 无参数时默认激活 py310，有参数时激活指定环境
ca() {
    if [ $# -eq 0 ]; then
        # 如果没有参数，默认激活 py313
        echo "Activating default environment: py313"
        conda activate py313
    else
        # 如果有参数，激活指定的环境
        conda activate "$1"
    fi
}
alias cc='conda deactivate'

source ~/.bashrc

dos2unix ~/.bashrc

### conda 常用命令_环境导入

conda env export --no-builds > environment.yml

conda env create -f environment.yml

conda env update -f environment.yml


## cuda 安装

### nvidia 驱动
1. sudo apt update
2. sudo ubuntu-drivers list
3. sudo ubuntu-drivers install
4. sudo apt install nvidia-driver-590
5. nvidia-smi

### cuda pytorch

pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
(可选)conda install pytorch torchvision torchaudio pytorch-cuda=13.1 -c pytorch -c nvidia

torch检测
```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
GPU 测试脚本
- 测试 PyTorch 是否可用 GPU
- 测试 TensorFlow 是否可用 GPU
- 打印版本、CUDA 版本和显卡信息
"""

import torch
import torchvision
from PIL import Image
import matplotlib
import requests
from transformers import Blip2Processor, CLIPProcessor

print("=== PyTorch GPU 检测 ===")
try:
    print("PyTorch version:", torch.__version__)
    print("CUDA version (PyTorch):", torch.version.cuda)
    print("Is CUDA available:", torch.cuda.is_available())
    if torch.cuda.is_available():
        print("GPU Name:", torch.cuda.get_device_name(0))
    else:
        print("No GPU detected by PyTorch")
except Exception as e:
    print("PyTorch GPU test failed:", e)

print("\n=== TensorFlow GPU 检测 ===")
try:
    import tensorflow as tf
    print("TensorFlow version:", tf.__version__)
    gpus = tf.config.list_physical_devices('GPU')
    print("GPUs detected:", gpus)
    print("Is GPU available:", len(gpus) > 0)
    if gpus:
        print("GPU Name:", gpus[0].name)
    else:
        print("No GPU detected by TensorFlow")
except Exception as e:
    print("TensorFlow GPU test failed:", e)

print("\n=== 第三方库检查 ===")
try:
    print("PIL (Pillow) version:", Image.__version__)
    print("Matplotlib version:", matplotlib.__version__)
    print("Transformers version:", Blip2Processor.__module__.split('.')[0])
except Exception as e:
    print("Library version check failed:", e)

print("\n=== 测试完成 ===")
```
#### PyTorch + torchvision + torchaudio + CUDA 12.1
conda install pytorch torchvision torchaudio pytorch-cuda=12.1 -c pytorch -c nvidia

#### 其他第三方库
pip install Pillow matplotlib requests transformers

pip install pysocks
