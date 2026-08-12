# GitHub 封锁测绘案例（完整数据，2026-08-12）

来源: 家庭网络沙盒（TP-Link 网关 192.168.2.1 出口）实测。

## 测试矩阵结果

| 服务/域名 | 代表 IP | TCP:443 | TLS证书 | 传输 | 判定 |
|---|---|---|---|---|---|
| github.com | 20.205.243.166（亚太） | ✓ | CN=github.com ✓ | 200 / 572KB 完整 | ✅ 可用 |
| github.com | 140.82.112.3（美西） | ✓ | ✓ | 200 / 510KB（慢） | ✅ 可用 |
| api.github.com | 20.205.243.168 | ✓ | ✓ | 200 / 199KB | ✅ 可用 |
| codeload.github.com | 20.205.243.165 | ✓ | ✓ | 200（大文件龟速） | ✅ 可用 |
| raw.githubusercontent.com | 185.199.108~111.133 ×4 | ✓ | ✓ 握手通 | 000 / 0 字节 | ❌ 封锁 |
| gist.github.com | 20.205.243.166 | ✓ | ✓ | 000 / 0 字节 | ❌ 封锁 |
| objects.githubusercontent.com | 185.199.109.133 | ✓ | ✓ | 404 / 425B | ✅ 可用 |
| github.io | 185.199.110.133 | ✓ | CN=*.github.io | 301 | ✅ 可用 |
| SSH 22 | 20.205.243.166 / 140.82.112.3 | ✓ | — | SSH-2.0-dad0df6 | ✅ 可用 |
| HTTP 80 | github.com | ✓ | — | 301 | ✅ 可用 |

## DNS 交叉验证

- 系统/8.8.8.8/1.1.1.1/223.5.5.5/114.114.114.114/119.29.29.29 + TCP 53: 全部一致
- 解析结果 20.205.243.x → meta 官方列表核对 = **官方 Azure 亚太节点**（非污染）
- DoH (cloudflare-dns.com) 可用，返回美西 140.82.121.x（GeoDNS 双节点）
- 结论: DNS 无污染

## 封锁规律（关键证据链）

1. **SNI 层封锁**:
   - raw 4 IP TCP/TLS 握手全部成功（证书正常）→ HTTP 0 字节
   - 同网段 185.199.109.133: objects SNI 返回 404 内容 vs raw SNI 0 字节
   - → 封锁发生在 TLS 首包后的数据阶段（GFW SNI 指纹阻断）
2. **限速排除**（对照组）: debian 镜像 261B/s、阿里云 5.8KB/s 同慢 → 环境带宽限制
3. **大文件**: linux tarball 30s 仅 1.5MB（exit 28 超时）= 限速非掐断
4. **git clone 实测成功**: smart HTTP 单连接走 github.com（info/refs 200 → git-upload-pack），不依赖 raw

## 复现命令

```bash
# 封锁判定（0字节）
curl -s --resolve raw.githubusercontent.com:443:185.199.108.133 -m 10 \
  -o /dev/null -w '%{http_code} %{size_download}' https://raw.githubusercontent.com/
# 可用判定
curl -s --resolve github.com:443:20.205.243.166 -m 10 -o /dev/null \
  -w '%{http_code} %{size_download}' https://github.com/
# SSH banner
printf 'SSH-2.0-test\r\n' | nc -w 5 github.com 22
```

## 教训

1. 不要把"慢"当封锁——必须做对照组
2. 不要把解析结果当污染——先核对官方 meta 列表（20.205.243.x 是官方节点！）
3. 封锁判定必须做**实际传输**测试，握手通过不代表可用
4. git 功能可用性 ≠ 全域名可用（smart HTTP 绕开 raw）
5. DoH 是 DNS 劫持环境下的真值来源（dns.google 常被墙，cloudflare-dns.com 更稳，dns.lemdns.com 最稳）

## 动态封锁时序数据（20 分钟监测，20s 间隔，21 轮）

### 可用率分层
| 节点 | 可用率 | 层 |
|---|---|---|
| api.github.com (20.205.243.168) | 100% | 稳定可用 |
| raw (185.199.108.133) | 61% | 间歇 |
| github.com 美西112 | 38% | 间歇 |
| github.com 亚太.166 | 28% | 间歇 |
| github.com 美西121 | 0% | 持久封锁 |
| gist (140.82.121.4) | 0% | 持久封锁 |

### 窗口参数
- 封禁期: 3-5 分钟（样本 1/3/4/4/5 分钟）
- 解封期: 4-12 分钟
- github.com 主站节点同步率: 71%（域名级规则 + 边界 1-2 轮漂移）
- raw 与 github.com 窗口独立（分域名规则）

### 触发机制（对照实验）
- 停止探测 3 分钟 → 封锁状态不变 → 外部时间驱动，非探测触发
- api 同频探测（20s/轮 × 21 轮）从未封锁 → 频率不是触发因素

### gist DNS 污染池（4 IP 轮换）
78.16.49.15（长驻 13 轮）/ 159.24.3.173（6 轮）/ 37.61.54.158 / 243.185.187.39 —— 全部不可达

### 重试策略（按窗口参数设计）
1. api 通道: 无需重试（100% 可用）
2. github.com 主站: 60s 间隔重试（封锁窗 3-5 分钟自动解除）
3. raw: 失败后等 5-10 分钟重试
4. 140.82.121.x / gist: 视为永久不可用，直接绕行
