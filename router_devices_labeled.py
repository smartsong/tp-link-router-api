# -*- coding: utf-8 -*-
"""
TP-Link 路由器 + Home Assistant 设备交叉比对
将路由器匿名设备通过 HA MAC 匹配识别身份
"""
import sys, requests, json, urllib.parse; sys.stdout.reconfigure(encoding='utf-8')

# ============================================================
# 配置（从环境变量读取）
# ============================================================
import os
# 加载 .env 文件
_env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(_env_file):
    for line in open(_env_file):
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

TP_HOST     = os.environ.get("TP_HOST", "http://192.168.0.1")
TP_USER     = os.environ.get("TP_USER", "admin")
TP_PASS     = os.environ.get("TP_PASS", "")
HA_URL      = os.environ.get("HA_URL", "http://192.168.0.200:8123")
HA_TOKEN    = os.environ.get("HA_TOKEN", "")

TP_KEY1 = "RDpbLfCPsJZ7fiv"
TP_KEY2 = "yLwVl0zKqws7LgKPRQ84Mdt708T1qQ3Ha7xv3H7NyU84p21BriUWBU43odz3iP4rBL3cD02KZciXTysVXiV8ngg6vL48rPJyAUw0HurW20xqxv9aYb4M9wK1Ae0wlro510qXeU07kV57fQMc8L6aLgMLwygtc0F10a0Dg70TOoouyFhdysuRMO51yY5ZlOZZLEal1h0t9YQW0Ko7oBwmCAHoic4HYbUyVeU3sfQ1xtXcPcf1aT303wAQhv66qzW"

def encode_password(pwd):
    r = []
    g, m, f = len(pwd), len(TP_KEY1), len(TP_KEY2)
    for e in range(max(g, m)):
        t = l = 187
        if e >= g:  t = ord(TP_KEY1[e])
        elif e >= m: l = ord(pwd[e])
        else:        l, t = ord(pwd[e]), ord(TP_KEY1[e])
        r.append(TP_KEY2[(l ^ t) % f])
    return ''.join(r)

# ============================================================
# 1. 登录路由器，获取设备列表
# ============================================================
def get_router_devices():
    r = requests.post(f"{TP_HOST}/", headers={"Content-Type": "application/json; charset=UTF-8"},
        json={"method":"do","login":{"username":TP_USER,"password":encode_password(TP_PASS)}}, timeout=10)
    stok = r.json().get("stok")
    resp = requests.post(f"{TP_HOST}/stok={stok}/ds",
        headers={"Content-Type": "application/json; charset=UTF-8"},
        json={"hosts_info":{"table":"host_info"},"method":"get"}, timeout=10)
    return resp.json().get("hosts_info", {}).get("host_info", [])

# ============================================================
# 2. 从 HA 获取所有设备的 MAC → 名称映射
# ============================================================
def get_ha_mac_map():
    """从HA获取MAC→设备名映射。
    策略：button实体含MAC字段，但无friendly_name。
    通过实体ID后缀（如_5231）找到同设备的其他实体（如sensor/switch/climate），
    其friendly_name即为设备名。
    """
    if not HA_TOKEN:
        return {}
    hdrs = {"Authorization": f"Bearer {HA_TOKEN}"}
    r = requests.get(f"{HA_URL}/api/states", headers=hdrs, timeout=10)
    if r.status_code != 200:
        return {}
    states = r.json()

    # Step 1: 收集所有含MAC的实体 → 建立 MAC → entity_id_suffix 映射
    mac_to_suffix = {}  # MAC -> 实体ID后缀（如 _5231, _ea40）
    for s in states:
        attrs = s.get("attributes", {})
        for k, v in attrs.items():
            if "mac" not in k.lower() or ":" not in str(v):
                continue
            mac = str(v).upper().replace("-", ":")
            # 从 entity_id 提取后缀（_XXXX 格式）
            entity_id = s.get("entity_id", "")
            parts = entity_id.split(".")
            if len(parts) >= 2:
                rest = parts[1]
                # 找最后一个 _XXXX 部分（4位十六进制）
                segs = rest.split("_")
                for seg in reversed(segs):
                    if len(seg) == 4 and all(c in "0123456789abcdefABCDEF" for c in seg):
                        suffix = "_" + seg.lower()
                        if mac not in mac_to_suffix:
                            mac_to_suffix[mac] = suffix
                        break

    # Step 2: 收集所有 entity_id → (friendly_name, domain) 映射
    id_to_name = {}
    for s in states:
        entity_id = s.get("entity_id", "")
        name = s.get("attributes", {}).get("friendly_name", "").strip()
        if name and entity_id not in id_to_name:
            parts = entity_id.split(".")
            domain = parts[0] if parts else ""
            id_to_name[entity_id] = (name, domain)

    # Step 3: 通过后缀查找同设备的其他实体，获取名称
    mac_to_name = {}
    for mac, suffix in mac_to_suffix.items():
        found = None
        # 优先找button实体（整体名称，无属性描述）
        for entity_id, (name, domain) in id_to_name.items():
            parts = entity_id.split(".")
            if len(parts) >= 2 and suffix in parts[1] and domain == "button":
                found = name.replace(" 信息", "").strip()
                break
        # 没有button实体，用其他实体并清理属性描述
        if not found:
            for entity_id, (name, domain) in id_to_name.items():
                parts = entity_id.split(".")
                if len(parts) >= 2 and suffix in parts[1]:
                    found = clean_device_name(name)
                    break

        # 如果还没找到，用后缀推断
        if not found:
            found = _infer_name_by_mac_suffix(suffix)

        if found:
            mac_to_name[mac] = found

    return mac_to_name

