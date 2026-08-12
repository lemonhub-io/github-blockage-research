#!/usr/bin/env python3
"""GitHub IP 连通性实测：分类 可达/超时/拒绝/重置"""
import socket
import sys
import time
from concurrent.futures import ThreadPoolExecutor

TIMEOUT = 4

def tcp_test(ip, port=443, timeout=TIMEOUT):
    """返回 (ip, port, status, latency_ms)"""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    t0 = time.time()
    try:
        s.connect((ip, port))
        lat = int((time.time() - t0) * 1000)
        return (ip, port, "REACHABLE", lat)
    except socket.timeout:
        return (ip, port, "TIMEOUT", None)
    except ConnectionRefusedError:
        return (ip, port, "REFUSED", None)
    except ConnectionResetError:
        return (ip, port, "RESET", None)
    except OSError as e:
        return (ip, port, f"ERR:{e.errno}", None)
    finally:
        s.close()

def batch(ips, ports=(443,), threads=30, label=""):
    results = []
    tasks = [(ip, p) for ip in ips for p in ports]
    with ThreadPoolExecutor(max_workers=threads) as ex:
        for r in ex.map(lambda t: tcp_test(*t), tasks):
            results.append(r)
    # 汇总
    from collections import Counter
    stat = Counter(r[2].split(":")[0] for r in results)
    print(f"\n=== {label} ({len(tasks)} 测试) ===")
    for k, v in stat.most_common():
        print(f"  {k:10s}: {v}")
    return results

if __name__ == "__main__":
    # 用法: python3 gh_connectivity.py <ip1> <ip2> ... 或 --file <list>
    pass
