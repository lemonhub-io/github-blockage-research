#!/usr/bin/env python3
"""GitHub 封锁时序监测: 多节点并行采样, 输出 CSV 供分析
用法: python3 gh_monitor.py [间隔秒] [轮数] [输出文件]
"""
import csv
import json
import subprocess
import sys
import time
from datetime import datetime

INTERVAL = int(sys.argv[1]) if len(sys.argv) > 1 else 30
ROUNDS = int(sys.argv[2]) if len(sys.argv) > 2 else 30
OUT = sys.argv[3] if len(sys.argv) > 3 else "gh_monitor.csv"

# (SNI, IP, 路径, 标签)
TARGETS = [
    ("github.com", "20.205.243.166", "/", "github_ap"),
    ("github.com", "140.82.112.3", "/", "github_us112"),
    ("github.com", "140.82.121.3", "/", "github_us121"),
    ("api.github.com", "20.205.243.168", "/meta", "api_ap"),
    ("raw.githubusercontent.com", "185.199.108.133", "/sullo/nikto/master/README.md", "raw_file"),
    ("gist.github.com", "140.82.121.4", "/", "gist_us"),
]


def probe(ip, sni, path, timeout=8):
    cmd = f"curl -s --resolve {sni}:443:{ip} -m {timeout} -o /dev/null -w '%{{http_code}} %{{size_download}}' https://{sni}{path}"
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout + 4)
        code, size = r.stdout.strip().split()
        return code, int(size)
    except (subprocess.TimeoutExpired, ValueError):
        return "TIMEOUT", 0


def local_dns(domain):
    try:
        r = subprocess.run(["dig", "+short", domain], capture_output=True, text=True, timeout=5)
        return r.stdout.split()[0] if r.stdout.strip() else "?"
    except Exception:
        return "?"


def main():
    print(f"[*] 监测开始: 间隔{INTERVAL}s x {ROUNDS}轮 x {len(TARGETS)}节点 -> {OUT}")
    with open(OUT, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ts"] + [t[3] + "_code" for t in TARGETS] +
                   [t[3] + "_size" for t in TARGETS] + ["dns_gist", "dns_github"])
        for i in range(ROUNDS):
            ts = datetime.now().strftime("%H:%M:%S")
            row = [ts]
            for sni, ip, path, label in TARGETS:
                code, size = probe(ip, sni, path)
                row += [code, size]
            row += [local_dns("gist.github.com"), local_dns("github.com")]
            w.writerow(row)
            f.flush()
            status = " ".join(f"{t[3]}:{row[1+2*j]}" for j, t in enumerate(TARGETS))
            print(f"[{ts}] 轮{i+1}/{ROUNDS} {status} dns_gist={row[-2]}")
            if i < ROUNDS - 1:
                time.sleep(INTERVAL)
    print(f"[*] 完成 -> {OUT}")


if __name__ == "__main__":
    main()
