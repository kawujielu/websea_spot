#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
查询 Binance 现货账户指定时间范围内的充值 / 提现历史（独立脚本，无项目依赖）。

Binance 接口:
  GET /sapi/v1/capital/deposit/hisrec   充值历史
  GET /sapi/v1/capital/withdraw/history 提现历史

文档:
  https://developers.binance.com/docs/zh-CN/wallet/capital/deposite-history
  https://developers.binance.com/docs/zh-CN/wallet/capital/withdraw-history

直接运行（无命令行参数，修改下方配置区即可）:

  python query_binance_deposit_withdraw.py

依赖: pip install requests
兼容: Python 3.9+
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

# 查询时间范围（含边界），格式 YYYY-MM-DD HH:MM:SS
TIME_START = "2026-08-01 00:00:00"
TIME_END = "2026-09-01 23:59:59"

# 可选：只查指定币种，如 "USDT"；留空则查全部
COIN = ""

# 单次 API 请求最多返回条数（Binance 上限 1000）
PAGE_LIMIT = 1000

# 分页 / 分片请求间隔（秒）；提现接口权重较高，建议 >= 0.5
PAGE_SLEEP = 0.5

# True: 只输出 status=1(充值成功) / status=6(提现完成) 的记录
ONLY_SUCCESS = False
# ==========================================================

# Binance startTime/endTime 单次跨度上限（天）
_MAX_RANGE_DAYS = 90

DEPOSIT_STATUS = {
    0: "待确认",
    1: "成功",
    2: "已拒绝",
    6: "已上账待解锁",
    7: "错误充值",
    8: "待用户申请确认",
}

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


def _parse_dt(text: str) -> datetime:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(text.strip(), fmt)
        except ValueError:
            continue
    raise ValueError(f"无法解析时间: {text!r}，请使用 YYYY-MM-DD HH:MM:SS")


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
    """Binance SAPI 签名 GET，返回 (http_status, body)。"""
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
    """将时间范围切分为不超过 _MAX_RANGE_DAYS 的片段（Binance API 限制）。"""
    if start_ms >= end_ms:
        raise ValueError("TIME_START 必须早于 TIME_END")

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


def _fetch_paginated_history(
    api_key: str,
    secret: str,
    path: str,
    start_ms: int,
    end_ms: int,
    coin: str = "",
) -> Tuple[Optional[str], List[Dict[str, Any]]]:
    all_rows: List[Dict[str, Any]] = []
    seen_ids: set[str] = set()

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


def fetch_deposit_history(
    api_key: str,
    secret: str,
    start_ms: int,
    end_ms: int,
    coin: str = "",
) -> Tuple[Optional[str], List[Dict[str, Any]]]:
    return _fetch_paginated_history(
        api_key,
        secret,
        "/sapi/v1/capital/deposit/hisrec",
        start_ms,
        end_ms,
        coin,
    )


def fetch_withdraw_history(
    api_key: str,
    secret: str,
    start_ms: int,
    end_ms: int,
    coin: str = "",
) -> Tuple[Optional[str], List[Dict[str, Any]]]:
    return _fetch_paginated_history(
        api_key,
        secret,
        "/sapi/v1/capital/withdraw/history",
        start_ms,
        end_ms,
        coin,
    )


def _deposit_time_ms(row: Dict[str, Any]) -> int:
    for key in ("insertTime", "completeTime"):
        value = row.get(key)
        if value is not None and str(value).strip() != "":
            return int(float(value))
    return 0


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


def filter_by_time_and_status(
    rows: List[Dict[str, Any]],
    start_ms: int,
    end_ms: int,
    time_fn,
    success_status: int,
) -> List[Dict[str, Any]]:
    filtered: List[Dict[str, Any]] = []
    for row in rows:
        ts = time_fn(row)
        if ts and not (start_ms <= ts <= end_ms):
            continue
        if ONLY_SUCCESS and int(row.get("status", -1)) != success_status:
            continue
        filtered.append(row)
    filtered.sort(key=time_fn)
    return filtered


def summarize_by_coin(
    deposits: List[Dict[str, Any]],
    withdraws: List[Dict[str, Any]],
) -> Dict[str, Dict[str, float]]:
    summary: Dict[str, Dict[str, float]] = defaultdict(
        lambda: {"deposit_count": 0.0, "deposit_amount": 0.0, "withdraw_count": 0.0, "withdraw_amount": 0.0}
    )
    for row in deposits:
        coin = str(row.get("coin", "UNKNOWN")).upper()
        summary[coin]["deposit_count"] += 1
        summary[coin]["deposit_amount"] += _to_float(row.get("amount"))
    for row in withdraws:
        coin = str(row.get("coin", "UNKNOWN")).upper()
        summary[coin]["withdraw_count"] += 1
        summary[coin]["withdraw_amount"] += _to_float(row.get("amount"))
    return dict(summary)


