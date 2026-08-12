# GitHub IP 封锁状况分布报告
日期: 2026-08-12 | 测试环境: 家庭网络沙盒（TP-Link 网关 192.168.2.1 出口）

## 0. 测试方法论

1. **官方 IP 基准**: 从 `api.github.com/meta` 获取 GitHub 官方 IP 列表（git 46 / web 26 / api 26 / hooks 6 / pages 10 / importer 5 / actions 7297）
2. **DNS 层**: 系统 DNS + 5 个公共 DNS（8.8.8.8/1.1.1.1/223.5.5.5/114.114.114.114/119.29.29.29）+ DoH（cloudflare）对比
3. **连通性**: TCP connect（4s 超时）→ TLS 握手（证书身份验证）→ HTTPS 实际传输（字节数/exit code）
4. **判定标准**: 完整传输=可用；TCP/TLS 通但 0 字节=封锁；超时=不可达

## 1. DNS 解析状况：✅ 正常（无污染）

| 查询 | 系统DNS | 8.8.8.8 | 1.1.1.1 | 223.5.5.5 | DoH真值 |
|---|---|---|---|---|---|
| github.com | 20.205.243.166 | 同左 | 同左 | 同左 | 140.82.121.x |
| api.github.com | 20.205.243.168 | 同左 | 同左 | 同左 | 140.82.121.5 |
| raw.githubusercontent.com | 185.199.108-111.133 | 同左 | 同左 | 同左 | — |
| codeload.github.com | 20.205.243.165 | 同左 | 同左 | 同左 | 140.82.121.10 |

- 所有解析结果均为 **GitHub 官方 IP**（meta 列表核对确认，20.205.243.x 为官方 Azure 亚太节点）
- 结论: **DNS 无污染、无劫持**（UDP/TCP 53 一致，GeoDNS 正常分配亚太节点）

## 2. 连通性分布矩阵（核心）

| 服务/域名 | 代表 IP | TCP:443 | TLS证书 | 实际传输 | **判定** |
|---|---|---|---|---|---|
| github.com（主站） | 20.205.243.166（亚太） | ✓ | CN=github.com ✓ | **200 / 572KB 完整** | ✅ **可用** |
| github.com（主站） | 140.82.112.3（美西） | ✓ | ✓ | 200 / 510KB 完整 | ✅ 可用（慢） |
| api.github.com | 20.205.243.168 | ✓ | ✓ | 200 / 199KB 完整 | ✅ **可用** |
| codeload.github.com | 20.205.243.165 | ✓ | ✓ | 200（大文件龟速） | ✅ 可用（受限） |
| **raw.githubusercontent.com** | **185.199.108~111.133（4IP全测）** | ✓ | ✓ 握手完成 | **000 / 0 字节** | ❌ **封锁** |
| **gist.github.com** | 20.205.243.166 | ✓ | ✓ | **000 / 0 字节** | ❌ **封锁** |
| objects.githubusercontent.com | 185.199.109.133 | ✓ | ✓ | 404 / 425B | ✅ 可用 |
| github.io（Pages） | 185.199.110.133 | ✓ | CN=*.github.io ✓ | 301 | ✅ 可用 |
| GitHub IPv6 | 2606:50c0:8001::153 | ✓ | — | — | ✅ 可用 |
| GitHub 官方 IPv6 | 2a0a:a440::5 | ✗ 超时 | — | — | ⚠️ 未验证（地址不确定） |

## 3. 端口分布

| 端口 | 服务 | 结果 |
|---|---|---|
| 443/tcp | HTTPS（主站/API/codeload/objects/pages） | ✅ 部分域名可用 |
| 443/tcp | HTTPS（raw/gist SNI） | ❌ 传输层封锁 |
| 22/tcp | SSH (git over SSH) | ✅ **可用**（banner: SSH-2.0-dad0df6，两节点验证） |
| 80/tcp | HTTP（明文） | ✅ 可用（301 → HTTPS） |