def clean_device_name(name):
    """清理HA friendly_name中的属性描述，只保留设备名"""
    if not name:
        return name
    # 通用清理："设备名 XY属性" → "设备名"（去掉空格+属性描述）
    # 策略：找最后一个空格，看空格前是否是常见属性词
    # 常见属性词
    attr_words = [
        "空调 开关", "空调 滤芯", "空调 温度", "空调 湿度", "空调 指示灯",
        "空调 左右摆风", "空调 上下摆风", "空调 ECO", "空调 干燥", "空调 睡眠",
        "空调 提示音", "空调 模式", "空调 喜好", "空调 风速", "空调 新风机",
        "客厅空调", "主卧空调", "书房空调", "小主人房空调",
        "智能面板 左键", "智能面板 中键", "智能面板 右键",
        "智能面板 禁麦", "智能面板 睡眠模式", "智能面板 自动息屏", "智能面板 屏幕亮度",
        "智能面板 触摸音效", "智能面板 显示按键名称", "智能面板 模式", "智能面板 屏幕状态",
        "小米门厅智能面板", "Xiaomi Smart Home Control",
        "摄像头", "门锁", "网关", "浴霸", "洗衣机", "冰箱", "燃气热水器",
        "电功率", "温度", "湿度", "PM2.5", "甲烷浓度", "电池电量", "故障",
        "养生壶", "油烟机", "净水器", "饮水机", "燃气灶", "微波炉",
        "人在传感器", "门窗传感器", "温湿度计", "体脂秤", "血压计",
        "提示音", "灯", "开关", "显示屏", "标签打印机", "晾衣架",
    ]
    # 从长到短检查，去掉最长的匹配
    for attr in sorted(attr_words, key=len, reverse=True):
        if name.endswith(" " + attr):
            return name[:-len(attr)-1]
    # 去掉 ". 信息" 后缀（button实体残留）
    if name.endswith(" 信息"):
        return name[:-3]
    # 去掉常见的" XXX描述"（空格后是英文或短中文）
    import re
    # "Xiaomi Smart Home Control 左键" → "Xiaomi Smart Home Control"
    # 匹配：空格后是单个或双个字，或"左右中键"等
    m = re.search(r'\s+(左键|右键|中键|开关|指示灯|提示音|音量|亮度|禁麦|睡眠模式|自动息屏|触摸音效|显示按键名称|模式|屏幕状态|唤醒|停止闹钟|进入主页|亮屏|播放文本|执行文本指令|播放控制|空调|开关状态|开关 左键|开关右键|开关中键)$', name)
    if m:
        return name[:m.start()]
    # 通用：最后一个空格后的部分是纯英文或1-2个汉字 → 去掉
    m = re.search(r'\s+([a-zA-Z0-9\-]+|[\u4e00-\u9fff]{1,2})$', name)
    if m:
        prefix = name[:m.start()]
        # 至少保留2个字
        if len(prefix) >= 2:
            return prefix
    return name

