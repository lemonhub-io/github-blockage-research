# GitHub Blockage Research

> GitHub 网络可达性与封锁状况的实证研究（IPv4 + IPv6 双栈）
> 环境：授权沙盒（家庭网络模拟）| 日期：2026-08-12 | 许可：MIT

## 项目简介

本仓库沉淀一次完整的**网络封锁测绘研究**：通过官方 IP 基准、DNS 交叉验证（含 DoH 评测）、IPv4/IPv6 双栈传输层实测与高频时序监测，量化 GitHub 生态各域名/IP 在真实网络环境下的可达性分布，归纳出可预测的**动态封锁规律**，并验证 **IPv6 作为绕行通道**的可行性。

**方法一句话**：DNS 拿真值（海外 DoH）→ 握手验身份 → 传输判封锁 → 时序找规律 → 对照验机制 → IPv6 找出口。

---

## 核心规律

### 1. 三层封锁结构（IPv4，21 轮时序监测）

| 层级 | 对象 | 实测可用率 | 特征 |
|---|---|---|---|
| 🟢 稳定可用 | `api.github.com` 亚太节点 (`20.205.243.168`) | **100%** | 全程无封锁窗口 |
| 🟡 间歇封锁 | `github.com` 主站节点、`raw.githubusercontent.com` | 28–61% | 封禁/解封循环 |
| 🔴 持久封锁 | `140.82.121.x` 段、`gist.github.com` | **0%** | 全程不可达 |

### 2. 窗口参数（时序监测实测）

```
封禁期   3–5 分钟（样本：1/3/4/4/5 分钟）
解封期   4–12 分钟
主站节点同步率   71%（域名级规则 + 边界 1–2 轮漂移）
跨域名同步       独立（raw 与 github.com 窗口不同步）
```

### 3. 封锁粒度与触发机制

- **IP 级**：同段 `.166` 封锁时 `.168` 正常（20.205.243.x）
- **域名/SNI 级**：gist 在所有可用 IP 上均 0 字节
- **非探测触发**：对照实验（停止探测 3 分钟状态不变）证明封锁由**外部时间驱动规则**产生；同频探测的 api 节点全程未被封锁，排除频率因素

### 4. DNS 污染（gist 专属，A/AAAA 双栈）

- 本地 DNS 与**国内 DoH 均被污染**：解析到轮换的不可达 IP 池（≥5 个），AAAA 投毒为 `2001::1` 黑洞
- **海外 DoH（dns.lemdns.com）返回真值** `140.82.121.4`——唯一可靠真值源

### 5. IPv6 双栈发现（附录 C）

| 服务 | IPv4 | IPv6 |
|---|---|---|
| raw.githubusercontent.com | 间歇封锁 | **`2606:50c0:8001::154` 稳定可用**（绕行通道） |
| pages.github.com | 稳定 | `2606:50c0:8001::153` 可用 |
| github.com 主站 | 间歇封锁 | 无 AAAA（纯 IPv4） |
| gist | 持久封锁 + 污染 | 无 IPv6 通道 |

**IPv6 出口可用（隧道/NAT）且封锁面更小**——IPv4 封锁窗口内强制 `-6` 可稳定获取 raw/pages 内容。

### 6. 工程结论（重试/绕行策略）

| 场景 | 策略 |
|---|---|
| API 自动化 | 固定走 IPv4 亚太 api，无需重试 |
| raw 文件下载 | **IPv6 绕行**（`-6 --resolve ...[2606:50c0:8001::154]`），或 IPv4 等 5–10 分钟 |
| git clone / 主站 | IPv4 亚太/美西 + 60s 间隔重试 |
| 140.82.121.x / gist | 视为永久不可用，直接绕行 |

---

## 方法论

### 阶段流程

