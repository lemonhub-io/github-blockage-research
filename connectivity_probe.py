#!/usr/bin/env python3
"""
批量 TCP 连通性探测: 分类 可达/超时/拒绝/重置 + 延迟
用法:
  python3 connectivity_probe.py <ip1> <ip2> ... [--ports 443,80,22] [--threads 30] [--timeout 4]
  python3 connectivity_probe.py --file ips.txt --ports 443
输出: 汇总统计 + 明细
"""
import argparse
import socket
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor


def tcp_test(ip, port, timeout):
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ips", nargs="*")
    ap.add_argument("--file", help="IP 列表文件（每行一个）")
    ap.add_argument("--ports", default="443", help="逗号分隔端口")
    ap.add_argument("--threads", type=int, default=30)
    ap.add_argument("--timeout", type=float, default=4.0)
    args = ap.parse_args()

    ips = list(args.ips)
    if args.file:
        ips += [l.strip() for l in open(args.file) if l.strip()]
    if not ips:
        print("错误: 未提供 IP"); sys.exit(1)
    ports = [int(p) for p in args.ports.split(",")]

    tasks = [(ip, p) for ip in ips for p in ports]
    print(f"[*] 测试 {len(ips)} IP × {len(ports)} 端口 = {len(tasks)} 项 (超时 {args.timeout}s, {args.threads} 线程)")
    results = []
    with ThreadPoolExecutor(max_workers=args.threads) as ex:
        for r in ex.map(lambda t: tcp_test(t[0], t[1], args.timeout), tasks):
            results.append(r)

    stat = Counter(r[2].split(":")[0] for r in results)
    print("\n=== 汇总 ===")
    for k, v in stat.most_common():
        print(f"  {k:10s}: {v}")
    print("\n=== 明细 ===")
    for ip, port, status, lat in sorted(results, key=lambda x: (x[2], x[0])):
        lat_s = f"{lat}ms" if lat is not None else "-"
        print(f"  {ip:18s} :{port:<5d} {status:12s} {lat_s}")


if __name__ == "__main__":
    main()
