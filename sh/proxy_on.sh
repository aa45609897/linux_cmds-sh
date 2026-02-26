#!/bin/bash
# proxy_on.sh
# 用法: source proxy_on.sh [代理地址]
# 默认地址: 192.168.10.100:10808

# 如果没有传参，使用默认代理
PROXY=${1:-192.168.10.100:10808}

# 设置环境变量
export http_proxy="http://$PROXY"
export https_proxy="http://$PROXY"
export all_proxy="socks5h://$PROXY"

echo "✅ 代理已开启: $PROXY"
echo "http_proxy=$http_proxy"
echo "https_proxy=$https_proxy"
echo "all_proxy=$all_proxy"