1. **官方 IP 基准** — 从 `api.github.com/meta` 获取官方 IPv4/IPv6 CIDR（7669 条），作为判定"污染"的准绳
2. **DNS 交叉验证** — 系统 DNS / 公共 DNS / TCP 53 / **海外 DoH** 四层对比；国内 DoH（阿里/腾讯）对封锁域名同样返回污染结果
3. **TCP 连通性** — 多线程批量探测（IPv4/IPv6 双栈）
4. **TLS 证书身份验证** — 区分真服务、中间人与 mTLS
5. **传输层实测**（判定核心）— `--resolve` 强制指定 IP 做真实 HTTPS 请求；**0 字节 = 传输层封锁**（TCP/TLS 握手通过不代表可用）
6. **限速对照** — 同测国内源，区分"环境带宽限制"与"目标限速"
7. **功能级验证** — git clone / SSH 全握手实测
8. **时序分析**（动态封锁）— 20s 间隔多节点采样 ≥20 分钟 → 可用率分层 / 窗口时长分布 / 同步性分析
9. **对照实验** — 停止探测 3–5 分钟，判定封锁是外部规则还是探测触发
10. **IPv6 对照** — AAAA 污染检测 + IPv6 传输矩阵，验证绕行通道

### 关键教训

- 不要把"慢"当封锁（对照组是刚需）
- 不要把解析结果当污染（先核对官方列表，`20.205.243.x` 就是官方节点）
- 国内 DoH 不可信（阿里对 gist 返回污染 IP）——真值必须走海外 DoH
- 单次测量只是快照，动态封锁必须看时间线
- IPv6 封锁面更小，是 IPv4 封锁的有效绕行通道

---

## DoH 推荐（详见 [DOH.md](DOH.md)）

| 服务 | 可用 | 评级 |
|---|---|---|
| **dns.lemdns.com** | ✅ 稳定 | ⭐ 首选（海外真值，未被污染） |
| doh.pub / dns.alidns.com | ✅ 可用 | ⚠️ 国内视角，封锁域名返回污染 |
| cloudflare-dns.com / dns.google / 1.1.1.1 | ❌ 被墙 | ✗ 当前环境不可用 |

---

## 项目结构

```
├── GITHUB_BLOCK_REPORT.md      # 完整研究报告（附录 A: DoH扩展 / B: 时序规律 / C: IPv6研究）
├── github-case-study.md        # 案例笔记：方法论 + 完整数据
├── DOH.md                      # DoH 服务评测与推荐
├── connectivity_probe.py       # 批量 TCP 连通性探测
├── blockage_monitor.py         # 封锁时序监测（多节点 + DNS 轮换记录）
├── gh_connectivity.py          # GitHub 专项连通性测试
├── gh_monitor.py               # GitHub 专项时序监测（简化版）
├── gh_monitor.csv              # 21 轮监测原始数据
├── LICENSE                     # MIT
└── README.md
```

## 快速开始

```bash
# 1. 批量 TCP 连通性测试
python3 connectivity_probe.py 140.82.112.3 140.82.121.3 --ports 443

# 2. 封锁判定（传输层实测，0 字节 = 封锁）
curl -s --resolve github.com:443:20.205.243.166 -m 10 \
  -o /dev/null -w '%{http_code} %{size_download}' https://github.com/

# 3. 海外 DoH 真值（DNS 污染环境下的可靠解析）
curl -s -H "accept: application/dns-json" \
  "https://dns.lemdns.com/dns-query?name=gist.github.com&type=A"

# 4. IPv6 绕行下载 raw 文件（IPv4 封锁窗口内）
curl -6 --resolve raw.githubusercontent.com:443:[2606:50c0:8001::154] \
  -m 15 -o file https://raw.githubusercontent.com/<owner>/<repo>/master/<path>

# 5. 动态封锁时序监测（20s 间隔 × 45 轮 ≈ 15 分钟）
python3 blockage_monitor.py 20 45 monitor.csv
```

## 许可

[MIT](LICENSE) © 2026 lemonhub-io
