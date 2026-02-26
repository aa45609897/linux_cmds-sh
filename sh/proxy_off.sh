#!/bin/bash
# proxy_off.sh
# 用法: source proxy_off.sh

unset http_proxy
unset https_proxy
unset all_proxy

echo "❌ 代理已关闭"
