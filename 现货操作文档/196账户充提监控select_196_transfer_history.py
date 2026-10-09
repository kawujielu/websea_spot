# -*- coding: utf-8 -*-
"""每10分钟检查：196近3天提现是否有等额充值到账（金额误差≤5U）。仅查196账户。"""
import hashlib
import random
import string
import time
from datetime import datetime

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ========== 参数 ==========
USER_ID = 196
RISK_HOST = "https://riskapi.websea.work"
RISK_TOKEN = "c1cf4185b2bed317aeb6e6674491fbef"
TOKEN = "78fc47c5590f77ca42d1e2c3bb432813"
SECRET = "5e5yg7ga285hctuqrtpb"

LOOKBACK_DAYS = 3
CHECK_INTERVAL = 600       # 10min
WD_AGE_SEC = 600           # 提现超过10min才检查
AMT_TOL_U = 5.0            # 金额误差 ≤5U 视为匹配
PAGE_SIZE = 100
TIMEOUT = 30
WD_SKIP_STATUS = {"2", "11", "12"}   # 撤销/失败/驳回不检查
DEP_OK_STATUS = {"9", "1"}           # 充值成功/待确认可匹配
# ==========================

WD_STATUS = {
    "0": "审核中", "1": "已通过", "2": "已撤销", "3": "排队中",
    "5": "打包中", "7": "确认中", "9": "已确认", "11": "失败", "12": "已驳回",
}
DEP_STATUS = {
    "0": "待确认", "1": "待确认", "2": "失败", "9": "已确认",
}


def _headers(data: dict) -> dict:
    nonce = f"{int(time.time() * 1000)}_{''.join(random.sample(string.ascii_letters + string.digits, 5))}"
    tmp = [TOKEN, SECRET, nonce] + [f"{k}={v}" for k, v in data.items()]
    return {
        "Token": TOKEN, "Nonce": nonce,
        "Signature": hashlib.sha1("".join(sorted(tmp)).encode()).hexdigest(),
        "user-agent": "Mozilla/5.0",
    }


def _fmt_ts(v) -> str:
    try:
        x = float(v)
        if x > 1e12:
            x /= 1000
        return datetime.fromtimestamp(x).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(v or "-")


