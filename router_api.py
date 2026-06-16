# -*- coding: utf-8 -*-
"""
TP-Link 路由器 REST API 核心库
适用型号：TL-R488GPM-AC 及同架构 TP-Link 路由器

作者：苏岚 @ 宋涛
日期：2026-06-16
"""

import sys
import json
import requests
import urllib.parse
from typing import Optional, Dict, Any, List

__version__ = "1.0.0"

# ============================================================
# 密码加密算法（TP-Link 自定义 XOR + 查表，非 RSA）
# ============================================================
TP_KEY1 = "RDpbLfCPsJZ7fiv"
TP_KEY2 = "yLwVl0zKqws7LgKPRQ84Mdt708T1qQ3Ha7xv3H7NyU84p21BriUWBU43odz3iP4rBL3cD02KZciXTysVXiV8ngg6vL48rPJyAUw0HurW20xqxv9aYb4M9wK1Ae0wlro510qXeU07kV57fQMc8L6aLgMLwygtc0F10a0Dg70TOoouyFhdysuRMO51yY5ZlOZZLEal1h0t9YQW0Ko7oBwmCAHoic4HYbUyVeU3sfQ1xtXcPcf1aT303wAQhv66qzW"


def encode_password(password: str) -> str:
    """
    TP-Link 路由器密码加密（securityEncode）
    算法：XOR + 查表替换，不是 RSA
    """
    r = []
    g, m, f = len(password), len(TP_KEY1), len(TP_KEY2)
    for e in range(max(g, m)):
        t = l = 187
        if e >= g:
            t = ord(TP_KEY1[e])
        elif e >= m:
            l = ord(password[e])
        else:
            l, t = ord(password[e]), ord(TP_KEY1[e])
        r.append(TP_KEY2[(l ^ t) % f])
    return ''.join(r)


class TPLinkRouter:
    """TP-Link 路由器 API 封装"""

    def __init__(self, host: str = "http://192.168.0.1", username: str = "admin", password: str = ""):
        self.host = host.rstrip("/")
        self.username = username
        self.password = password
        self.stok: Optional[str] = None
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json; charset=UTF-8",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
        })

    # --------------------------------------------------------
    # 认证
    # --------------------------------------------------------

    def login(self) -> bool:
        """登录路由器，返回 True/False"""
        encoded = encode_password(self.password)
        payload = {"method": "do", "login": {"username": self.username, "password": encoded}}
        try:
            r = self.session.post(self.host + "/", json=payload, timeout=10)
            j = r.json()
            if j.get("error_code") == 0:
                self.stok = j.get("stok")
                return True
            return False
        except Exception:
            return False

    def is_logged_in(self) -> bool:
        """检查是否已登录"""
        return self.stok is not None

    # --------------------------------------------------------
    # 底层 API 调用
    # --------------------------------------------------------

    def _api(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        发送 API 请求
        - 读操作: method="get"
        - 写操作: method="do"
        """
        if not self.stok:
            raise RuntimeError("未登录，请先调用 login()")
        url = f"{self.host}/stok={self.stok}/ds"
        r = self.session.post(url, json=payload, timeout=10)
        return r.json()

    def get(self, module: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """读操作 API"""
        if params is None:
            payload = {module: None, "method": "get"}
        else:
            payload = {module: params, "method": "get"}
        return self._api(payload)

    def do(self, module: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """写操作 API"""
        if params is None:
            payload = {module: None, "method": "do"}
        else:
            payload = {module: params, "method": "do"}
        return self._api(payload)

    # --------------------------------------------------------
    # 高级 API
    # --------------------------------------------------------

    def get_devices(self) -> List[Dict[str, Any]]:
        """获取所有在线设备"""
        resp = self.get("hosts_info", {"table": "host_info"})
        return resp.get("hosts_info", {}).get("host_info", [])

    def get_lan_info(self) -> Dict[str, Any]:
        """获取 LAN 信息"""
        resp = self.get("network", {"name": "lan"})
        return resp.get("network", {}).get("lan", {})

    def get_wan_info(self) -> Dict[str, Any]:
        """获取 WAN 信息"""
        resp = self.get("network", {"name": "wan"})
        return resp.get("network", {}).get("wan", {})

    def get_sys_info(self) -> Dict[str, Any]:
        """获取系统信息"""
        resp = self.get("system", {"name": "sys_info"})
        return resp.get("system", {}).get("sys_info", {})

    def get_uptime(self) -> str:
        """获取运行时间"""
        resp = self.get("system", {"name": "uptime"})
        uptime_list = resp.get("system", {}).get("uptime", [])
        return ", ".join(str(u) for u in uptime_list) if uptime_list else "未知"

    def reboot(self) -> bool:
        """重启路由器"""
        resp = self.do("system", {"reboot": None})
        return resp.get("error_code") == 0

    # --------------------------------------------------------
    # 格式化输出
    # --------------------------------------------------------

    def format_devices(self, devices: List[Dict[str, Any]]) -> str:
        """格式化设备列表为可读字符串"""
        if not devices:
            return "没有在线设备"
        lines = []
        lines.append(f"{'主机名':<30} {'IP':<16} {'MAC':<19} {'信号':>5} 连接")
        lines.append("-" * 85)
        for h in devices:
            for key, info in h.items():
                name = urllib.parse.unquote(info.get("hostname", "匿名主机"))
                ip = info.get("ip", "?")
                mac = info.get("mac", "?")
                rssi = info.get("rssi", "?")
                conn_type = "WiFi" if info.get("type") == "1" else "有线"
                ssid = info.get("ssid", "")
                if ssid:
                    conn_type += f"({ssid})"
                cur = " ← 当前" if info.get("is_cur_host") == "1" else ""
                lines.append(f"{name:<30} {ip:<16} {mac:<19} {rssi:>5} {conn_type}{cur}")
        return "\n".join(lines)


# ============================================================
# 快速使用函数
# ============================================================

def quick_test(host: str = "http://192.168.0.1", username: str = "admin", password: str = "admin"):
    """一键测试：登录 + 设备列表 + LAN信息"""
    router = TPLinkRouter(host, username, password)
    print(f"[*] 正在登录 {host}...")

    if not router.login():
        print("[!] 登录失败！")
        return None

    print(f"[OK] 登录成功，stok={router.stok}\n")

    # 设备列表
    print("=" * 60)
    print("在线设备")
    print("=" * 60)
    devices = router.get_devices()
    print(f"共 {len(devices)} 台设备在线：")
    print(router.format_devices(devices))

    # LAN信息
    lan = router.get_lan_info()
    print(f"\nLAN: {lan.get('ipaddr')}/{lan.get('netmask')}  MAC: {lan.get('macaddr')}")

    return router


if __name__ == "__main__":
    # 命令行快速测试
    import argparse
    parser = argparse.ArgumentParser(description="TP-Link 路由器 API 工具")
    parser.add_argument("--host", default="http://192.168.0.1")
    parser.add_argument("-u", "--username", default="admin")
    parser.add_argument("-p", "--password", default="admin")
    args = parser.parse_args()

    quick_test(args.host, args.username, args.password)