def _infer_name_by_mac_suffix(suffix):
    """根据MAC地址后缀推断设备名称（当HA无friendly_name时的兜底）"""
    suffix = suffix.lower()  # _5231, _ea40
    known = {
        "_5231": "小米电视S75 Mini LED",
        "_7059": "Aqara网关",
        "_3cb9": "Yeelight床头灯",
        "_7e08": "小主人房窗帘",
        "_5326": "餐厅窗帘",
        "_7cd4": "书房窗帘",
        "_97b5": "客厅窗帘",
        "_a59b": "主卧右窗帘",
        "_a708": "左窗帘",
        "_2c28": "扫地机5Pro",
        "_7dc0": "智能门锁",
        "_bdaf": "智能门铃2",
        "_5618": "摄像头4 Zoom",
        "_ea40": "小米中枢网关",
        "_efb0": "空气净化器5",
        "_3547": "客厅开关(双开)",
        "_e1f0": "客卫双开",
        "_18d1": "走廊开关",
        "_c6f1": "主卫开关",
        "_3fc7": "养生壶",
        "_1359": "智米风扇",
        "_0652": "门厅智能面板",
        "_9a07": "小米智能面板",
        "_7d48": "小主人房空调",
        "_8044": "主卧空调",
        "_f455": "客厅空调",
        "_5ebb": "书房空调",
        "_b22e": "客卫智能浴霸",
        "_bb8c": "主卫浴霸",
        "_a8d2": "蒸烤箱",
        "_4392": "冰箱",
        "_1311": "燃气热水器",
        "_68d4": "小米音箱Pro",
        "_2471": "Redmi音箱8寸",
        "_f684": "书房灯带",
        "_07c1": "客厅灯带A",
        "_294d": "客厅灯带B",
        "_0420": "客厅灯带C",
        "_e1f0_bpx": "血压计",
        "_e90e": "门窗传感器",
        "_fc55": "标签打印机",
        "_de2d": "客卫人在传感器",
        "_3709": "主卫人在传感器",
        "_3f11": "厨房人在传感器",
        "_91ef": "体脂秤S400 Pro",
        "_7903": "冰箱插座",
        "_22c2": "油烟机Pro",
        "_1b6f": "洗衣机",
        "_0505": "洗衣机",
        "_0511": "阳台温湿度计",
    }
    return known.get(suffix, f"设备_{suffix}")


def _infer_name(entity_id, rest, attrs):
    """从 entity_id 推断设备名称（废弃，保持兼容）"""
    # 品牌型号前缀 → 中文名
    brand_map = {
        "ov21cn": "扫地机5Pro",
        "b03": "智能门锁",
        "mih1": "小米电视",
        "mcn004": "冰箱插座",
        "mp5": "空气净化器5",
        "cyp10": "油烟机Pro",
        "x08e": "Redmi音箱8寸",
        "hub1": "小米中枢网关",
        "hub": "Aqara网关",
        "x08e_2471": "小爱音箱8寸",
        "oh2p_68d4": "小米音箱Pro",
    }
    # 精确匹配
    if rest in brand_map:
        return brand_map[rest]

    # 前缀匹配
    for prefix, name in brand_map.items():
        if rest.startswith(prefix):
            return name

    # 通用推断
    if "lumi_hmcn02" in rest:
        return "Aqara窗帘电机"
    if "lumi_mgl03" in rest:
        return "Aqara网关"
    if "yeelink_bslamp2" in rest:
        return "Yeelight床头灯"
    if "chunmi_a1" in rest or "chunmi_health_pot" in rest:
        return "米家养生壶"
    if "chunmi_tsx8" in rest:
        return "米家蒸烤箱"
    if "dmaker_p8" in rest:
        return "智米风扇"
    if "zimi_h01" in rest:
        return "米家燃气热水器"
    if "midr_ph300" in rest:
        return "智能门铃2"
    if "midjd_bf06s" in rest:
        return "冰箱"
    if "mibx5_f60" in rest:
        return "洗衣机"
    if "mike_2_b22e" in rest:
        return "智能浴霸(客卫)"
    if "mike_2_bb8c" in rest:
        return "智能浴霸(主卫)"
    if "miaomiaoce_t2" in rest:
        return "阳台温湿度计"
    if "ihealth_bpx1" in rest:
        return "血压计"
    if "isa_dw2hl" in rest:
        return "门窗传感器"
    if "xiaomi_pir1" in rest:
        loc = rest.split("_")[-1][:4]
        loc_map = {"de2d": "客卫", "3709": "主卫", "3f11": "厨房"}
        return f"人在传感器({loc_map.get(loc, loc)})"
    if "ms110" in rest:
        return "体脂秤"
    if "label" in rest:
        return "标签打印机"
    if "abhome_wy0a01" in rest:
        return "米家灯带"
    if "xiaomi_86v1" in rest:
        return "门厅智能面板"
    if "xiaomi_w2_3547" in rest:
        return "客厅开关"
    if "xiaomi_w2_e1f0" in rest:
        return "客卫开关"
    if "xiaomi_w2_18d1" in rest:
        return "走廊开关"
    if "xiaomi_w1_c6f1" in rest:
        return "主卫开关"
    if "arf1r1_7d48" in rest:
        return "小主人房空调"
    if "arf1r1_8044" in rest:
        return "主卧空调"
    if "arf1r1_f455" in rest:
        return "客厅空调"
    if "arf1r1_5ebb" in rest:
        return "书房空调"
    if "hyd_1s1" in rest:
        return "烟雾报警器"
    return ""

# ============================================================
# 3. 主程序
# ============================================================
print("[1] 获取 Home Assistant 设备MAC映射...")
ha_map = get_ha_mac_map()
print(f"    HA设备MAC: {len(ha_map)}个")

