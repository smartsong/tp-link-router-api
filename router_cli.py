#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TP-Link 路由器 CLI 工具
用法:
    python router_cli.py devices           # 查看设备列表
    python router_cli.py lan               # 查看LAN信息
    python router_cli.py wan               # 查看WAN信息
    python router_cli.py sys               # 查看系统信息
    python router_cli.py reboot            # 重启路由器（危险！）
    python router_cli.py all               # 查看所有信息
    python router_cli.py login             # 测试登录
"""

import sys
import os

# 尝试从同一目录导入 router_api
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from router_api import TPLinkRouter, encode_password

# 默认配置
DEFAULT_HOST = "http://192.168.0.1"
DEFAULT_USER = "admin"
DEFAULT_PASS = "Smartsong771211"


def get_router() -> TPLinkRouter:
    """创建并登录路由器实例"""
    host = os.environ.get("TP_HOST", DEFAULT_HOST)
    user = os.environ.get("TP_USER", DEFAULT_USER)
    password = os.environ.get("TP_PASS", DEFAULT_PASS)

    router = TPLinkRouter(host, user, password)
    if not router.login():
        print(f"[!] 登录失败！请检查密码是否正确（当前密码: {password}）")
        sys.exit(1)
    return router


def cmd_devices(detail: bool = False):
    """设备列表"""
    router = get_router()
    devices = router.get_devices()
    print(f"\n{'='*60}")
    print(f"TP-Link 路由器在线设备 ({len(devices)} 台)")
    print(f"{'='*60}")
    print(router.format_devices(devices))
    if detail:
        print(f"\n[原始JSON - 前3台设备]")
        import json
        print(json.dumps(devices[:3], indent=2, ensure_ascii=False))


def cmd_lan():
    """LAN信息"""
    router = get_router()
    lan = router.get_lan_info()
    print(f"\n{'='*40}")
    print("LAN 信息")
    print(f"{'='*40}")
    print(f"  IP地址:    {lan.get('ipaddr')}")
    print(f"  子网掩码:  {lan.get('netmask')}")
    print(f"  MAC地址:   {lan.get('macaddr')}")
    print(f"  接口:      {', '.join(lan.get('ifname', []))}")
    print(f"  类型:      {lan.get('type')}")
    print(f"  原厂IP:    {lan.get('fac_ipaddr')}")


def cmd_wan():
    """WAN信息"""
    router = get_router()
    wan = router.get_wan_info()
    print(f"\n{'='*40}")
    print("WAN 信息")
    print(f"{'='*40}")
    if isinstance(wan, list) and not wan:
        print("  （空 - 可能是 AP 模式）")
    else:
        import json
        print(json.dumps(wan, indent=2, ensure_ascii=False))


def cmd_sys():
    """系统信息"""
    router = get_router()
    sys_info = router.get_sys_info()
    uptime = router.get_uptime()
    print(f"\n{'='*40}")
    print("系统信息")
    print(f"{'='*40}")
    import json
    print(json.dumps(sys_info, indent=2, ensure_ascii=False))
    print(f"\n运行时间: {uptime}")


def cmd_all():
    """查看所有信息"""
    router = get_router()

    # 设备
    devices = router.get_devices()
    print(f"\n{'='*60}")
    print(f"📡 在线设备 ({len(devices)} 台)")
    print(f"{'='*60}")
    print(router.format_devices(devices))

    # LAN
    lan = router.get_lan_info()
    print(f"\n🌐 LAN: {lan.get('ipaddr')}/{lan.get('netmask')}  MAC: {lan.get('macaddr')}")

    # 系统
    uptime = router.get_uptime()
    print(f"⏱️  运行时间: {uptime}")


def cmd_login():
    """测试登录"""
    host = os.environ.get("TP_HOST", DEFAULT_HOST)
    user = os.environ.get("TP_USER", DEFAULT_USER)
    password = os.environ.get("TP_PASS", DEFAULT_PASS)

    router = TPLinkRouter(host, user, password)
    print(f"[*] 正在登录 {host} (user={user}, pass={'*'*len(password)})...")

    if router.login():
        print(f"[OK] 登录成功！")
        print(f"     stok: {router.stok}")
    else:
        print(f"[!] 登录失败！")


def cmd_reboot():
    """重启路由器"""
    print("⚠️  确认要重启路由器吗？")
    confirm = input("输入 'yes' 确认: ")
    if confirm.lower() != "yes":
        print("取消操作。")
        return

    router = get_router()
    print("[*] 正在重启路由器...")
    if router.reboot():
        print("[OK] 重启命令已发送，路由器将在约30秒后重启。")
    else:
        print("[!] 重启失败。")


# ============================================================
# 主程序
# ============================================================

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("\n环境变量（可选）:")
        print("  TP_HOST=192.168.0.1")
        print("  TP_USER=admin")
        print("  TP_PASS=你的密码")
        sys.exit(1)

    cmd = sys.argv[1].lower()

    if cmd == "devices":
        detail = "--detail" in sys.argv or "-v" in sys.argv
        cmd_devices(detail)
    elif cmd == "lan":
        cmd_lan()
    elif cmd == "wan":
        cmd_wan()
    elif cmd == "sys":
        cmd_sys()
    elif cmd == "all":
        cmd_all()
    elif cmd == "login":
        cmd_login()
    elif cmd == "reboot":
        cmd_reboot()
    else:
        print(f"未知命令: {cmd}")
        print("可用命令: devices, lan, wan, sys, all, login, reboot")
        sys.exit(1)


if __name__ == "__main__":
    main()