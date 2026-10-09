#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
查询 WebSea 现货账户资产 + Gate / Binance 现货账户权益（独立脚本，无项目依赖）。

WebSea 账户来源: abclibs/account.py maker_near / maker_defense / maker_depth /
                 dc / spot_bak_1~4
WebSea 接口: GET /openApi/wallet/list

Gate 接口: GET /api/v4/spot/accounts（签名逻辑与 gateio.GateioApi 一致）
Binance 接口: GET /api/v3/account（签名逻辑与 binance.BinanceApi 一致）

依赖: pip install requests
兼容: Python 3.9+
"""

import hashlib
import hmac
import json
import random
import string
import sys
import time
from datetime import datetime
from operator import itemgetter
from typing import Any, Dict, List, Optional, Tuple, Union

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ======================== 写死配置 ========================
# 正式环境开放 API；若内网环境可改为 https://exqv.websea.work
SPOT_HOST = "https://oapi.websea.com"

REQUEST_TIMEOUT = 30

# account.py 第 14-16 行
ACCOUNTS = {
    "maker_near": {
        "token": "18c4725b9d218777c3863f812e21d9a2522",
        "sk": "2ijh2r7nf8nvjce4rnq7",
        "uid": 11,
        "comment": "whm",
    },
    "maker_defense": {
        "token": "291d6fa8dc35f58690c38f7c3afcf2h2808",
        "sk": "7rk8zhyxbbxk5ro8r4to",
        "uid": 12,
        "comment": "here",
    },
    "maker_depth": {
        "token": "e5451dae5de519289e45aaab4be461f2856",
        "sk": "lmtn1yxnlwq6ecjqs5yv",
        "uid": 13,
        "comment": "hyy",
    },
    # account.py 第 39-48 行
    "dc": {
        "token": "78fc47c5590f77ca42d1e2c3bb432813",
        "sk": "5e5yg7ga285hctuqrtpb",
        "uid": 196,
        "comment": "自动充提",
    },
    "spot_bak_1": {
        "token": "4ee5b2948440de07dc09c139835cfep3248",
        "sk": "ali6bpfyqv4lgaln4eq9",
        "uid": 14,
        "comment": "spot_bak_1",
    },
    "spot_bak_2": {
        "token": "d83e771c4d55f1fef98e34a2c43772o3330",
        "sk": "g1xo2axzjdax2ujh6twf",
        "uid": 15,
        "comment": "spot_bak_2",
    },
    "spot_bak_3": {
        "token": "027dc638e8819a3f8233645c9de076r3534",
        "sk": "rpaw214rnbgvt0vhl52j",
        "uid": 16,
        "comment": "spot_bak_3",
    },
    "spot_bak_4": {
        "token": "2ec49187f681419d1959af499d7bb0p3584",
        "sk": "wcj34ct96l2vh3s1hog7",
        "uid": 17,
        "comment": "spot_bak_4",
    },
}

# True: 只输出 available 或 frozen 非零的币种；False: 输出 API 返回的全部币种
ONLY_NONZERO = True

# Gate 现货对冲账户（GET /api/v4/spot/accounts）
GATE_HOST = "https://api.gateio.ws"
GATE_API_PREFIX = "/api/v4"

GATE_ACCOUNT = {
    "apiKey": "dd0eeebf5f147b1c8c1cfb5c1db2f38f",
    "secret": "a05598264dd97f2b3aa614efea65b69b02fd972c3f285253da80c43a95b6343e",
    "comment": "gate对冲",
}

# Binance 现货账户（GET /api/v3/account）
BINANCE_HOST = "https://api.binance.com"

BINANCE_ACCOUNT = {
    "apiKey": "lWbYa9CHzHSyulhmaPcXLyUT6coxSQAULHgAYU9NjA5UM3qd2SMZeR9cCBd4uiIE",
    "secret": "U40aH29UAiotheaikRk2eUvZtQOt8psNSyNGAYRLocLfeg6HKeIhHDqGkWY8rPqU",
    "comment": "binance现货",
}
# ==========================================================


def sign(token: str, secret_key: str, nonce: str, data: Dict[str, Any]) -> str:
    parts = [token, secret_key, nonce]
    for key, value in data.items():
        parts.append(f"{key}={value}")
    return hashlib.sha1("".join(sorted(parts)).encode("utf-8")).hexdigest()


def make_headers(token: str, secret_key: str, data: Dict[str, Any]) -> Dict[str, str]:
    nonce = "%d_%s" % (int(time.time() * 1000), "".join(random.sample(string.ascii_letters + string.digits, 5)))
    return {
        "Token": token,
        "Nonce": nonce,
        "Signature": sign(token, secret_key, nonce, data),
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_5) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"
        ),
    }


def fetch_spot_wallet(token: str, secret_key: str, show_all: bool = True) -> Dict[str, Any]:
    url = SPOT_HOST.rstrip("/") + "/openApi/wallet/list"
    params: Dict[str, Any] = {}
    if show_all:
        params["show_all"] = 1
    headers = make_headers(token, secret_key, params)
    resp = requests.get(
        url,
        params=params,
        headers=headers,
        timeout=REQUEST_TIMEOUT,
        verify=False,
    )
    try:
        body = resp.json()
    except json.JSONDecodeError:
        body = {"errno": -1, "errmsg": resp.text, "raw_status": resp.status_code}
    if resp.status_code != 200:
        return {
            "errno": -1,
            "errmsg": f"HTTP {resp.status_code}",
            "result": body,
        }
    return body


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


def _gate_signed_get(path: str, api_key: str, secret: str) -> Tuple[int, Union[List[Any], Dict[str, Any]]]:
    """Gate API v4 签名 GET，返回 (http_status, body)。"""
    full_path = f"{GATE_API_PREFIX}{path}"
    url = f"{GATE_HOST.rstrip('/')}{full_path}"
    timestamp = str(time.time())
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "KEY": api_key,
        "Timestamp": timestamp,
        "SIGN": _gate_gen_sign(secret, "GET", full_path, timestamp),
    }
    resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
    try:
        body = resp.json()
    except json.JSONDecodeError:
        body = {"errmsg": resp.text, "raw_status": resp.status_code}
    return resp.status_code, body


def fetch_gate_spot_accounts(api_key: str, secret: str) -> Dict[str, Any]:
    status, body = _gate_signed_get("/spot/accounts", api_key, secret)
    if status != 200:
        return {
            "errno": -1,
            "errmsg": f"HTTP {status}",
            "result": body,
        }
    if not isinstance(body, list):
        return {
            "errno": -1,
            "errmsg": "unexpected response",
            "result": body,
        }
    return {"errno": 0, "result": body}


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
    """Binance 签名 GET，返回 (http_status, body)。"""
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
    except json.JSONDecodeError:
        body = {"errmsg": resp.text, "raw_status": resp.status_code}
    return resp.status_code, body


def fetch_binance_spot_account(api_key: str, secret: str) -> Dict[str, Any]:
    status, body = _binance_signed_get("/api/v3/account", api_key, secret)
    if status != 200:
        return {
            "errno": -1,
            "errmsg": f"HTTP {status}",
            "result": body,
        }
    if not isinstance(body, dict):
        return {
            "errno": -1,
            "errmsg": "unexpected response",
            "result": body,
        }
    if "code" in body:
        return {
            "errno": -1,
            "errmsg": body.get("msg", "binance error"),
            "result": body,
        }
    balances = body.get("balances")
    if not isinstance(balances, list):
        return {
            "errno": -1,
            "errmsg": "unexpected response",
            "result": body,
        }
    return {"errno": 0, "result": balances}


def _to_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def normalize_wallet_rows(payload: Dict[str, Any]) -> Tuple[Optional[str], List[Dict[str, Any]]]:
    if payload.get("errno") != 0:
        return payload.get("errmsg", "unknown error"), []

    result = payload.get("result") or []
    rows: List[Dict[str, Any]] = []
    for item in result:
        if not isinstance(item, dict):
            continue
        available = _to_float(item.get("available", 0))
        frozen = _to_float(item.get("frozen", 0))
        total = available + frozen
        if ONLY_NONZERO and total <= 0:
            continue
        rows.append(
            {
                "currency": str(item.get("currency", "")),
                "available": available,
                "frozen": frozen,
                "total": total,
            }
        )
    rows.sort(key=lambda x: (-x["total"], x["currency"]))
    return None, rows


def normalize_gate_wallet_rows(payload: Dict[str, Any]) -> Tuple[Optional[str], List[Dict[str, Any]]]:
    if payload.get("errno") != 0:
        return payload.get("errmsg", "unknown error"), []

    result = payload.get("result") or []
    rows: List[Dict[str, Any]] = []
    for item in result:
        if not isinstance(item, dict):
            continue
        available = _to_float(item.get("available", 0))
        frozen = _to_float(item.get("locked", 0))
        total = available + frozen
        if ONLY_NONZERO and total <= 0:
            continue
        currency = str(item.get("currency", "")).upper()
        rows.append(
            {
                "currency": currency,
                "available": available,
                "frozen": frozen,
                "total": total,
            }
        )
    rows.sort(key=lambda x: (-x["total"], x["currency"]))
    return None, rows


def normalize_binance_wallet_rows(payload: Dict[str, Any]) -> Tuple[Optional[str], List[Dict[str, Any]]]:
    if payload.get("errno") != 0:
        return payload.get("errmsg", "unknown error"), []

    result = payload.get("result") or []
    rows: List[Dict[str, Any]] = []
    for item in result:
        if not isinstance(item, dict):
            continue
        available = _to_float(item.get("free", 0))
        frozen = _to_float(item.get("locked", 0))
        total = available + frozen
        if ONLY_NONZERO and total <= 0:
            continue
        currency = str(item.get("asset", "")).upper()
        rows.append(
            {
                "currency": currency,
                "available": available,
                "frozen": frozen,
                "total": total,
            }
        )
    rows.sort(key=lambda x: (-x["total"], x["currency"]))
    return None, rows


def print_account_wallet(name: str, meta: Dict[str, Any], payload: Dict[str, Any]) -> bool:
    err, rows = normalize_wallet_rows(payload)
    uid = meta.get("uid")
    comment = meta.get("comment", "")

    print("=" * 72)
    print(f"账户: {name}  uid={uid}  ({comment})")
    print(f"查询时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"接口: {SPOT_HOST}/openApi/wallet/list")

    if err:
        print(f"查询失败: {err}")
        print(f"原始响应: {json.dumps(payload, ensure_ascii=False)}")
        return False

    if not rows:
        print("(无有余额的币种)")
        return True

    print(f"{'币种':<12} {'可用':>18} {'冻结':>18} {'合计':>18}")
    print("-" * 72)
    sum_available = 0.0
    sum_frozen = 0.0
    for row in rows:
        print(
            f"{row['currency']:<12} "
            f"{row['available']:>18.8f} "
            f"{row['frozen']:>18.8f} "
            f"{row['total']:>18.8f}"
        )
        sum_available += row["available"]
        sum_frozen += row["frozen"]
    print("-" * 72)
    print(
        f"{'[汇总]':<12} "
        f"{sum_available:>18.8f} "
        f"{sum_frozen:>18.8f} "
        f"{sum_available + sum_frozen:>18.8f}  (币种数 {len(rows)})"
    )
    usdt = next((r for r in rows if r["currency"].upper() == "USDT"), None)
    if usdt:
        print(
            f"USDT 可用={usdt['available']:.4f}  "
            f"冻结={usdt['frozen']:.4f}  "
            f"合计={usdt['total']:.4f}"
        )
    return True


def print_gate_account_wallet(name: str, meta: Dict[str, Any], payload: Dict[str, Any]) -> bool:
    err, rows = normalize_gate_wallet_rows(payload)
    comment = meta.get("comment", "")
    api_key = meta.get("apiKey", "")

    print("=" * 72)
    print(f"账户: {name}  ({comment})")
    print(f"apiKey: {api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else f"apiKey: {api_key}")
    print(f"查询时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"接口: {GATE_HOST}{GATE_API_PREFIX}/spot/accounts")

    if err:
        print(f"查询失败: {err}")
        print(f"原始响应: {json.dumps(payload, ensure_ascii=False)}")
        return False

    if not rows:
        print("(无有余额的币种)")
        return True

    print(f"{'币种':<12} {'可用':>18} {'冻结':>18} {'合计':>18}")
    print("-" * 72)
    sum_available = 0.0
    sum_frozen = 0.0
    for row in rows:
        print(
            f"{row['currency']:<12} "
            f"{row['available']:>18.8f} "
            f"{row['frozen']:>18.8f} "
            f"{row['total']:>18.8f}"
        )
        sum_available += row["available"]
        sum_frozen += row["frozen"]
    print("-" * 72)
    print(
        f"{'[汇总]':<12} "
        f"{sum_available:>18.8f} "
        f"{sum_frozen:>18.8f} "
        f"{sum_available + sum_frozen:>18.8f}  (币种数 {len(rows)})"
    )
    usdt = next((r for r in rows if r["currency"] == "USDT"), None)
    if usdt:
        print(
            f"USDT 可用={usdt['available']:.4f}  "
            f"冻结={usdt['frozen']:.4f}  "
            f"合计={usdt['total']:.4f}"
        )
    return True


def print_binance_account_wallet(name: str, meta: Dict[str, Any], payload: Dict[str, Any]) -> bool:
    err, rows = normalize_binance_wallet_rows(payload)
    comment = meta.get("comment", "")
    api_key = meta.get("apiKey", "")

    print("=" * 72)
    print(f"账户: {name}  ({comment})")
    print(f"apiKey: {api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else f"apiKey: {api_key}")
    print(f"查询时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"接口: {BINANCE_HOST}/api/v3/account")

    if err:
        print(f"查询失败: {err}")
        print(f"原始响应: {json.dumps(payload, ensure_ascii=False)}")
        return False

    if not rows:
        print("(无有余额的币种)")
        return True

    print(f"{'币种':<12} {'可用':>18} {'冻结':>18} {'合计':>18}")
    print("-" * 72)
    sum_available = 0.0
    sum_frozen = 0.0
    for row in rows:
        print(
            f"{row['currency']:<12} "
            f"{row['available']:>18.8f} "
            f"{row['frozen']:>18.8f} "
            f"{row['total']:>18.8f}"
        )
        sum_available += row["available"]
        sum_frozen += row["frozen"]
    print("-" * 72)
    print(
        f"{'[汇总]':<12} "
        f"{sum_available:>18.8f} "
        f"{sum_frozen:>18.8f} "
        f"{sum_available + sum_frozen:>18.8f}  (币种数 {len(rows)})"
    )
    usdt = next((r for r in rows if r["currency"] == "USDT"), None)
    if usdt:
        print(
            f"USDT 可用={usdt['available']:.4f}  "
            f"冻结={usdt['frozen']:.4f}  "
            f"合计={usdt['total']:.4f}"
        )
    return True


def main() -> int:
    total_accounts = len(ACCOUNTS) + 2
    ok_count = 0

    print(f"WebSea 现货资产查询 | host={SPOT_HOST}")
    for name, meta in ACCOUNTS.items():
        try:
            payload = fetch_spot_wallet(meta["token"], meta["sk"], show_all=True)
            if print_account_wallet(name, meta, payload):
                ok_count += 1
        except requests.RequestException as exc:
            print("=" * 72)
            print(f"账户: {name}  uid={meta.get('uid')}  请求异常: {exc}")

    print()
    print(f"Gate 现货账户权益查询 | host={GATE_HOST}")
    try:
        payload = fetch_gate_spot_accounts(GATE_ACCOUNT["apiKey"], GATE_ACCOUNT["secret"])
        if print_gate_account_wallet("gate", GATE_ACCOUNT, payload):
            ok_count += 1
    except requests.RequestException as exc:
        print("=" * 72)
        print(f"账户: gate  请求异常: {exc}")

    print()
    print(f"Binance 现货账户权益查询 | host={BINANCE_HOST}")
    try:
        payload = fetch_binance_spot_account(BINANCE_ACCOUNT["apiKey"], BINANCE_ACCOUNT["secret"])
        if print_binance_account_wallet("binance", BINANCE_ACCOUNT, payload):
            ok_count += 1
    except requests.RequestException as exc:
        print("=" * 72)
        print(f"账户: binance  请求异常: {exc}")

    print("=" * 72)
    print(f"完成: 成功 {ok_count}/{total_accounts} 个账户")
    return 0 if ok_count == total_accounts else 1


if __name__ == "__main__":
    sys.exit(main())