def print_deposit_rows(rows: List[Dict[str, Any]]) -> None:
    print(f"{'时间':<20} {'币种':<8} {'数量':>16} {'网络':<10} {'状态':<12} {'txId':<20}")
    print("-" * 96)
    if not rows:
        print("(无充值记录)")
        return
    for row in rows:
        ts = _format_ms(_deposit_time_ms(row))
        coin = str(row.get("coin", ""))
        amount = _to_float(row.get("amount"))
        network = str(row.get("network", ""))
        status = DEPOSIT_STATUS.get(int(row.get("status", -1)), str(row.get("status", "")))
        tx_id = str(row.get("txId", ""))
        if len(tx_id) > 18:
            tx_id = tx_id[:8] + "..." + tx_id[-8:]
        print(f"{ts:<20} {coin:<8} {amount:>16.8f} {network:<10} {status:<12} {tx_id:<20}")


def print_withdraw_rows(rows: List[Dict[str, Any]]) -> None:
    print(
        f"{'时间':<20} {'币种':<8} {'数量':>16} {'手续费':>12} {'网络':<10} {'状态':<12} {'txId':<20}"
    )
    print("-" * 104)
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
        tx_id = str(row.get("txId", ""))
        if len(tx_id) > 18:
            tx_id = tx_id[:8] + "..." + tx_id[-8:]
        print(
            f"{ts:<20} {coin:<8} {amount:>16.8f} {fee:>12.8f} {network:<10} {status:<12} {tx_id:<20}"
        )


def print_coin_summary(summary: Dict[str, Dict[str, float]]) -> None:
    if not summary:
        print("(无汇总数据)")
        return
    print(f"{'币种':<8} {'充值笔数':>8} {'充值数量':>18} {'提现笔数':>8} {'提现数量':>18} {'净变动':>18}")
    print("-" * 84)
    for coin in sorted(summary):
        row = summary[coin]
        deposit_amount = row["deposit_amount"]
        withdraw_amount = row["withdraw_amount"]
        net = deposit_amount - withdraw_amount
        print(
            f"{coin:<8} {int(row['deposit_count']):>8} {deposit_amount:>18.8f} "
            f"{int(row['withdraw_count']):>8} {withdraw_amount:>18.8f} {net:>18.8f}"
        )


def print_report(
    meta: Dict[str, Any],
    time_start: str,
    time_end: str,
    coin: str,
    deposits: List[Dict[str, Any]],
    withdraws: List[Dict[str, Any]],
) -> None:
    api_key = meta.get("apiKey", "")
    comment = meta.get("comment", "")

    print("=" * 96)
    print(f"Binance 出入金历史查询  ({comment})")
    print(f"apiKey: {api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else f"apiKey: {api_key}")
    print(f"充值接口: {BINANCE_HOST}/sapi/v1/capital/deposit/hisrec")
    print(f"提现接口: {BINANCE_HOST}/sapi/v1/capital/withdraw/history")
    print(f"查询时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"时间范围: [{time_start}, {time_end}]")
    print(f"币种过滤: {coin or '全部'}")
    print(f"仅成功记录: {'是' if ONLY_SUCCESS else '否'}")
    print("-" * 96)

    print(f"\n【充值记录】共 {len(deposits)} 笔")
    print_deposit_rows(deposits)

    print(f"\n【提现记录】共 {len(withdraws)} 笔")
    print_withdraw_rows(withdraws)
    
    print("\n【按币种汇总】")
    print_coin_summary(summarize_by_coin(deposits, withdraws))

    print("\n说明:")
    print("  - 充值时间取 insertTime；提现时间优先 completeTime，否则 applyTime")
    print("  - 单次 API 查询跨度不超过 90 天，脚本会自动分片并分页拉取")
    print("  - 不同币种数量直接相加仅作参考，不代表统一计价后的净值")
    print("=" * 96)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    try:
        dt_start = _parse_dt(TIME_START)
        dt_end = _parse_dt(TIME_END)
    except ValueError as exc:
        print(f"配置错误: {exc}")
        return 1

    if dt_start > dt_end:
        print("配置错误: TIME_START 不能晚于 TIME_END")
        return 1

    start_ms = _dt_to_ms(dt_start)
    end_ms = _dt_to_ms(dt_end)
    coin = (COIN or "").strip().upper()

    api_key = BINANCE_ACCOUNT["apiKey"]
    secret = BINANCE_ACCOUNT["secret"]

    print("正在拉取 Binance 充值记录 ...")
    dep_err, raw_deposits = fetch_deposit_history(api_key, secret, start_ms, end_ms, coin)
    if dep_err:
        print(f"充值查询失败: {dep_err}")
        if not raw_deposits:
            return 1
        print(f"已获取 {len(raw_deposits)} 笔充值（部分数据）")

    print("正在拉取 Binance 提现记录 ...")
    wd_err, raw_withdraws = fetch_withdraw_history(api_key, secret, start_ms, end_ms, coin)
    if wd_err:
        print(f"提现查询失败: {wd_err}")
        if not raw_deposits and not raw_withdraws:
            return 1
        print(f"已获取 {len(raw_withdraws)} 笔提现（部分数据）")

    deposits = filter_by_time_and_status(raw_deposits, start_ms, end_ms, _deposit_time_ms, success_status=1)
    withdraws = filter_by_time_and_status(raw_withdraws, start_ms, end_ms, _withdraw_time_ms, success_status=6)

    print_report(BINANCE_ACCOUNT, TIME_START, TIME_END, coin, deposits, withdraws)
    return 0 if not dep_err and not wd_err else 1


if __name__ == "__main__":
    sys.exit(main())