## 4. 封锁规律分析

### 4.1 封锁是 SNI 层（七层）阻断，非 IP 层
- **证据**: raw 的 4 个 IP（185.199.108~111.133）TCP/TLS 握手全部成功（证书正常），但 HTTP 传输 **0 字节**；同一网段 185.199.109.133 以 objects SNI 访问却返回 404 内容
- **特征**: 握手完成 → 首包后连接被 RST/静默丢弃（GFW TLS SNI 阻断典型行为）
- **被封锁 SNI**: `raw.githubusercontent.com`（全部 4 IP）、`gist.github.com`
- **未封锁 SNI**: github.com / api.github.com / codeload.github.com / objects.githubusercontent.com / *.github.io

### 4.2 传输限速（与封锁区分）
- github.com 大文件实测 ~50KB/s；但**国内源同样慢**（debian 镜像 261B/s、阿里云 5.8KB/s）→ 属于环境出口带宽限制，**非 GitHub 专属封锁**
- 判定方法: 对照组测试（国内源 vs 目标源）

### 4.3 git 功能可用性（实测）
| 操作 | 结果 | 说明 |
|---|---|---|
| `git clone https://github.com/...` | ✅ **成功** | smart HTTP 全程走 github.com 同一连接（info/refs 200 → git-upload-pack），不依赖 raw |
| 下载 raw 文件 | ❌ 失败 | 依赖被封锁的 raw SNI |
| git over SSH | ✅ 可用 | ssh.github.com 等价（22 端口 banner 正常） |
| 下载 release 资产 | ✅ 可用 | objects SNI 未封锁 |

## 5. 结论与建议（封堵/优化视角）

### 封锁面（需要规避）
1. **raw.githubusercontent.com** — 文件直链下载的唯一封锁点；规避: 走 `github.com/owner/repo/raw/...` 网页路径或 codeload tarball
2. **gist.github.com** — 代码片段服务封锁；规避: 转移至 repo 存储

### 可用面（无需代理）
- 主站浏览、API、git clone/push（HTTPS & SSH）、release 下载、Pages — **全部原生可用**
- 若 git 操作失败: 优先检查**节点切换**（140.82.x 美西 vs 20.205.243.x 亚太），亚太节点更快更稳

### 优化建议
1. git 全局配置走亚太节点（或 SSH 协议，已验证双向可用）
2. 需要 raw 直链时用 `gh api`（api.github.com 未封锁）或 codeload 替代
3. 无需额外代理即可完成常规开发流程；仅 raw/gist 需替代方案

## 6. 复测方法
```bash
# 封锁判定（0字节=封锁）
curl -s --resolve raw.githubusercontent.com:443:185.199.108.133 -m 10 \
  -o /dev/null -w '%{http_code} %{size_download}' https://raw.githubusercontent.com/
# 可用性判定
curl -s --resolve github.com:443:20.205.243.166 -m 10 -o /dev/null \
  -w '%{http_code} %{size_download}' https://github.com/
```

---

# 附录 A：DoH 扩展研究（dns.lemdns.com）——动态封锁发现

## 方法
- 真值源: `https://dns.lemdns.com/dns-query`（RFC 8484, 返回官方美西节点）
- 与本地 DNS 对比 → 发现 **gist.github.com 本地解析污染**（203.98.7.65 → 8.7.198.45 → 37.61.54.158，全不可达且轮换，均为非官方 IP）
- 用 DoH 真值 IP 做 --resolve 传输实测（多轮次，验证时间动态性）

## 核心发现：封锁是动态演进的

