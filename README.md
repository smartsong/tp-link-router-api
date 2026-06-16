# TP-Link 路由器 REST API 逆向工具箱

> 适用型号：TL-R488GPM-AC（理论上通用于所有使用相同固件架构的 TP-Link 路由器）

**核心成果：**
- ✅ 登录认证（自定义XOR加密，非RSA）
- ✅ 设备列表查询（38台设备全获取）
- ✅ LAN/WAN/系统信息
- ✅ 命令行工具 + Python库 + OpenClaw Skill

---

## 快速开始

```bash
# 1. 安装依赖
pip install requests

# 2. 配置（复制并编辑）
cp .env.example .env
# 编辑 .env，填入你的路由器密码

# 3. 使用
python router_cli.py devices    # 查看设备列表
python router_cli.py lan        # 查看LAN信息
python router_cli.py all       # 查看所有信息
python router_cli.py sys       # 系统信息

# 或设置环境变量（无需 .env 文件）
export TP_HOST=http://192.168.0.1
export TP_USER=admin
export TP_PASS=你的密码
python router_cli.py devices
```

---

## API 认证机制

### 1. 密码加密（自定义 XOR + 查表替换）

TP-Link 路由器的密码加密**不是RSA**，而是自定义的 `securityEncode` 算法：

```python
KEY1 = "RDpbLfCPsJZ7fiv"        # XOR 密钥
KEY2 = "yLwVl0zKqws7LgKPRQ84Mdt708T1qQ3Ha7xv3H7NyU84p21BriUWBU43odz3iP4rBL3cD02KZciXTysVXiV8ngg6vL48rPJyAUw0HurW20xqxv9aYb4M9wK1Ae0wlro510qXeU07kV57fQMc8L6aLgMLwygtc0F10a0Dg70TOoouyFhdysuRMO51yY5ZlOZZLEal1h0t9YQW0Ko7oBwmCAHoic4HYbUyVeU3sfQ1xtXcPcf1aT303wAQhv66qzW"

def encode_password(password):
    r = []
    g, m, f = len(password), len(KEY1), len(KEY2)
    for e in range(max(g, m)):
        t = l = 187
        if e >= g:  t = ord(KEY1[e])
        elif e >= m: l = ord(password[e])
        else:        l, t = ord(password[e]), ord(KEY1[e])
        r.append(KEY2[(l ^ t) % f])
    return ''.join(r)
```

### 2. 登录

```bash
POST http://192.168.0.1/
Content-Type: application/json; charset=UTF-8

{"method":"do","login":{"username":"admin","password":"<encoded>"}}
```

响应：
```json
{"error_code":0,"stok":"0cf749710a8bca252a934e7bf3aa9b0a"}
```

### 3. API 调用规则

**读操作**（`method: "get"`）和**写操作**（`method: "do"`）：

```bash
POST http://192.168.0.1/stok=<token>/ds
Content-Type: application/json; charset=UTF-8

# 读设备列表
{"hosts_info":{"table":"host_info"},"method":"get"}

# 读LAN信息
{"network":{"name":"lan"},"method":"get"}

# 重启路由器（写操作）
{"system":{"reboot":null},"method":"do"}
```

### 错误码

| 错误码 | 含义 |
|--------|------|
| 0 | 成功 |
| -40106 | 缺少 `method` 字段或认证格式错误 |
| -40209 | `method` 值错误（读操作用了 `"do"` 或 payload 格式错误） |
| -40401 | 未登录或 token 过期 |

---

## 已验证的 API 接口

| 功能 | Payload | 说明 |
|------|---------|------|
| 设备列表 | `{"hosts_info":{"table":"host_info"},"method":"get"}` | 返回所有在线设备 |
| LAN信息 | `{"network":{"name":"lan"},"method":"get"}` | IP/MAC/子网掩码 |
| WAN信息 | `{"network":{"name":"wan"},"method":"get"}` | AP模式下为空 |
| 系统信息 | `{"system":{"name":"sys_info"},"method":"get"}` | 设备型号/固件版本 |
| 运行时间 | `{"system":{"name":"uptime"},"method":"get"}` | 路由器运行时间 |
| 重启 | `{"system":{"reboot":null},"method":"do"}` | 重启路由器 |

---

## 逆向过程记录

### 2026-06-16 发现经过

1. **登录接口定位**：通过浏览器 F12 抓包，发现 `POST http://192.168.0.1/` 返回 JSON + `stok` token

2. **密码加密逆向**：
   - 从 `login.htm` 找到 JS 入口：`orgAuthPwd()`
   - 在 `web-static/js/su/lib/encrypt.js` 找到加密库（`encryptPwd`, `getPubKey`）
   - 关键发现：公钥是**硬编码**在 JS 中的，不需要从服务器动态获取
   - 最终确认算法是 **XOR + 查表**，不是 RSA

3. **API 调用规则发现**：
   - 搜索 CSDN 参考文章，发现正确格式：`method:"get"` 用于读取，`method:"do"` 用于写入
   - 之前一直用 `"do"` 读数据导致 `-40209` 错误

4. **验证成功**：
   - 设备列表返回 38 台在线设备
   - LAN/WAN/系统信息全部正常

### 关键文件位置

- `web-static/js/su/lib/encrypt.js` — 加密算法源码
- `web-static/js/su/su.js` — SU框架源码
- `login.htm` — 登录页入口

---

## 文件结构

```
tp-link-router-api/
├── README.md              # 本文件
├── router_api.py          # 核心库（登录 + API 调用）
├── router_cli.py         # 命令行工具
├── router_gui.py          # 图形界面工具（可选）
└── docs/
    └── 逆向过程.md        # 详细逆向记录
```

---

## License

MIT - 可以随意使用、修改、传播