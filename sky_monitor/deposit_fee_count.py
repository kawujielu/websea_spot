#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统计 Binance 最近 N 个月提币手续费消耗（按月汇总）。

接口: GET /sapi/v1/capital/withdraw/history
文档: https://developers.binance.com/docs/zh-CN/wallet/capital/withdraw-history

运行:
  python bn_withdraw_fee_stats.py

依赖: pip install requests
"""
from __future__ import annotations

import hashlib
import hmac
import json
import sys
import time
from collections import defaultdict
from datetime import datetime
from operator import itemgetter
from typing import Any, Dict, List, Optional, Tuple, Union

import requests

# ======================== 写死配置 ========================
BINANCE_HOST = "https://api.binance.com"
REQUEST_TIMEOUT = 30

BINANCE_ACCOUNT = {
    "apiKey": "lWbYa9CHzHSyulhmaPcXLyUT6coxSQAULHgAYU9NjA5UM3qd2SMZeR9cCBd4uiIE",
    "secret": "U40aH29UAiotheaikRk2eUvZtQOt8psNSyNGAYRLocLfeg6HKeIhHDqGkWY8rPqU",
    "comment": "binance现货",
}

# 统计最近几个自然月（含当月），按当前本地时间回推
MONTHS = 3

# 可选：只查指定币种，如 "USDT"；留空则查全部
COIN = ""

# True: 只统计 status=6（提现完成）的记录
ONLY_SUCCESS = True

PAGE_LIMIT = 1000
PAGE_SLEEP = 0.5
# ==========================================================

_MAX_RANGE_DAYS = 90

WITHDRAW_STATUS = {
    0: "已发送确认Email",
    2: "等待确认",
    3: "被拒绝",
    4: "处理中",
    6: "提现完成",
}


def _to_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _dt_to_ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def _format_ms(ts_ms: Union[int, float, str, None]) -> str:
    if ts_ms is None or str(ts_ms).strip() == "":
        return "-"
    try:
        return datetime.fromtimestamp(float(ts_ms) / 1000).strftime("%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError, OSError):
        return str(ts_ms)


def _format_time_value(value: Any) -> str:
    if value is None or str(value).strip() == "":
        return "-"
    text = str(value).strip()
    if text.isdigit():
        return _format_ms(int(text))
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    return text


def _recent_months_range(months: int) -> Tuple[datetime, datetime, List[str]]:
    """返回 [起始日 00:00:00, 当前时刻] 以及月份标签列表 YYYY-MM（旧→新）。"""
    if months < 1:
        raise ValueError("MONTHS 必须 >= 1")
    now = datetime.now()
    y, m = now.year, now.month
    labels: List[str] = []
    for i in range(months - 1, -1, -1):
        mm = m - i
        yy = y
        while mm <= 0:
            mm += 12
            yy -= 1
        labels.append(f"{yy:04d}-{mm:02d}")
    start_y, start_m = map(int, labels[0].split("-"))
    start = datetime(start_y, start_m, 1, 0, 0, 0)
    return start, now, labels


def _binance_order_params(data: Dict[str, Any]) -> List[Tuple[str, Any]]:
    has_signature = False
    params: List[Tuple[str, Any]] = []
    for key, value in data.items():
        if key == "signature":
            has_signature = True
        else:
            params.append((key, value))
    params.sort(key=itemgetter(0))
    if has_signature:
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
    ordered = [(k, v) for k, v in _binance_order_params(data) if v is not None and v != ""]
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
    except json.JSONDecodeError:
        body = {"errmsg": resp.text, "raw_status": resp.status_code}
    return resp.status_code, body


def _split_time_ranges_ms(start_ms: int, end_ms: int) -> List[Tuple[int, int]]:
    if start_ms >= end_ms:
        raise ValueError("开始时间必须早于结束时间")
    ranges: List[Tuple[int, int]] = []
    chunk_ms = (_MAX_RANGE_DAYS - 1) * 86400 * 1000
    cur = start_ms
    while cur < end_ms:
        chunk_end = min(cur + chunk_ms, end_ms)
        ranges.append((cur, chunk_end))
        if chunk_end >= end_ms:
            break
        cur = chunk_end
    return ranges


def fetch_withdraw_history(
    api_key: str,
    secret: str,
    start_ms: int,
    end_ms: int,
    coin: str = "",
) -> Tuple[Optional[str], List[Dict[str, Any]]]:
    all_rows: List[Dict[str, Any]] = []
    seen_ids: set = set()
    path = "/sapi/v1/capital/withdraw/history"

    for chunk_start, chunk_end in _split_time_ranges_ms(start_ms, end_ms):
        offset = 0
        while True:
            params: Dict[str, Any] = {
                "startTime": chunk_start,
                "endTime": chunk_end,
                "limit": PAGE_LIMIT,
                "offset": offset,
            }
            if coin:
                params["coin"] = coin.upper()

            status, body = _binance_signed_get(path, api_key, secret, params)
            if status != 200:
                errmsg = body.get("msg") if isinstance(body, dict) else f"HTTP {status}"
                return str(errmsg or f"HTTP {status}"), all_rows
            if not isinstance(body, list):
                return f"unexpected response: {body!r}", all_rows
            if not body:
                break

            for row in body:
                if not isinstance(row, dict):
                    continue
                row_id = str(row.get("id", ""))
                if row_id and row_id in seen_ids:
                    continue
                if row_id:
                    seen_ids.add(row_id)
                all_rows.append(row)

            if len(body) < PAGE_LIMIT:
                break
            offset += len(body)
            time.sleep(PAGE_SLEEP)

    return None, all_rows


def _withdraw_time_ms(row: Dict[str, Any]) -> int:
    for key in ("completeTime", "applyTime"):
        value = row.get(key)
        if value is None or str(value).strip() == "":
            continue
        text = str(value).strip()
        if text.isdigit():
            return int(float(text))
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
            try:
                return _dt_to_ms(datetime.strptime(text, fmt))
            except ValueError:
                continue
    return 0


def _month_key(ts_ms: int) -> str:
    if not ts_ms:
        return "unknown"
    return datetime.fromtimestamp(ts_ms / 1000).strftime("%Y-%m")


def filter_withdraws(
    rows: List[Dict[str, Any]],
    start_ms: int,
    end_ms: int,
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in rows:
        ts = _withdraw_time_ms(row)
        if ts and not (start_ms <= ts <= end_ms):
            continue
        if ONLY_SUCCESS and int(row.get("status", -1)) != 6:
            continue
        out.append(row)
    out.sort(key=_withdraw_time_ms)
    return out


def summarize_fees_by_month(
    rows: List[Dict[str, Any]],
    month_labels: List[str],
) -> Dict[str, Dict[str, Any]]:
    """
    返回:
      month -> {
        count, fee_by_coin: {coin: fee}, total_rows
      }
    """
    result: Dict[str, Dict[str, Any]] = {
        m: {"count": 0, "fee_by_coin": defaultdict(float)} for m in month_labels
    }
    for row in rows:
        ts = _withdraw_time_ms(row)
        mk = _month_key(ts)
        if mk not in result:
            # 边界外月份忽略（或并入）
            continue
        coin = str(row.get("coin", "UNKNOWN")).upper()
        fee = _to_float(row.get("transactionFee"))
        result[mk]["count"] += 1
        result[mk]["fee_by_coin"][coin] += fee
    return result


def print_detail(rows: List[Dict[str, Any]]) -> None:
    print(
        f"{'时间':<20} {'币种':<8} {'数量':>14} {'手续费':>12} {'网络':<10} {'状态':<10}"
    )
    print("-" * 88)
    if not rows:
        print("(无提现记录)")
        return
    for row in rows:
        ts = _format_time_value(row.get("completeTime") or row.get("applyTime"))
        coin = str(row.get("coin", ""))
        amount = _to_float(row.get("amount"))
        fee = _to_float(row.get("transactionFee"))
        network = str(row.get("network", ""))
        status = WITHDRAW_STATUS.get(int(row.get("status", -1)), str(row.get("status", "")))
        print(
            f"{ts:<20} {coin:<8} {amount:>14.8f} {fee:>12.8f} {network:<10} {status:<10}"
        )


def print_monthly_fee_report(
    month_labels: List[str],
    summary: Dict[str, Dict[str, Any]],
) -> None:
    print("\n【按月手续费汇总】")
    print("-" * 72)
    all_coins = set()
    for m in month_labels:
        all_coins.update(summary[m]["fee_by_coin"].keys())
    coins = sorted(all_coins)

    if not coins:
        print("(无手续费数据)")
        return

    # 每月一块：笔数 + 各币种手续费
    for m in month_labels:
        info = summary[m]
        fees = info["fee_by_coin"]
        print(f"\n{m}  提币笔数={info['count']}")
        if info["count"] == 0:
            print("  (无记录)")
            continue
        print(f"  {'币种':<8} {'手续费合计':>18}")
        for coin in coins:
            fee = float(fees.get(coin, 0.0))
            if fee == 0 and coin not in fees:
                continue
            print(f"  {coin:<8} {fee:>18.8f}")
        # 同币种手续费已分别列出；不同币种不可直接相加为统一金额
        nonzero = [(c, float(fees[c])) for c in fees if float(fees[c]) != 0]
        if len(nonzero) == 1:
            c, f = nonzero[0]
            print(f"  → 本月手续费合计: {f:.8f} {c}")
        elif nonzero:
            parts = ", ".join(f"{f:.8f} {c}" for c, f in sorted(nonzero))
            print(f"  → 本月手续费(分币种): {parts}")

    print("\n【近{}个月手续费总览】".format(len(month_labels)))
    print(f"{'月份':<10} {'笔数':>6}  手续费明细")
    print("-" * 72)
    grand: Dict[str, float] = defaultdict(float)
    for m in month_labels:
        info = summary[m]
        fees = info["fee_by_coin"]
        detail = ", ".join(
            f"{float(fees[c]):.8f} {c}" for c in sorted(fees) if float(fees[c]) != 0
        ) or "-"
        print(f"{m:<10} {info['count']:>6}  {detail}")
        for c, f in fees.items():
            grand[c] += float(f)
    print("-" * 72)
    if grand:
        g = ", ".join(f"{grand[c]:.8f} {c}" for c in sorted(grand) if grand[c] != 0)
        print(f"{'合计':<10} {'':>6}  {g}")
    else:
        print("合计: 0")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    try:
        dt_start, dt_end, month_labels = _recent_months_range(MONTHS)
    except ValueError as exc:
        print(f"配置错误: {exc}")
        return 1

    start_ms = _dt_to_ms(dt_start)
    end_ms = _dt_to_ms(dt_end)
    coin = (COIN or "").strip().upper()
    api_key = BINANCE_ACCOUNT["apiKey"]
    secret = BINANCE_ACCOUNT["secret"]
    comment = BINANCE_ACCOUNT.get("comment", "")

    print("=" * 88)
    print(f"Binance 提币手续费统计  ({comment})")
    print(f"apiKey: {api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else f"apiKey: {api_key}")
    print(f"统计月份: {', '.join(month_labels)}  (最近 {MONTHS} 个自然月，含当月)")
    print(f"时间范围: [{dt_start.strftime('%Y-%m-%d %H:%M:%S')}, {dt_end.strftime('%Y-%m-%d %H:%M:%S')}]")
    print(f"币种过滤: {coin or '全部'}")
    print(f"仅成功(status=6): {'是' if ONLY_SUCCESS else '否'}")
    print("-" * 88)

    print("正在拉取 Binance 提现记录 ...")
    err, raw = fetch_withdraw_history(api_key, secret, start_ms, end_ms, coin)
    if err:
        print(f"提现查询失败: {err}")
        if not raw:
            return 1
        print(f"已获取 {len(raw)} 笔（部分数据）")

    rows = filter_withdraws(raw, start_ms, end_ms)
    print(f"有效提现记录: {len(rows)} 笔\n")
    print("【提现明细】")
    print_detail(rows)

    summary = summarize_fees_by_month(rows, month_labels)
    print_monthly_fee_report(month_labels, summary)

    print("\n说明:")
    print("  - 手续费取字段 transactionFee；时间优先 completeTime，否则 applyTime")
    print("  - 不同币种手续费分别统计，不可直接相加为统一计价金额")
    print("  - 单次 API 跨度不超过 90 天，脚本自动分片分页")
    print("=" * 88)
    return 0 if not err else 1


if __name__ == "__main__":
    sys.exit(main())