### 时间线（同一测试环境）
| 时间 | github.com 主站 | api.github.com | raw.githubusercontent | gist.github.com | 备注 |
|---|---|---|---|---|---|
| T-2h | ✅ 亚太/美西通 | ✅ | ❌ 0B | ❌ 0B + DNS污染 | 首轮测绘 |
| T-1h | ✅ 亚太通 / ❌ 美西121 | ✅ | ❌ | ❌ | 美西段部分封锁 |
| T0 | ❌ 全封(亚太.166+美西全段) | ✅ 亚太.168 | ✅ 解封 | ❌ | 封锁扩大+raw解封 |
| T+3m | ✅ 恢复(亚太.166/美西112) | ✅ | ✅ | ❌ | github恢复,gist持续封 |

### 封锁规律（修正版）
1. **gist.github.com：持续性封锁** — 全程不可达；DNS 被投毒到轮换的不可达 IP（GFW 毒化特征）
2. **github.com 主站：间歇性封锁窗口** — 封禁→解封周期（分钟~小时级）；封锁期间亚太+美西全部 IP 传输 0 字节
3. **raw.githubusercontent.com：动态变化** — 先前封锁 → 后解封（根路径 301/文件 200 稳定）
4. **api.github.com：亚太节点稳定可用**（20.205.243.168 全程 200）
5. **140.82.121.x 段：封锁较持久**（与主站封锁联动）
6. **封锁粒度：IP 级**（20.205.243.166 封时 .168 通；140.82.121.x 封时 112/114/116 通）

### 功能影响（实测）
| 功能 | T0(封锁窗) | T+3m(恢复后) |
|---|---|---|
| git clone (https) | ❌ 失败 | ✅ 成功 |
| API 调用 | ✅（走亚太 api） | ✅ |
| raw 文件下载 | ✅（已解封） | ✅ |
| gist | ❌ | ❌ |

## 结论更新
1. **封锁是动态的**——单次测量只能反映瞬时状态；"封堵漏洞"视角需多时点测绘
2. **持续性封锁面**：gist.github.com（DNS 污染 + 传输阻断双重）
3. **间歇性封锁面**：github.com 主站（窗口期 0 字节）、raw（历史有封锁记录）
4. **稳定可用面**：api.github.com（亚太）、codeload、objects、pages
5. **DNS 污染检测法**：本地解析 vs DoH 真值对比；污染 IP 特征 = 非官方 + 不可达 + 轮换
6. **DoH 选择**：dns.lemdns.com 可用稳定；dns.google 被墙；cloudflare-dns.com 部分域名不响应

## 复测命令
```bash
# DoH 真值
curl -s -H "accept: application/dns-json" "https://dns.lemdns.com/dns-query?name=gist.github.com&type=A"
# 多时点封锁监测（定时跑）
while true; do
  curl -s --resolve github.com:443:20.205.243.166 -m 8 -o /dev/null \
    -w "$(date +%H:%M:%S) github: %{http_code} %{size_download}\n" https://github.com/
  sleep 60
done
```

---

# 附录 B：封锁时序规律分析（21 轮高频监测 + 对照实验）

## 方法
- 6 节点并行监测：github.com(亚太.166/美西112/美西121) + api(亚太.168) + raw(文件路径) + gist(美西)
- 20s 间隔 × 21 轮 ≈ 20 分钟；每轮同时记录 gist DNS 解析
- 对照实验：停止探测 3 分钟 → 状态不变 → **排除"探测触发封锁"**

## 时序数据摘要

| 节点 | 可用率 | 封锁窗口 | 结论 |
|---|---|---|---|
| api.github.com (20.205.243.168) | **100%** | 无 | **持久可用** |
| raw.githubusercontent.com | 61% | 03:38-43, 03:56-至今 | 间歇（窗口≥5min） |
| github.com 美西112 | 38% | 03:41-45, 03:46-47, 03:48-51, 03:54-至今 | 间歇 |
| github.com 亚太.166 | 28% | 03:42-46, 03:48-至今 | 间歇 |
| github.com 美西121 | **0%** | 全程 | **持久封锁** |
| gist.github.com | **0%** | 全程 | **持久封锁** |

## 规律提炼