def _to_f(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _ts_sec(v) -> float:
    try:
        x = float(v)
        return x / 1000 if x > 1e12 else x
    except Exception:
        return 0.0


def fetch_pages(path: str, start_s: int, end_s: int) -> list:
    rows, page = [], 1
    while True:
        data = {
            "token": RISK_TOKEN, "user_id": USER_ID,
            "page": page, "page_size": PAGE_SIZE,
            "min_time": start_s, "max_time": end_s,
        }
        r = requests.get(
            f"{RISK_HOST}{path}", params=data, headers=_headers(data),
            timeout=TIMEOUT, verify=False,
        )
        r.raise_for_status()
        j = r.json()
        if j.get("errno", 0) not in (0, None, "0"):
            raise RuntimeError(f"{path} 失败: {j}")
        chunk = (j.get("result") or {}).get("data") or []
        if not chunk:
            break
        rows.extend(chunk)
        if len(chunk) < PAGE_SIZE:
            break
        page += 1
        time.sleep(0.2)
    return rows


def fetch_prices(coins: set) -> dict:
    px = {"USDT": 1.0}
    need = [c for c in coins if c and c.upper() != "USDT"]
    if not need:
        return px
    try:
        r = requests.get("https://api.binance.com/api/v3/ticker/price", timeout=TIMEOUT)
        r.raise_for_status()
        m = {i["symbol"]: float(i["price"]) for i in r.json()}
        for c in need:
            u = c.upper()
            if u + "USDT" in m:
                px[u] = m[u + "USDT"]
    except Exception as e:
        print(f"[WARN] 拉价格失败: {e}")
    return px


def match_u(coin: str, a: float, b: float, prices: dict) -> bool:
    diff = abs(a - b)
    if coin.upper() == "USDT":
        return diff <= AMT_TOL_U
    p = prices.get(coin.upper(), 0.0)
    if p <= 0:
        return diff <= 1e-8
    return diff * p <= AMT_TOL_U


def _row_ts(row: dict) -> float:
    return _ts_sec(row.get("create_time") or row.get("mtime") or row.get("ctime") or row.get("utime"))


def print_deposits(deps: list):
    print(f"\n--- 充值 cashin 共 {len(deps)} 条 ---")
    if not deps:
        print("  (无)")
        return
    rows = sorted(deps, key=_row_ts, reverse=True)
    for d in rows:
        coin = str(d.get("currency_name") or d.get("currency") or "").upper()
        amt = _to_f(d.get("user_amount") or d.get("amount"))
        st = str(d.get("status", ""))
        st_cn = DEP_STATUS.get(st, st)
        print(
            f"  {_fmt_ts(_row_ts(d))}  {coin:<8}  amt={amt}  status={st_cn}({st})  "
            f"addr={str(d.get('address') or '')[:24]}  "
            f"tx={str(d.get('tx_hash') or '')[:20]}  id={d.get('id')}"
        )


def print_withdraws(wds: list):
    print(f"\n--- 提现 takeout 共 {len(wds)} 条 ---")
    if not wds:
        print("  (无)")
        return
    rows = sorted(wds, key=_row_ts, reverse=True)
    for w in rows:
        coin = str(w.get("currency_name") or w.get("currency") or "").upper()
        amt = _to_f(w.get("amount") or w.get("user_amount"))
        st = str(w.get("status", ""))
        st_cn = WD_STATUS.get(st, st)
        print(
            f"  {_fmt_ts(_row_ts(w))}  {coin:<8}  amt={amt}  status={st_cn}({st})  "
            f"addr={str(w.get('address') or '')[:24]}  "
            f"tx={str(w.get('tx_hash') or '')[:20]}  id={w.get('id')}"
        )


def check_once():
    end_s = int(time.time())
    start_s = end_s - LOOKBACK_DAYS * 86400
    now = time.time()
    print(f"\n===== 检查 {datetime.now():%Y-%m-%d %H:%M:%S} 近{LOOKBACK_DAYS}天 =====")
    print(f"时间范围: {_fmt_ts(start_s)} ~ {_fmt_ts(end_s)}")

    wds = fetch_pages("/api/transfer/takeoutlist", start_s, end_s)
    deps = fetch_pages("/api/transfer/cashinlist", start_s, end_s)

    print_deposits(deps)
    print_withdraws(wds)

    # 充值池
    pool = []
    for d in deps:
        if str(d.get("status", "")) not in DEP_OK_STATUS:
            continue
        coin = str(d.get("currency_name") or d.get("currency") or "").upper()
        amt = _to_f(d.get("user_amount") or d.get("amount"))
        pool.append((coin, amt, d))

    coins = {c for c, _, _ in pool}
    pending = []
    for w in wds:
        if str(w.get("status", "")) in WD_SKIP_STATUS:
            continue
        ts = _row_ts(w)
        if not ts or now - ts < WD_AGE_SEC:
            continue
        coin = str(w.get("currency_name") or w.get("currency") or "").upper()
        amt = _to_f(w.get("amount") or w.get("user_amount"))
        coins.add(coin)
        pending.append((w, coin, amt, ts))

    prices = fetch_prices(coins)
    used, unmatched = set(), []
    for w, coin, amt, ts in pending:
        hit = None
        for i, (pc, pa, _) in enumerate(pool):
            if i in used or pc != coin:
                continue
            if match_u(coin, amt, pa, prices):
                hit = i
                break
        if hit is None:
            unmatched.append((w, coin, amt, ts))
        else:
            used.add(hit)

    print(f"\n--- 匹配检查 提现(>10min): {len(pending)}  充值池: {len(pool)}  未匹配: {len(unmatched)} ---")
    if not unmatched:
        print("无超时未匹配提现")
        return

    print("!!! 以下196提现超过10min，未找到等额充值(误差≤5U):")
    for w, coin, amt, ts in unmatched:
        st = WD_STATUS.get(str(w.get("status", "")), str(w.get("status", "")))
        print(
            f"  {_fmt_ts(ts)}  {coin:<8}  amt={amt}  status={st}  "
            f"addr={str(w.get('address') or '')[:20]}  "
            f"tx={str(w.get('tx_hash') or '')[:18]}  id={w.get('id')}"
        )


def main():
    print(f"196充提监控启动  interval={CHECK_INTERVAL}s  tol={AMT_TOL_U}U")
    while True:
        try:
            check_once()
        except Exception as e:
            print(f"[ERROR] {e}")
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
