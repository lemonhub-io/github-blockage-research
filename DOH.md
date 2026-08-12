# DoH（DNS over HTTPS）服务评测与推荐

实测日期：2026-08-12 | 测试环境：家庭网络沙盒

## 实测结果表

| DoH 服务 | 可用性 | 延迟 | github.com 解析 | gist 解析 | 评级 |
|---|---|---|---|---|---|
| **dns.lemdns.com** | ✅ 可用 | ~919ms | `140.82.121.4`（美西真值） | `140.82.121.4`（**真值**） | ⭐ 首选 |
| dns.alidns.com（阿里） | ✅ 可用 | ~455ms | `20.205.243.166`（官方亚太） | **`159.24.3.173`（污染!）** + AAAA `2001::1` | ⚠️ 受限 |
| doh.pub（腾讯） | ✅ 可用 | ~502ms | `20.205.243.166`（官方亚太） | `20.205.243.166`（官方） | ⚠️ 受限 |
| cloudflare-dns.com | ❌ 被墙/拦截 | — | 无响应 | 无响应 | ✗ |
| 1.1.1.1 | ❌ 被墙/拦截 | — | 无响应 | 无响应 | ✗ |
| dns.google | ❌ 被墙 | — | 无响应 | 无响应 | ✗ |
| doh.360.cn | ❌ 不可用 | — | 非标准响应 | — | ✗ |
| dns.quad9.net | ❌ 被墙/拦截 | — | 无响应 | — | ✗ |
| dns.adguard-dns.com | ❌ 被墙/拦截 | — | 无响应 | — | ✗ |

## 核心结论

1. **海外 DoH 是 DNS 污染环境下的唯一真值来源**：dns.lemdns.com 对 gist 返回官方 IP（140.82.121.4），本地 DNS 与国内 DoH 均返回污染 IP
2. **国内 DoH 同样不可信**：阿里 DoH 对 gist 返回污染池 IP（159.24.3.173）+ AAAA 黑洞（2001::1）——污染在链路/DNS 服务器层面生效，不限于 UDP 53
3. **主流通用 DoH（cloudflare/google）被墙**：当前环境不可达，只有小众海外 DoH 可用
4. 国内 DoH（阿里/腾讯）对**普通域名**解析正常（github.com 返回官方亚太节点），仅对**封锁域名**返回污染结果

## 推荐用法

```bash
# 首选: 真值查询（封锁域名）
curl -s -H "accept: application/dns-json" \
  "https://dns.lemdns.com/dns-query?name=gist.github.com&type=A"

# 备选: 国内 DoH（普通域名/低延迟）
curl -s -H "accept: application/dns-json" \
  "https://doh.pub/dns-query?name=github.com&type=A"
curl -s -H "accept: application/dns-json" \
  "https://dns.alidns.com/resolve?name=api.github.com&type=A"

# 系统级配置（可选，改 /etc/resolv.conf 需管理员权限）
# 或使用 curl --doh-url 参数（curl 8.x+）
curl --doh-url https://dns.lemdns.com/dns-query https://example.com
```

## 污染检测快速法

```bash
# 对比本地解析 vs 海外 DoH: 不一致且本地为不可达/非官方 IP = 污染
dig +short gist.github.com
# → 78.16.49.15 (不可达, 污染)
curl -s -H "accept: application/dns-json" \
  "https://dns.lemdns.com/dns-query?name=gist.github.com&type=A"
# → 140.82.121.4 (官方, 真值)
```

## 已知污染 IP 池（gist 域名，实测收集）

```
78.16.49.15 / 159.24.3.173 / 37.61.54.158 / 243.185.187.39 / 8.7.198.45 / 203.98.7.65
（AAAA 黑洞: 2001::1）
```