### 1. 三层封锁结构
- **持久封锁层**：gist（域名级 + DNS 污染池轮换）、140.82.121.x（IP 段级）
- **间歇封锁层**：github.com 主站节点（窗口 3-5 分钟）、raw
- **稳定可用层**：api 亚太（全程 100%）

### 2. 窗口参数
- **封禁期**：3-5 分钟（实测 1/3/4/4/5 分钟）
- **解封期**：4-12 分钟
- **github.com 主站节点同步性**：71%（域名级规则 + 边界 1-2 轮漂移）
- **不同域名窗口独立**（raw 与 github.com 不同步）

### 3. 触发机制（对照实验证明）
- 停止探测 3 分钟 → 封锁状态不变 → **外部时间驱动，非探测触发**
- api 同频探测（20s/轮）从未封锁 → 频率不是因素

### 4. DNS 污染池（gist 专用）
| 污染 IP | 出现轮次 | 特征 |
|---|---|---|
| 78.16.49.15 | 13 轮（长驻） | 不可达 |
| 159.24.3.173 | 6 轮 | 不可达 |
| 37.61.54.158 / 243.185.187.39 | 各 1 轮 | 不可达 |

### 5. 可预测的使用策略
1. **api 通道**：随时可用（20.205.243.168），自动化首选
2. **github.com 主站**：间歇封锁——重试策略按窗口（封禁 3-5 分钟→解封 4-12 分钟），重试间隔建议 60s 以上
3. **raw**：间歇窗口，文件下载失败后 5-10 分钟重试成功率最高
4. **140.82.121.x / gist**：视为永久不可用，直接绕行（gist 用 repo 替代）

## 监测复现
```bash
python3 gh_monitor.py 20 45 gh_monitor.csv   # 20s间隔 45轮
# 对照实验: kill 监测 → 停3分钟 → 单轮探测对比状态
```

---

# 附录 C：IPv6 封锁状况与可达性研究

## 环境 IPv6 能力
- 无全局 IPv6 地址、无 IPv6 路由表项（仅 link-local）
- **IPv6 出口经隧道/NAT 可用**（实测 aliyun `2400:3200::1`、baidu `240e:...` 均可达）

## AAAA 解析状况（本地 vs DoH）

| 域名 | 本地 AAAA | DoH 真值 | 判定 |
|---|---|---|---|
| gist.github.com | **`2001::1`** | 无 AAAA 记录 | ❌ **污染**（RFC 保留黑洞地址） |
| raw.githubusercontent.com | `2606:50c0:800x::154` | 同左 | ✅ 正常（Fastly） |
| avatars / pages.github.com | `2606:50c0:800x::153/154` | 同左 | ✅ 正常 |
| github.com / api / codeload / objects | 无 | 无 | 纯 IPv4，无 IPv6 |

**关键**：`2001::1` 为 RFC 保留地址（GFW 经典投毒目标），实测不可达——IPv6 DNS 同样存在污染，且**针对 gist 域名**。

## IPv6 连通性分布

| 目标 | TCP 443 | 传输实测 | 判定 |
|---|---|---|---|
| `2606:50c0:8001::154` (raw) | ✅ | **200 / 10071B 完整** | ✅ 可用 |
| `2606:50c0:8002::154` (avatars) | ✅ | 302 | ✅ 可用 |
| `2606:50c0:8001::153` (pages) | ✅ | **200 / 14446B 完整** | ✅ 可用 |
| `2606:50c0:8000::154` (raw) | ❌ 超时 | 000 | ⚠️ 路由不可达 |
| `2606:50c0:8002::153` (pages) | ✅ | 000 | ⚠️ 传输不可达 |
| `2a0a:a440::/29` 抽样 8 地址 | ❌ 全超时 | — | 未分配实际服务（猜测地址） |

## IPv4 vs IPv6 对照（核心发现）

