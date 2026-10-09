#!/usr/bin/env python3
"""
跨服务器定时上架脚本

部署机器: ip-10-0-209-181
部署路径: /home/ubuntu/code/trade/跨服务器上线脚本(scheduled_online).py
（或与本脚本同目录，见下方运行命令）

========== 操作步骤 ==========

1. 确认前置条件
   - 已在 181 上配置好到 47、223 的 SSH 免密（ubuntu@ip-10-0-209-47、ubuntu@ip-10-0-208-223）
   - trade 目录下 new_online.py 及 StartScripts 脚本可用
   - 47 上 spot_market_maker/restart.sh、223 上 monitor/manage_quant.py 可正常执行

2. 确定上架整点时间
   - 格式: YYYY-MM-DD HH:MM:SS（本地时间）
   - 示例: 2026-07-03 18:00:00

3. 在 181 上启动本脚本（须早于整点至少 5 分钟启动，否则只会立即重启 StartScripts）
   cd /home/ubuntu/code/trade
   python3 跨服务器上线脚本\(scheduled_online\).py "2026-07-03 18:00:00"

4. 脚本自动执行时间线
   T-5 分钟（整点前 5 分钟）— 本机 181 重启 StartScripts，顺序:
     - start_spot_price.sh → 等待 2s
     - start_spot_price.sh → 等待 2s
     - start_volume_ws_source.sh → 等待 40s
     - start_volume.sh → 等待 2s

   T 整点 — 跨服务器上架:
     - 181: python3 new_online.py
     - 47:  bash /home/ubuntu/code/spot_market_maker/restart.sh
     - 223: cd /home/ubuntu/monitor && python3 manage_quant.py restart

5. 异常说明
   - 若启动时已过整点，脚本直接退出，不执行任何操作
   - 若启动时已过 T-5 但未到整点，会立即重启 StartScripts，再等至整点执行上架

6. 配置修改
   - START_SCRIPTS: 调整 181 重启脚本及间隔
   - 第二个 start_spot_price.sh 若应为 start_spot_dex_price.sh，改 START_SCRIPTS 对应项

========== 涉及服务器 ==========
  181 (本机): trade / StartScripts / new_online.py
  47:         spot_market_maker
  223:        monitor (manage_quant.py)
"""
import argparse
import subprocess
import sys
import time
from datetime import datetime, timedelta

TRADE_DIR = "/home/ubuntu/code/trade"
START_DIR = f"{TRADE_DIR}/StartScripts"
# 第二个脚本若应为 start_spot_dex_price.sh，改此处即可
START_SCRIPTS = [
    ("start_spot_price.sh", 3),
    ("start_spot_price.sh", 3),
    ("start_volume_ws_source.sh", 40),
    ("start_volume.sh", 3),
]


def run(cmd, cwd=None):
    print(f">>> {cmd}")
    subprocess.run(cmd, shell=True, check=True, cwd=cwd)


def ssh(host, cmd):
    run(f'ssh ubuntu@{host} "{cmd}"')


def wait_until(target):
    while datetime.now() < target:
        time.sleep(min((target - datetime.now()).total_seconds(), 1))


def restart_start_scripts():
    for script, delay in START_SCRIPTS:
        run(f"bash {script}", cwd=START_DIR)
        if delay:
            time.sleep(delay)


def run_online_flow():
    run("python3 new_online.py", cwd=TRADE_DIR)
    ssh("ip-10-0-209-47", "bash /home/ubuntu/code/spot_market_maker/restart.sh")
    ssh("ip-10-0-208-223", "cd /home/ubuntu/monitor && python3 manage_quant.py restart")


def main():
    parser = argparse.ArgumentParser(description="整点跨服务器上架流程")
    parser.add_argument("time", help="整点时间，格式 2026-07-03 18:00:00")
    args = parser.parse_args()

    scheduled = datetime.strptime(args.time, "%Y-%m-%d %H:%M:%S")
    restart_at = scheduled - timedelta(minutes=5)
    now = datetime.now()

    if now >= scheduled:
        sys.exit(f"已过预定时间 {args.time}")

    if now < restart_at:
        print(f"等待至 {restart_at.strftime('%Y-%m-%d %H:%M:%S')} 重启 StartScripts...")
        wait_until(restart_at)
    else:
        print("已过重启窗口起点，立即重启 StartScripts...")

    restart_start_scripts()

    if datetime.now() < scheduled:
        print(f"等待至整点 {args.time} 执行 new_online.py 及后续流程...")
        wait_until(scheduled)

    run_online_flow()
    print("全部完成")


if __name__ == "__main__":
    main()
