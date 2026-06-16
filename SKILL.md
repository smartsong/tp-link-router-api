# SKILL.md — TP-Link 路由器控制

> 通过 REST API 控制 TP-Link TL-R488GPM-AC 路由器

## 工作原理

TP-Link 路由器提供 JSON API，认证方式：
1. **密码加密**：自定义 XOR + 查表（不是 RSA）
2. **登录**：`POST /` 获取 `stok` token
3. **API调用**：`POST /stok=<token>/ds`
   - 读操作用 `method: "get"`
   - 写操作用 `method: "do"`

## 快速使用

### 查看设备列表
```bash
python E:\QClaw\workspace\tp-link-router-api\router_cli.py devices
```

### 查看所有信息
```bash
python E:\QClaw\workspace\tp-link-router-api\router_cli.py all
```

### 在 Python 中使用
```python
from router_api import TPLinkRouter

router = TPLinkRouter(
    host="http://192.168.0.1",
    username="admin",
    password="Smartsong771211"
)
router.login()
devices = router.get_devices()
print(router.format_devices(devices))
```

## 路由器配置

| 字段 | 值 |
|------|-----|
| 地址 | `http://192.168.0.1` |
| 用户名 | `admin` |
| 密码 | `Smartsong771211` |
| LAN MAC | `9C-47-82-2E-57-72` |

## 可用命令

| 命令 | 说明 |
|------|------|
| `devices` | 查看所有在线设备（IP/MAC/主机名/信号强度） |
| `lan` | 查看 LAN 信息（IP/子网/MAC） |
| `wan` | 查看 WAN 信息 |
| `sys` | 查看系统信息（型号/固件/运行时间） |
| `all` | 查看所有信息 |
| `login` | 测试登录 |
| `reboot` | 重启路由器（需确认） |

## 注意事项

- 路由器位于 `192.168.0.1`，当前登录设备 `smartgamepc` 在 `192.168.0.38`
- 有线连接设备 MAC 以 `C4-BD-E5` 开头
- 已知在线设备 38 台，包括智能家居（网关/摄像头/音箱/灯/窗帘等）
- WiFi 信息接口部分型号不支持（返回 -40209）

## 脚本位置

- 核心库：`E:\QClaw\workspace\tp-link-router-api\router_api.py`
- CLI工具：`E:\QClaw\workspace\tp-link-router-api\router_cli.py`
- 仓库：https://github.com/smartsong/tp-link-router-api