| 服务 | IPv4 状态（时序监测 21 轮） | IPv6 状态（实测） |
|---|---|---|
| raw.githubusercontent.com | 间歇封锁（可用率 61%，窗口 3-5 分钟） | **8001::154 稳定可用**（多轮全 200） |
| pages.github.com | 稳定可用 | 8001::153 可用 |
| gist.github.com | 持久封锁 + AAAA/A 双重 DNS 污染 | 无 IPv6 通道（域名无 AAAA，A 被污染） |

**结论**：
1. **IPv6 是 IPv4 封锁的有效绕行通道**（对 raw/avatars/pages 等 Fastly 服务）——IPv4 封锁窗口内，强制 `-6` 走 `2606:50c0:8001::154` 可稳定获取内容
2. IPv6 下封锁面明显更小（主要是路由不可达，非主动阻断）
3. **IPv6 DNS 同样被投毒**（gist AAAA → 2001::1）——DoH 检测对 AAAA 同样必要
4. github.com 主站无 IPv6（纯 IPv4），IPv6 绕行不适用于主站

## 使用建议
```bash
# IPv4 封锁窗口内下载 raw 文件（IPv6 绕行）
curl -6 --resolve raw.githubusercontent.com:443:[2606:50c0:8001::154] \
  -m 15 -o file https://raw.githubusercontent.com/<owner>/<repo>/master/<path>
# git 配置走 IPv6（若支持）
git config --global http.https://github.com.proxy ""  # 无代理时
```

---

# 附录 D：方法论复测验证（05:58，间隔 ~2 小时）

## 快照对比

| 维度 | 首次监测(03:38-04:00) | 复测(05:58-06:00) | 结论 |
|---|---|---|---|
| 官方 IP 列表 | 7611 CIDR | 7611（meta 重新拉取） | ✅ 无变化 |
| api.github.com 亚太 .168 | 100% 可用 | 200 / 199KB | ✅ 稳定层确认 |
| gist.github.com | 持久封 + 污染轮换 | 000 + 污染池轮换(203.98.7.65) | ✅ 持久层确认 |
| 140.82.121.x 段 | 持久封（TCP 通/传输 0B） | **TCP 超时 + 0B** | ⚠️ 封锁加深至 TCP 层 |
| github.com 亚太 .166 | 间歇窗口 | 000（封锁窗中） | 🔄 窗口状态轮换 |
| github.com 美西 112.3 | 间歇窗口 | **200 / 195KB（解封）** | 🔄 窗口状态轮换 |
| raw.githubusercontent.com | 间歇窗口 | 200 / 10KB（解封） | 🔄 窗口状态轮换 |
| IPv6 raw (8001::154) | 稳定可用 | 200 / 10KB | ✅ 绕行通道稳定 |
| git clone | 随窗口成功/失败 | 失败（亚太封窗中） | ✅ 与窗口联动 |
| DNS 解析 | gist 污染其余正常 | 完全一致 | ✅ 无变化 |
| CF 边缘位置 | AMS/FRA | AMS | ✅ 无变化 |

## 复测结论

1. **三层封锁结构完全复现**：稳定可用层（api 亚太）、间歇窗口层（github.com/raw，各 IP 窗口独立轮换）、持久封锁层（gist + 140.82.121.x）——与 2 小时前监测结论一致
2. **窗口状态已轮换**：上次亚太封/美西112封/raw解封 → 本次亚太封/美西112解封/raw解封——印证"IP 级独立窗口 + 持续轮换"规律
3. **封锁加深案例**：140.82.121.x 从"TCP 通/传输 0B"变为"TCP 超时"——持久封锁层可能从传输层升级到连接层（待多时点确认）
4. **稳定项零变化**：api、IPv6 绕行、DNS 污染模式、CF 边缘——4 项完全稳定
5. **方法论有效性验证**：按照 skill 流程（基准→DNS→TCP→传输→功能）一次跑通，5 分钟内完成全量判定——**单次快照 + 窗口规律知识即可预测当前状态**，无需完整 20 分钟监测

## 实用提示（复测时点）

