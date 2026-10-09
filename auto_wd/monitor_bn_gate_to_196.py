#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""拉取并打印：196 充值、BN 提币、Gate 提币（最近1小时）。不依赖 libs/load。"""

from __future__ import annotations

import hashlib
import hmac
import time
from datetime import datetime, timedelta, timezone
from operator import itemgetter
from pathlib import Path

import requests

LOOKBACK_SEC = 3600  # 最近1小时
LIMIT = 100
TZ_UTC8 = timezone(timedelta(hours=8))

ABC_USER_ID = 196
ABC_RISK_HOST = "https://riskapi.websea.work"
ABC_RISK_TOKEN = "c1cf4185b2bed317aeb6e6674491fbef"
ABC_TOKEN = "78fc47c5590f77ca42d1e2c3bb432813"
ABC_SECRET = "5e5yg7ga285hctuqrtpb"

BN = {
    "apiKey": "lWbYa9CHzHSyulhmaPcXLyUT6coxSQAULHgAYU9NjA5UM3qd2SMZeR9cCBd4uiIE",
    "secret": "U40aH29UAiotheaikRk2eUvZtQOt8psNSyNGAYRLocLfeg6HKeIhHDqGkWY8rPqU",
}
GATE = {
    "apiKey": "dd0eeebf5f147b1c8c1cfb5c1db2f38f",
    "secret": "a05598264dd97f2b3aa614efea65b69b02fd972c3f285253da80c43a95b6343e",
}
TIMEOUT = 30


def _ts_range():
    end_s = int(time.time())
    start_s = end_s - LOOKBACK_SEC
    return start_s, end_s


def _fmt(ts):
    """本地/UTC+8 时间戳格式化（196 充值用）。"""
    try:
        v = float(ts)
        if v > 1e12:
            v /= 1000
        return datetime.fromtimestamp(v, tz=TZ_UTC8).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(ts or "-")


def _fmt_utc_to_cst(ts):
    """BN 时间为 UTC，转为 UTC+8 显示。"""
    if ts is None or str(ts).strip() == "":
        return "-"
    s = str(ts).strip()
    try:
        v = float(s)
        if v > 1e12:
            v /= 1000
        return datetime.fromtimestamp(v, tz=timezone.utc).astimezone(TZ_UTC8).strftime("%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
        try:
            dt = datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
            return dt.astimezone(TZ_UTC8).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    return s


def _abc_headers(data: dict) -> dict:
    import random
    import string
    nonce = f"{int(time.time() * 1000)}_{''.join(random.sample(string.ascii_letters + string.digits, 5))}"
    tmp = [ABC_TOKEN, ABC_SECRET, nonce] + [f"{k}={v}" for k, v in data.items()]
    return {
        "Token": ABC_TOKEN,
        "Nonce": nonce,
        "Signature": hashlib.sha1("".join(sorted(tmp)).encode()).hexdigest(),
        "user-agent": "Mozilla/5.0",
    }


def abc_deposits(user_id, start_s, end_s, limit=LIMIT):
    data = {
        "token": ABC_RISK_TOKEN,
        "user_id": user_id,
        "page": 1,
        "page_size": limit,
        "min_time": start_s,
        "max_time": end_s,
    }
    r = requests.get(
        f"{ABC_RISK_HOST}/api/transfer/cashinlist",
        params=data, headers=_abc_headers(data), timeout=TIMEOUT,
    )
    r.raise_for_status()
    return ((r.json().get("result") or {}).get("data") or [])[:limit]


def bn_withdraws(start_ms, end_ms, limit=LIMIT):
    data = {
        "startTime": start_ms,
        "endTime": end_ms,
        "limit": limit,
        "timestamp": int(time.time() * 1000),
    }
    qs = "&".join(f"{k}={v}" for k, v in sorted(data.items(), key=itemgetter(0)))
    data["signature"] = hmac.new(BN["secret"].encode(), qs.encode(), hashlib.sha256).hexdigest()
    ordered = sorted(((k, v) for k, v in data.items() if k != "signature"), key=itemgetter(0))
    ordered.append(("signature", data["signature"]))
    qs = "&".join(f"{k}={v}" for k, v in ordered)
    r = requests.get(
        f"https://api.binance.com/sapi/v1/capital/withdraw/history?{qs}",
        headers={"X-MBX-APIKEY": BN["apiKey"]}, timeout=TIMEOUT,
    )
    r.raise_for_status()
    return (r.json() or [])[:limit]


def gate_withdraws(start_s, end_s, limit=LIMIT):
    """GET /wallet/withdrawals — 指定时间窗内最近 limit 条。"""
    host = "https://api.gateio.ws"
    path = "/api/v4/wallet/withdrawals"
    query = f"from={start_s}&to={end_s}&limit={limit}"
    t = str(time.time())
    body_hash = hashlib.sha512(b"").hexdigest()
    sign = hmac.new(
        GATE["secret"].encode(),
        f"GET\n{path}\n{query}\n{body_hash}\n{t}".encode(),
        hashlib.sha512,
    ).hexdigest()
    r = requests.get(
        f"{host}{path}?{query}",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "KEY": GATE["apiKey"],
            "Timestamp": t,
            "SIGN": sign,
        },
        timeout=TIMEOUT,
    )
    if r.status_code != 200:
        print(f"  Gate 提币查询失败 [{r.status_code}] {r.text}")
        return []
    return (r.json() or [])[:limit]


