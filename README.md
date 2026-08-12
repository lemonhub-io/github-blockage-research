# GitHub Blockage Research

GitHub 网络可达性与封锁状况的实证研究：DNS 污染检测、SNI/IP 层封锁测绘、动态封锁时序分析。

> 研究环境：授权沙盒（家庭网络模拟环境），2026-08-12 实测。
> 声明：所有测试为被动连通性测量（TCP/TLS/HTTPS 传输），无任何攻击性 payload。

## 核心发现

1. **三层封锁结构**
   - 持久封锁层：`gist.github.com`（DNS 污染池轮换 + 传输阻断）、`140.82.121.x` IP 段
   - 间歇封锁层：`github.com` 主站（窗口 3-5 分钟封禁 / 4-12 分钟解封）、`raw.githubusercontent.com`
   - 稳定可用层：`api.github.com` 亚太节点（`20.205.243.168`，全程 100% 可用率）

2. **封锁粒度**：IP 级（同段 `.166` 封时 `.168` 通）+ 域名/SNI 级（gist 全 IP 封锁）

3. **触发机制**：对照实验（停止探测 3 分钟状态不变）证明封锁为**外部时间驱动规则**，非探测触发

4. **DNS 污染**：gist 本地解析被投毒至轮换的不可达 IP 池（≥5 个，如 `78.16.49.15` / `159.24.3.173`），其余域名 DNS 正常解析到官方节点

## 项目结构

```
├── GITHUB_BLOCK_REPORT.md      # 完整研究报告（含附录 A/B：DoH 扩展 + 时序规律）
├── github-case-study.md        # 案例笔记（方法论 + 完整数据）
├── connectivity_probe.py       # 批量 TCP 连通性探测（多线程分类+延迟）
├── blockage_monitor.py         # 封锁时序监测（多节点采样 + DNS 轮换记录）
├── gh_connectivity.py          # GitHub 专项连通性测试
├── gh_monitor.py               # GitHub 专项时序监测（简化版）
└── gh_monitor.csv              # 21 轮监测原始数据
```

## 快速开始

```bash
# 1. 批量 TCP 连通性测试
python3 connectivity_probe.py 140.82.112.3 140.82.121.3 --ports 443

# 2. 封锁判定（传输层实测，0 字节 = 封锁）
curl -s --resolve github.com:443:20.205.243.166 -m 10 \
  -o /dev/null -w '%{http_code} %{size_download}' https://github.com/

# 3. DoH 真值（DNS 劫持环境下的可靠解析）
curl -s -H "accept: application/dns-json" \
  "https://dns.lemdns.com/dns-query?name=gist.github.com&type=A"

# 4. 动态封锁时序监测（20s 间隔 × 45 轮）
python3 blockage_monitor.py 20 45 monitor.csv
```

## 方法论要点

- 封锁判定必须做**实际传输**测试（TCP/TLS 握手通过不代表可用，0 字节=传输层封锁）
- "慢"≠封锁：需对照组（国内源同测）区分环境带宽限制
- 单次测量只是快照：动态封锁需 ≥20 分钟时序采样 + 窗口分析
- 对照实验（停止探测）判定触发机制，避免误判

## 许可

MIT License — 见 [LICENSE](LICENSE)
