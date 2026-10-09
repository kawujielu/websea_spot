#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统计 Gate + Binance 现货账户在指定时间范围内的成交金额净额（USDT）。

口径（与 mongoorders_notional_sum.py 一致）:
- 成交额 USDT = |qty| × price（或 API 的 quote/deal 字段）
- buy = 正，sell = 负，最后加总净额
- 仅统计计价币为 USDT 的交易对

账户密钥与 select_spot_wallet.py 相同。
时间范围与 select_mongoorder_table.py 默认一致。

运行:
  python bn_gate_spot_notional_sum.py
依赖: pip install requests
"""
from __future__ import annotations

import hashlib
import hmac
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from operator import itemgetter
from typing import Any, Dict, List, Optional, Tuple, Union

import requests

# ======================== 配置 ========================
# 与 select_mongoorder_table.py 相同时间范围（北京时间）
TS_START = "2026-05-07 16:11:00"
TS_END = "2026-09-22 21:45:58"

REQUEST_TIMEOUT = 30
PAGE_SLEEP = 0.2

GATE_HOST = "https://api.gateio.ws"
GATE_API_PREFIX = "/api/v4"
GATE_ACCOUNT = {
    "apiKey": "dd0eeebf5f147b1c8c1cfb5c1db2f38f",
    "secret": "a05598264dd97f2b3aa614efea65b69b02fd972c3f285253da80c43a95b6343e",
    "comment": "gate对冲",
}
GATE_PAGE_LIMIT = 1000
GATE_MAX_RANGE_DAYS = 30

BINANCE_HOST = "https://api.binance.com"
BINANCE_ACCOUNT = {
    "apiKey": "lWbYa9CHzHSyulhmaPcXLyUT6coxSQAULHgAYU9NjA5UM3qd2SMZeR9cCBd4uiIE",
    "secret": "U40aH29UAiotheaikRk2eUvZtQOt8psNSyNGAYRLocLfeg6HKeIhHDqGkWY8rPqU",
    "comment": "binance现货",
}
BINANCE_TRADE_LIMIT = 1000
# Binance myTrades 单次 start/end 最长约 24h
BINANCE_CHUNK_MS = 24 * 3600 * 1000 - 1

CST = timezone(timedelta(hours=8))
# ======================================================


def _to_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _parse_bjt(text: str) -> datetime:
    return datetime.strptime(text.strip(), "%Y-%m-%d %H:%M:%S").replace(tzinfo=CST)


def _fmt_ts(ts: float) -> str:
    try:
        return datetime.fromtimestamp(ts, CST).strftime("%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError, OSError):
        return str(ts)


# ---------- Gate ----------
def _gate_gen_sign(
    secret: str,
    method: str,
    url_path: str,
    timestamp: str,
    query_string: str = "",
    payload_string: str = "",
) -> str:
    m = hashlib.sha512()
    m.update((payload_string or "").encode("utf-8"))
    hashed_payload = m.hexdigest()
    sign_payload = "%s\n%s\n%s\n%s\n%s" % (
        method,
        url_path,
        query_string or "",
        hashed_payload,
        timestamp,
    )
    return hmac.new(secret.encode("utf-8"), sign_payload.encode("utf-8"), hashlib.sha512).hexdigest()


def _gate_signed_get(
    path: str,
    api_key: str,
    secret: str,
    params: Optional[Dict[str, Any]] = None,
) -> Tuple[int, Union[List[Any], Dict[str, Any]]]:
    full_path = f"{GATE_API_PREFIX}{path}"
    parts = []
    for key, value in (params or {}).items():
        if value is None or value == "":
            continue
        parts.append(f"{key}={value}")
    query_string = "&".join(parts)
    url = f"{GATE_HOST.rstrip('/')}{full_path}"
    if query_string:
        url = f"{url}?{query_string}"
    timestamp = str(time.time())
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "KEY": api_key,
        "Timestamp": timestamp,
        "SIGN": _gate_gen_sign(secret, "GET", full_path, timestamp, query_string=query_string),
    }
    resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
    try:
        body = resp.json()
    except Exception:
        body = {"errmsg": resp.text, "raw_status": resp.status_code}
    return resp.status_code, body


def _gate_trade_ts(trade: Dict[str, Any]) -> float:
    ms = trade.get("create_time_ms")
    if ms is not None and str(ms).strip() != "":
        return float(ms) / 1000.0
    return _to_float(trade.get("create_time"))


def _gate_quote_usdt(trade: Dict[str, Any]) -> float:
    """计价金额：优先 deal，否则 price×amount。"""
    deal = trade.get("deal")
    if deal is not None and str(deal).strip() != "":
        return abs(_to_float(deal))
    return abs(_to_float(trade.get("price")) * _to_float(trade.get("amount")))


def fetch_gate_trades(start_ts: int, end_ts: int) -> Tuple[Optional[str], List[Dict[str, Any]]]:
    """拉取 Gate 全交易对成交，按 30 天切片分页。"""
    all_trades: List[Dict[str, Any]] = []
    seen: set[str] = set()
    chunk_sec = (GATE_MAX_RANGE_DAYS - 1) * 86400
    cur = start_ts
    while cur < end_ts:
        chunk_to = min(cur + chunk_sec, end_ts)
        page = 1
        while True:
            status, body = _gate_signed_get(
                "/spot/my_trades",
                GATE_ACCOUNT["apiKey"],
                GATE_ACCOUNT["secret"],
                {"from": cur, "to": chunk_to, "limit": GATE_PAGE_LIMIT, "page": page},
            )
            if status != 200:
                err = body.get("message") or body.get("label") or body.get("errmsg") or f"HTTP {status}"
                return str(err), all_trades
            if not isinstance(body, list) or not body:
                break
            for row in body:
                if not isinstance(row, dict):
                    continue
                tid = str(row.get("id", ""))
                if tid and tid in seen:
                    continue
                if tid:
                    seen.add(tid)
                all_trades.append(row)
            if len(body) < GATE_PAGE_LIMIT:
                break
            page += 1
            time.sleep(PAGE_SLEEP)
        cur = chunk_to
        if cur >= end_ts:
            break
        time.sleep(PAGE_SLEEP)
    # 精确过滤边界
    filtered = [t for t in all_trades if start_ts <= _gate_trade_ts(t) <= end_ts]
    return None, filtered


# ---------- Binance ----------
def _binance_order_params(data: Dict[str, Any]) -> List[Tuple[str, Any]]:
    params: List[Tuple[str, Any]] = []
    has_sig = False
    for key, value in data.items():
        if key == "signature":
            has_sig = True
        else:
            params.append((key, value))
    params.sort(key=itemgetter(0))
    if has_sig:
        params.append(("signature", data["signature"]))
    return params


def _binance_gen_sign(secret: str, data: Dict[str, Any]) -> str:
    ordered = _binance_order_params(data)
    query_string = "&".join(f"{k}={v}" for k, v in ordered)
    return hmac.new(secret.encode("utf-8"), query_string.encode("utf-8"), hashlib.sha256).hexdigest()


def _binance_signed_get(
    path: str,
    api_key: str,
    secret: str,
    extra_params: Optional[Dict[str, Any]] = None,
) -> Tuple[int, Union[List[Any], Dict[str, Any]]]:
    data = dict(extra_params or {})
    data["timestamp"] = int(time.time() * 1000)
    data["signature"] = _binance_gen_sign(secret, data)
    ordered = [(k, v) for k, v in _binance_order_params(data) if v is not None]
    query_string = "&".join(f"{k}={v}" for k, v in ordered)
    url = f"{BINANCE_HOST.rstrip('/')}{path}?{query_string}"
    headers = {
        "Accept": "application/json",
        "User-Agent": "binance/python",
        "X-MBX-APIKEY": api_key,
    }
    resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
    try:
        body = resp.json()
    except Exception:
        body = {"errmsg": resp.text, "raw_status": resp.status_code}
    return resp.status_code, body


def fetch_binance_usdt_symbols() -> Tuple[Optional[str], List[str]]:
    url = f"{BINANCE_HOST.rstrip('/')}/api/v3/exchangeInfo"
    resp = requests.get(url, timeout=REQUEST_TIMEOUT)
    try:
        body = resp.json()
    except Exception:
        return f"exchangeInfo 非 JSON: {resp.text[:200]}", []
    if resp.status_code != 200:
        return f"exchangeInfo HTTP {resp.status_code}", []
    symbols = []
    for s in body.get("symbols") or []:
        if (
            str(s.get("status")) == "TRADING"
            and str(s.get("quoteAsset", "")).upper() == "USDT"
            and str(s.get("isSpotTradingAllowed", True))
        ):
            symbols.append(str(s["symbol"]))
    return None, symbols


def _binance_symbol_has_activity(symbol: str, start_ms: int, end_ms: int) -> bool:
    """抽样首/中/末三个 24h 窗口，任一侧有成交则认为该币对需全量拉取。"""
    if end_ms <= start_ms:
        return False
    mid = start_ms + (end_ms - start_ms) // 2
    probes = [
        (start_ms, min(start_ms + BINANCE_CHUNK_MS, end_ms)),
        (mid, min(mid + BINANCE_CHUNK_MS, end_ms)),
        (max(end_ms - BINANCE_CHUNK_MS, start_ms), end_ms),
    ]
    for lo, hi in probes:
        status, body = _binance_signed_get(
            "/api/v3/myTrades",
            BINANCE_ACCOUNT["apiKey"],
            BINANCE_ACCOUNT["secret"],
            {"symbol": symbol, "startTime": lo, "endTime": hi, "limit": 1},
        )
        time.sleep(PAGE_SLEEP)
        if status == 200 and isinstance(body, list) and body:
            return True
    return False


def fetch_binance_trades_for_symbol(
    symbol: str, start_ms: int, end_ms: int
) -> Tuple[Optional[str], List[Dict[str, Any]]]:
    trades: List[Dict[str, Any]] = []
    cur = start_ms
    while cur <= end_ms:
        chunk_end = min(cur + BINANCE_CHUNK_MS, end_ms)
        # 第一页用时间窗；满页后用 fromId 继续，再按时间过滤
        params: Dict[str, Any] = {
            "symbol": symbol,
            "startTime": cur,
            "endTime": chunk_end,
            "limit": BINANCE_TRADE_LIMIT,
        }
        while True:
            status, body = _binance_signed_get(
                "/api/v3/myTrades",
                BINANCE_ACCOUNT["apiKey"],
                BINANCE_ACCOUNT["secret"],
                params,
            )
            time.sleep(PAGE_SLEEP)
            if status != 200:
                err = body.get("msg") if isinstance(body, dict) else str(body)
                return f"{symbol}: {err}", trades
            if not isinstance(body, list) or not body:
                break
            stop_chunk = False
            for row in body:
                if not isinstance(row, dict):
                    continue
                t = int(row.get("time") or 0)
                if t > chunk_end:
                    stop_chunk = True
                    break
                if start_ms <= t <= end_ms:
                    trades.append(row)
            if stop_chunk or len(body) < BINANCE_TRADE_LIMIT:
                break
            # 后续页只用 fromId（会忽略时间参数）
            params = {
                "symbol": symbol,
                "fromId": int(body[-1]["id"]) + 1,
                "limit": BINANCE_TRADE_LIMIT,
            }
        cur = chunk_end + 1
    return None, trades


def fetch_binance_trades(start_ms: int, end_ms: int) -> Tuple[Optional[str], List[Dict[str, Any]]]:
    err, symbols = fetch_binance_usdt_symbols()
    if err:
        return err, []
    print(f"  Binance USDT 交易对数量={len(symbols)}，抽样探测有成交的币对…")
    active: List[str] = []
    for i, sym in enumerate(symbols, 1):
        if _binance_symbol_has_activity(sym, start_ms, end_ms):
            active.append(sym)
            print(f"    命中 {sym}（已发现 {len(active)}）")
        if i % 50 == 0:
            print(f"    探测进度 {i}/{len(symbols)}，命中 {len(active)}")
    print(f"  需全量拉取的币对: {len(active)} -> {active}")

    all_trades: List[Dict[str, Any]] = []
    for sym in active:
        e, rows = fetch_binance_trades_for_symbol(sym, start_ms, end_ms)
        if e:
            print(f"  警告 {e}")
            continue
        print(f"  {sym}: {len(rows)} 笔")
        all_trades.extend(rows)
    return None, all_trades


def _is_usdt_pair(pair: str) -> bool:
    p = str(pair or "").upper().replace("-", "_")
    return p.endswith("_USDT") or (("_" not in p) and p.endswith("USDT"))


# ---------- 汇总 ----------
def summarize_signed(
    rows: List[Dict[str, Any]],
    *,
    quote_fn,
    pair_key: str,
    is_buy_fn,
) -> Dict[str, Any]:
    buy_usdt = sell_usdt = net = 0.0
    n_buy = n_sell = 0
    by_pair: Dict[str, float] = defaultdict(float)

    for r in rows:
        pair = str(r.get(pair_key) or "")
        if not _is_usdt_pair(pair):
            continue
        quote = quote_fn(r)
        if quote <= 0:
            continue
        if is_buy_fn(r):
            signed = quote
            buy_usdt += quote
            n_buy += 1
        else:
            signed = -quote
            sell_usdt += quote
            n_sell += 1
        net += signed
        by_pair[pair] += signed

    return {
        "n_buy": n_buy,
        "n_sell": n_sell,
        "buy_usdt": buy_usdt,
        "sell_usdt": sell_usdt,
        "net": net,
        "by_pair": sorted(by_pair.items(), key=lambda x: abs(x[1]), reverse=True),
    }


def _print_exchange(name: str, summary: Dict[str, Any]) -> None:
    print(f"\n===== {name} =====")
    print(f"  buy笔数={summary['n_buy']} sell笔数={summary['n_sell']}")
    print(f"  buy 成交额:  +{summary['buy_usdt']:,.4f} USDT")
    print(f"  sell 成交额: -{summary['sell_usdt']:,.4f} USDT")
    print(f"  净额加总:     {summary['net']:,.4f} USDT")
    if summary["by_pair"]:
        print(f"  {'交易对':<16} {'净额USDT':>16}")
        for pair, net in summary["by_pair"][:30]:
            print(f"  {pair:<16} {net:>16.4f}")
        if len(summary["by_pair"]) > 30:
            print(f"  … 共 {len(summary['by_pair'])} 个交易对")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    start_dt = _parse_bjt(TS_START)
    end_dt = _parse_bjt(TS_END)
    start_ts = int(start_dt.timestamp())
    end_ts = int(end_dt.timestamp())
    start_ms = start_ts * 1000
    end_ms = end_ts * 1000

    print(f"时间范围(北京时间): [{TS_START}, {TS_END}]")
    print("口径: 成交额USDT=qty×price；buy=+，sell=-；仅 USDT 计价对")
    print()

    # Gate
    print("正在拉取 Gate 成交…")
    g_err, g_trades = fetch_gate_trades(start_ts, end_ts)
    if g_err:
        print(f"Gate 失败: {g_err}")
        g_summary = summarize_signed(
            [],
            quote_fn=_gate_quote_usdt,
            pair_key="currency_pair",
            is_buy_fn=lambda r: str(r.get("side", "")).lower() == "buy",
        )
    else:
        print(f"Gate 成交笔数={len(g_trades)}")
        g_trades = [t for t in g_trades if _is_usdt_pair(str(t.get("currency_pair", "")))]
        g_summary = summarize_signed(
            g_trades,
            quote_fn=_gate_quote_usdt,
            pair_key="currency_pair",
            is_buy_fn=lambda r: str(r.get("side", "")).lower() == "buy",
        )
    _print_exchange("Gate", g_summary)

    # Binance
    print("\n正在拉取 Binance 成交…")
    b_err, b_trades = fetch_binance_trades(start_ms, end_ms)
    if b_err:
        print(f"Binance 失败: {b_err}")
        b_summary = summarize_signed(
            [],
            quote_fn=lambda r: abs(
                _to_float(r.get("quoteQty"))
                if _to_float(r.get("quoteQty")) > 0
                else _to_float(r.get("qty")) * _to_float(r.get("price"))
            ),
            pair_key="symbol",
            is_buy_fn=lambda r: bool(r.get("isBuyer")),
        )
    else:
        print(f"Binance 成交笔数={len(b_trades)}")
        b_summary = summarize_signed(
            b_trades,
            quote_fn=lambda r: abs(
                _to_float(r.get("quoteQty"))
                if _to_float(r.get("quoteQty")) > 0
                else _to_float(r.get("qty")) * _to_float(r.get("price"))
            ),
            pair_key="symbol",
            is_buy_fn=lambda r: bool(r.get("isBuyer")),
        )
    _print_exchange("Binance", b_summary)

    combined = g_summary["net"] + b_summary["net"]
    print("\n===== 合计 =====")
    print(f"  Gate 净额:    {g_summary['net']:,.4f} USDT")
    print(f"  Binance 净额: {b_summary['net']:,.4f} USDT")
    print(f"  两边加总:     {combined:,.4f} USDT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