def _amt(v) -> str:
    try:
        return f"{float(v):.10f}".rstrip("0").rstrip(".")
    except (TypeError, ValueError):
        return str(v or "")


def _match_key(time_str: str, coin, amount) -> tuple:
    """相同日期+小时+分钟 + 币种 + 数量。"""
    return (str(time_str)[:16], str(coin or "").upper(), _amt(amount))


def _send_tg(msg: str):
    """与 wd.py 相同：ser=spot_hedge。直接加载 senddd，避开 libs/__init__ 的 load。"""
    try:
        import importlib.util
        p = Path(__file__).resolve().parents[1] / "libs" / "senddd.py"
        spec = importlib.util.spec_from_file_location("_senddd", p)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        m.send_telegram_msg(msg, ser="spot_hedge")
    except Exception as e:
        print(f"  tg发送失败: {e}")


def main():
    start_s, end_s = _ts_range()
    start_txt = datetime.fromtimestamp(start_s, tz=TZ_UTC8).strftime("%Y-%m-%d %H:%M:%S")
    end_txt = datetime.fromtimestamp(end_s, tz=TZ_UTC8).strftime("%Y-%m-%d %H:%M:%S")
    print(f"时间范围(UTC+8): [{start_txt}, {end_txt}]  最近1小时\n")

    print("=" * 80)
    print("【196 充值】")
    deps = abc_deposits(ABC_USER_ID, start_s, end_s)
    for d in deps:
        print(f"  {_fmt(d.get('create_time') or d.get('mtime'))}  "
              f"{d.get('currency_name')}  {d.get('user_amount') or d.get('amount')}")
    print(f"  共 {len(deps)} 笔\n")

    print("=" * 80)
    print("【BN 提币】")
    bn = bn_withdraws(start_s * 1000, end_s * 1000)
    for w in bn:
        print(f"  {_fmt_utc_to_cst(w.get('completeTime') or w.get('applyTime'))}  {w.get('coin')}  {w.get('amount')}")
    print(f"  共 {len(bn)} 笔\n")

    # BN 提币 vs 196 充值：同分钟 + 同币 + 同数量
    dep_keys = []
    for d in deps:
        t = _fmt(d.get("create_time") or d.get("mtime"))
        dep_keys.append(_match_key(t, d.get("currency_name"), d.get("user_amount") or d.get("amount")))

    missing = []
    for w in bn:
        t = _fmt_utc_to_cst(w.get("completeTime") or w.get("applyTime"))
        key = _match_key(t, w.get("coin"), w.get("amount"))
        if key in dep_keys:
            dep_keys.remove(key)
        else:
            missing.append((t, w.get("coin"), w.get("amount")))

    print("=" * 80)
    print("【BN→196 对账】")
    if missing:
        print(f"  充值未到账 {len(missing)} 笔:")
        lines = [f"!!! 充值未到账  {t}  {coin}  {amount}" for t, coin, amount in missing]
        for line in lines:
            print(f"  {line}")
        _send_tg("【BN→196】充值未到账\n" + "\n".join(lines))
    else:
        print("  全部到账")
    print()

    print("=" * 80)
    print("【Gate 提币】")
    gate = gate_withdraws(start_s, end_s)
    for w in gate:
        print(f"  {_fmt(w.get('timestamp'))}  {w.get('currency')}  "
              f"{w.get('amount')}  status={w.get('status')}  tx={w.get('txid')}")
    print(f"  共 {len(gate)} 笔")


if __name__ == "__main__":
    main()