- 当前（05:58 快照）github.com 主站：走**美西 112.3** 可用，亚太在封——git clone 失败时先切节点
- git clone 失败 = 主站窗口内（本次验证），60s 后重试或 `git config http.https://github.com/ 192.168.2.1` 类节点切换（或 SSH 通道）
- raw 与 IPv6 通道当前均可用，文件下载无阻碍

---

# 附录 E：封锁机制指纹研究（分层阻断画像）

## 实验方法
- 分阶段探测：TCP 连接 → TLS 握手 → HTTP 请求 → 传输（Python socket/ssl 手工控制）
- 隔离实验：同一正常 IP × 不同 SNI（分离"IP 封锁"与"SNI 封锁"）
- 错误类型区分：RST 注入（ConnectionReset/EOF）vs 静默丢弃（timeout）
- 3 轮重复 × 10s 间隔消除网络抖动

## 核心发现：两种截然不同的封锁机制

### 机制一：SNI 握手层阻断（gist.github.com，持久规则）
```
指纹: TCP ✅ → TLS ClientHello 后 ❌ EOF/RST（握手被掐）
```
- **跨 IP 稳定复现**：Azure 亚太(.166/.168)、Fastly(.109/.108.153)、GitHub 美西(112.3) 全部命中
- 与目标 IP 无关——**纯 SNI 黑名单**（GFW 明文 ClientHello 检测）
- 附加：A/AAAA 双 DNS 污染（轮换池 + 2001::1 黑洞）
- TLS 1.3 的 ClientHello 更大，EOF 触发更明显（1.2 偶发超时）

### 机制二：间歇窗口多层阻断（github.com / raw，窗口规则）
```
封锁窗口内: 动态穿越 TCP/TLS/HTTP 层
  - 连接层: TCP 超时（最深）
  - 握手层: TLS EOF
  - 传输层: TLS ✅ → HTTP 静默丢弃（最浅）
```
- **github 亚太实测**：06:13 全通(200×3) → 06:15 TCP 超时 → 06:17-06:20 持续 000——窗口切换分钟级
- 窗口参数与附录 B 一致（封禁 3-5 分钟 +）
- IP 级独立窗口（亚太/美西不同步，附录 D 已证）

### 机制三：连接层持久封锁（140.82.121.x，加深中）
```
指纹: TCP 超时（连接建立即失败）
```
- 附录 D 观察：从"传输层 0B"升级为"TCP 超时"——封锁深度加深

## 分层阻断模型

| 封锁层 | 指纹特征 | 代表目标 | 规则类型 |
|---|---|---|---|
| DNS 层 | A/AAAA 投毒为不可达 IP | gist | 持久 |
| 连接层 | TCP 超时（静默丢弃） | 140.82.121.x、github 窗口深处 | 持久/窗口 |
| 握手层 | TCP✅→TLS-EOF（RST 注入） | gist（任何 IP）、github 窗口 | 持久/窗口 |
| 传输层 | TLS✅→HTTP 0 字节（静默丢弃） | github/raw 窗口 | 窗口 |

**判定要点**：
- TLS-EOF 且 TCP 正常 = SNI 握手层封锁（持久规则，换 IP 无效）
- TLS 正常但 HTTP 0B = 传输层窗口封锁（换 IP 可能有效）
- TCP 超时 = 连接层封锁（最深，等窗口或换段）

## 附：api.github.com 稳定性修正
- 高频探测期出现罕见瞬时 000（复查 2/3 轮恢复 200）
- 结论修正：api 亚太**高可用（>99%）但非绝对**——自动化仍建议轻量重试（1 次即可）

## 实用价值
1. **指纹判定封锁类型**：一次探测（TCP/TLS/HTTP 三段）即可判断是"持久 SNI 规则"（换 IP 无用）还是"窗口规则"（换 IP/等待有效）
2. **gist 换 IP 无效**（SNI 级）——绕行只能走非 gist 域名
3. **github 窗口期换节点有效**（IP 级窗口独立）——自动化应多节点轮询
4. **IPv6 通道独立**（附录 C）：raw IPv6 在 IPv4 封锁时仍可用

