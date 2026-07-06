#!/bin/bash
# 切换系统默认启动目标（图形/文本）

set -e

show_status() {
    current=$(systemctl get-default)
    echo "当前默认启动目标: $current"
    if [[ "$current" == "graphical.target" ]]; then
        echo "当前: 图形界面模式（开机启动桌面）"
    elif [[ "$current" == "multi-user.target" ]]; then
        echo "当前: 文本模式（不启动桌面）"
    else
        echo "当前: 其他目标"
    fi
}

case "$1" in
    status|--status|-s)
        show_status
        ;;
    enable|on|graphical)
        echo "切换到图形界面模式（开机启动 GDM）..."
        sudo systemctl set-default graphical.target
        echo "设置完成。下次重启将进入图形界面。"
        ;;
    disable|off|multi-user)
        echo "切换到文本模式（开机不启动 GDM）..."
        sudo systemctl set-default multi-user.target
        echo "设置完成。下次重启将进入文本模式。"
        ;;
    toggle|"")
        current=$(systemctl get-default)
        if [[ "$current" == "graphical.target" ]]; then
            target="multi-user.target"
            msg="文本模式"
        else
            target="graphical.target"
            msg="图形界面模式"
        fi
        echo "当前: $current，将切换至 $target ($msg)"
        read -p "确认切换? [y/N] " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            sudo systemctl set-default "$target"
            echo "切换完成。下次重启将进入 $msg。"
        else
            echo "取消切换。"
        fi
        ;;
    *)
        echo "用法: $0 [status|enable|disable|toggle]"
        echo "  status          显示当前默认启动目标"
        echo "  enable|on|graphical  设置为图形界面模式（开机启动桌面）"
        echo "  disable|off|multi-user 设置为文本模式（开机不启动桌面）"
        echo "  toggle (默认)    切换当前模式（交互确认）"
        exit 1
        ;;
esac