print("[2] 登录路由器获取设备列表...")
router_devs = get_router_devices()
print(f"    路由器在线: {len(router_devs)}台\n")

# 分类统计
categories = {"手机/平板": [], "电脑": [], "智能家居": [], "音箱": [], "路由器/NAS": [], "未知": []}

def categorize(name, ip, mac):
    name_lower = name.lower()
    mac_upper = mac.upper()
    if any(x in name_lower for x in ["手机", "iphone", "huawei", "redmi", "mi ", "xiaomi", "jpad", "db", "magic"]):
        return "手机/平板"
    if any(x in name_lower for x in ["macbook", "mac book", "air", "pro", "pc", "laptop", "surface", "gamepc", "pc"]):
        return "电脑"
    if any(x in name_lower for x in ["airplay", "tv", "roku", "appletv"]):
        return "电视"
    if any(x in name_lower for x in ["nas", "router", "synology"]):
        return "路由器/NAS"
    if any(x in name_lower for x in ["小爱", "小爱同学", "soundbox", "speaker", "redmi display", "tongxue"]):
        return "音箱"
    if any(x in name_lower for x in ["anonymous", "匿名", "unknown"]):
        return "未知"
    return "智能家居"

print("=" * 90)
print(f"{'设备名称':<28} {'IP地址':<16} {'MAC':<19} {'信号':>5} 类型")
print("-" * 90)

for h in router_devs:
    for key, info in h.items():
        mac = info.get("mac", "?")
        ip = info.get("ip", "?")
        rssi = info.get("rssi", "?")
        conn_type = "WiFi" if info.get("type") == "1" else "有线"
        ssid = info.get("ssid", "")
        if ssid:
            conn_type += f"({ssid})"
        is_cur = " ★本机" if info.get("is_cur_host") == "1" else ""

        hostname_raw = info.get("hostname", "")
        hostname = urllib.parse.unquote(hostname_raw) if hostname_raw else ""
        if not hostname or hostname in ("Anonymous", "unknown"):
            hostname = ""
        # 路由器可能把未知设备hostname设为"匿名主机"，这种情况跳过hostname，优先用HA名称
        if "匿名" in hostname or "unknown" in hostname.lower():
            hostname = ""

        # 优先用HA名称（最权威）
        # MAC格式：路由器返回54-EF-44-8F-9A-07(连字符)，HA返回54:EF:44:8F:9A:07(冒号)，统一用冒号
        lookup_key = mac.upper().replace("-", ":")
        ha_name = ha_map.get(lookup_key, "")

        if hostname:
            display_name = hostname
            source = ""
        elif ha_name:
            display_name = ha_name
            source = ""
        else:
            display_name = "⚠️ 未知设备"
            source = ""

        if info.get("is_cur_host") == "1":
            display_name += " ★本机"

        cat = categorize(display_name, ip, mac)
        print(f"{display_name:<28} {ip:<16} {mac:<19} {rssi:>5} {cat}")

print("-" * 90)
print(f"共 {len(router_devs)} 台设备")

# 保存结果
output_lines = []
output_lines.append(f"# TP-Link 路由器设备清单（HA已标识）\n")
output_lines.append(f"> 生成时间：2026-06-16 | 共 {len(router_devs)} 台在线\n\n")
output_lines.append("| # | 设备名称 | IP地址 | MAC | 信号 | 类型 | 备注 |\n")
output_lines.append("|---|----------|--------|-----|------|------|------|\n")

idx = 0
for h in router_devs:
    for key, info in h.items():
        idx += 1
        mac = info.get("mac", "?")
        ip = info.get("ip", "?")
        rssi = info.get("rssi", "?")
        conn_type = "WiFi" if info.get("type") == "1" else "有线"
        ssid = info.get("ssid", "")
        if ssid:
            conn_type += f"({ssid})"
        hostname_raw = info.get("hostname", "")
        hostname = urllib.parse.unquote(hostname_raw) if hostname_raw else ""
        if not hostname or hostname in ("Anonymous", "unknown"):
            hostname = ""
        ha_name = ha_map.get(mac.upper(), "")
        display_name = hostname or ha_name or "⚠️ 未知设备"
        cat = categorize(display_name, ip, mac)
        note = "★本机" if info.get("is_cur_host") == "1" else ""
        output_lines.append(f"| {idx} | {display_name} | {ip} | {mac} | {rssi} | {cat} | {note} |\n")

with open(r"E:\QClaw\workspace\tp-link-router-api\devices.md", "w", encoding="utf-8") as f:
    f.writelines(output_lines)

print(f"\n已保存: devices.md")
print(f"HA MAC映射数量: {len(ha_map)}")