---

# 附录 F：多域名封锁机制对比 + 污染池 ASN 画像

## 1. 多域名机制指纹矩阵（三阶段探测）

| 域名 | TCP | TLS | HTTP | 封锁层 | 规则类型 |
|---|---|---|---|---|---|
| google.com | ❌超时 | - | - | **连接层** | IP 段整体封锁（最严） |
| youtube.com | ❌超时 | - | - | **连接层** | 同上 |
| twitter.com / x.com | ✅ | ✅ | ❌RST | **传输层** | 数据阶段检测（最松） |
| facebook.com | ✅ | ❌EOF | - | **握手层** | SNI 黑名单 |
| instagram.com | ✅ | ❌EOF | - | **握手层** | SNI 黑名单 |
| wikipedia.org | ✅ | ❌EOF | - | **握手层** | SNI 黑名单 |
| gist.github.com | ✅ | ❌EOF | - | **握手层** | SNI 黑名单（+DNS污染） |
| github.com | 窗口动态 | 窗口动态 | 窗口动态 | 三层穿越 | 间歇窗口 |
| bing.com / baidu.com | ✅ | ✅ | ✅ | 无 | 对照 |

## 2. 封锁严格度阶梯

```
连接层(最严) > 握手层 > 传输层(最松)
google/youtube     → IP 段级: 连接全断
facebook/insta/wiki/gist → SNI 级: 握手即 RST
twitter            → 数据级: 握手放行, HTTP 被掐
github.com         → 窗口级: 三层随机穿越
```

**机制解读**（与公开 GFW 研究一致）：
- 连接层 = IP 黑名单（整段封禁，TCP 都不让建）
- 握手层 = SNI 黑名单（明文 ClientHello 检测 → RST 注入）
- 传输层 = 数据阶段检测（握手放行，后续流量被掐——理论上 TLS 1.3 ECH 可规避此层，但无法规避握手层/连接层）

## 3. DNS 污染池 ASN 画像（gist 专属）

| 污染 IP | 归属 | 国家 | 特征 |
|---|---|---|---|
| 203.98.7.65 | ONENZ-NZ | 新西兰 | 不可达 |
| 8.7.198.45 | LVLT-ORG-8-8 | 美国 | 不可达（Level3） |
| 37.61.54.158 | AZTELEKOM-ISP | 阿塞拜疆 | 不可达 |
| 159.24.3.173 | MCI-DSN | 美国 | 不可达 |
| 78.16.49.15 | IE-ISI | 爱尔兰 | 不可达 |
| 243.185.187.39 | (无信息) | ? | 不可达 |
| 2001::1 | RFC 保留 | - | AAAA 黑洞 |

**画像结论**：
- 污染池 = **全球随机不可达 IP 集合**（无共同 ASN/国家/运营商归属）
- 共同特征：全部 TCP 不可达（连接超时）→ 制造"DNS 解析成功但连不上"的封锁假象
- 轮换机制：短 TTL + 多 IP 随机分配（观测到 5+ 个 IP 轮换）
- 判定法：解析结果 ∈ 此特征（非官方 + 不可达 + 无共同归属）→ 高置信度污染

## 4. 实用价值

1. **指纹判断封锁类型**：一次三段探测即知规则类型，决定对策：
   - 连接层（google 类）→ 换 IP 段/换协议（如 QUIC）均无效，放弃或走代理
   - 握手层（gist 类）→ 换 IP 无效，换 SNI/域名有效
   - 传输层（twitter 类）→ 换 IP 可能有效（若 IP 未封）
   - 窗口层（github 类）→ 换 IP/等窗口有效
2. **污染判定不再依赖 DoH**：解析结果不可达 + 全球随机归属 → 直接判定污染
3. **封锁等级对照表**：评估"封堵漏洞"时按层评估绕行成本
